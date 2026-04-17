"""ExamSession：考试模式 — 仅 AI-SP，结束后一次性整体评估。"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.final_evaluator import evaluate_exam
from app.agents.sp_agent import generate_sp_response
from app.evaluation.checklist import compute_score, create_empty_checklist
from app.models.final_evaluation import FinalEvaluation
from app.models.session import TrainingSession
from app.prompts import PromptRegistry
from app.sessions.base import SendFn, SessionStrategy


class ExamSession(SessionStrategy):
    METHOD = "exam"
    PROMPT_KEYS = ("sp_agent", "final_evaluator")

    def __init__(self, session_id: uuid.UUID, case_id: str, user_id: uuid.UUID):
        super().__init__(session_id, case_id, user_id)
        self.current_emotion = "baseline"
        self.student_message_count = 0
        self.last_student_message_time: float | None = None
        # 占位 checklist：考试模式中前端不显示评估，但 end_session 可在 final_evaluator
        # 失败时回落到 0 完成度。
        self._placeholder_checklist = create_empty_checklist()

    async def get_opening(self) -> dict:
        voluntary = self.case_data["information_layers"]["voluntary"]
        opening = "，".join(voluntary)
        self._append_history("patient", opening)
        return {
            "type": "patient_response",
            "content": opening,
            "emotion": self.current_emotion,
            "exam_mode": True,
        }

    async def process_student_message(
        self, content: str, db: AsyncSession, send_fn: SendFn = None
    ) -> list[dict]:
        responses: list[dict] = []

        async def emit(msg: dict) -> None:
            await self._emit(send_fn, msg, responses)

        await self._save_prompt_versions(db)

        now = time.time()
        latency_ms = (
            int((now - self.last_student_message_time) * 1000)
            if self.last_student_message_time is not None
            else None
        )
        self.last_student_message_time = now
        self.student_message_count += 1

        self._append_history("student", content)
        await self._persist_message(
            db, "student", content, response_latency_ms=latency_ms
        )

        await emit({"type": "typing", "content": ""})

        sp_response, new_emotion = await generate_sp_response(
            case_data=self.case_data,
            conversation_history=self.conversation_history,
            current_emotion=self.current_emotion,
        )
        self.current_emotion = new_emotion

        self._append_history("patient", sp_response)
        await self._persist_message(db, "patient", sp_response, emotion=new_emotion)

        await emit({
            "type": "patient_response",
            "content": sp_response,
            "emotion": new_emotion,
            "exam_mode": True,
        })

        session = await db.get(TrainingSession, self.session_id)
        if session is not None:
            session.total_messages = len(self.conversation_history)
            session.student_messages = self.student_message_count

        await db.flush()
        return responses

    async def end_session(self, db: AsyncSession) -> dict:
        await self._save_prompt_versions(db)

        result, raw = await evaluate_exam(
            case_data=self.case_data,
            conversation_history=self.conversation_history,
        )

        # 把 checklist_results 转成 weighted score 与 placeholder_checklist 同结构
        checklist_state = self._merge_into_checklist(result["checklist_results"])
        score, completion_rate, missed_critical = compute_score(checklist_state)

        # 写入 FinalEvaluation（每个 session 唯一）
        existing = await db.execute(
            FinalEvaluation.__table__.select().where(
                FinalEvaluation.session_id == self.session_id
            )
        )
        if existing.first() is None:
            db.add(
                FinalEvaluation(
                    session_id=self.session_id,
                    checklist_results_json=result["checklist_results"],
                    holistic_scores_json=result["holistic_scores"],
                    diagnosis_given=result["diagnosis_given"],
                    diagnosis_correct=result["diagnosis_correct"],
                    differentials_given_json=result["differentials_given"],
                    strengths_json=result["strengths"],
                    improvements_json=result["improvements"],
                    narrative_feedback=result["narrative_feedback"],
                    raw_llm_output=raw,
                    prompt_version=PromptRegistry.get_version("final_evaluator"),
                )
            )

        started, ended = await self._close_session_record(
            db,
            final_score=score,
            checklist_json=checklist_state,
            student_message_count=self.student_message_count,
            tutor_intervention_count=0,
        )

        duration = int((ended - started).total_seconds())
        return {
            "type": "session_summary",
            "method": self.METHOD,
            "session_id": str(self.session_id),
            "case_id": self.case_id,
            "final_score": score,
            "completion_rate": completion_rate,
            "total_messages": len(self.conversation_history),
            "student_messages": self.student_message_count,
            "tutor_interventions_count": 0,
            "duration_seconds": duration,
            "checklist": checklist_state,
            "checklist_results": result["checklist_results"],
            "holistic_scores": result["holistic_scores"],
            "diagnosis_given": result["diagnosis_given"],
            "diagnosis_correct": result["diagnosis_correct"],
            "differentials_given": result["differentials_given"],
            "critical_missed": missed_critical,
            "strengths": result["strengths"],
            "improvements": result["improvements"],
            "narrative_feedback": result["narrative_feedback"],
        }

    # ------------------------------------------------------------------ utils
    def _merge_into_checklist(self, checklist_results: dict[str, bool]) -> dict:
        """把 LLM 给出的 {item_name: bool} 投影到带分类 / 权重的 checklist 结构上。"""
        checklist = create_empty_checklist()
        for cat_data in checklist.values():
            for item_name, item_state in cat_data["items"].items():
                if checklist_results.get(item_name):
                    item_state["checked"] = True
        return checklist
