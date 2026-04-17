"""MultiAgentSession：完整的三智能体协作模式（AI-SP + Tutor + Silent Evaluator）。

行为与原 `app.agents.orchestrator.SessionOrchestrator` 完全一致，仅做文件迁移与基类化。
"""

from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.evaluator_agent import evaluate_exchange
from app.agents.final_evaluator import evaluate_exam
from app.agents.sp_agent import generate_sp_response
from app.agents.tutor_agent import evaluate_need_for_intervention
from app.evaluation.checklist import (
    compute_score,
    create_empty_checklist,
    update_checklist,
)
from app.models.evaluation import EvaluationSnapshot
from app.models.final_evaluation import FinalEvaluation
from app.models.session import TrainingSession
from app.prompts import PromptRegistry
from app.sessions.base import SendFn, SessionStrategy


class MultiAgentSession(SessionStrategy):
    METHOD = "multi_agent"
    # 结束时也会调用 final_evaluator（基于 worksheet + 全程对话）
    PROMPT_KEYS = ("sp_agent", "tutor_agent", "turn_evaluator", "final_evaluator")

    TUTOR_COOLDOWN_MESSAGES = 2
    TUTOR_MAX_INTERVENTIONS = 5
    TUTOR_MIN_MESSAGES_BEFORE_FIRST = 3

    def __init__(self, session_id: uuid.UUID, case_id: str, user_id: uuid.UUID):
        super().__init__(session_id, case_id, user_id)
        self.checklist = create_empty_checklist()
        self.current_emotion = "baseline"
        self.student_message_count = 0
        self.tutor_intervention_count = 0
        self.last_student_message_time: float | None = None
        self._already_checked: list[str] = []
        self._last_intervention_at_msg: int = 0

    # ---------------------------------------------------------------- opening
    async def get_opening(self) -> dict:
        voluntary = self.case_data["information_layers"]["voluntary"]
        opening = "，".join(voluntary)

        self._append_history("patient", opening)

        score, completion_rate, _ = compute_score(self.checklist)
        return {
            "type": "patient_response",
            "content": opening,
            "emotion": self.current_emotion,
            "eval_update": {
                "checklist": self.checklist,
                "completion_rate": completion_rate,
                "score": score,
            },
        }

    # ------------------------------------------------------------------ tick
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
        student_msg = await self._persist_message(
            db, "student", content, response_latency_ms=latency_ms
        )

        # --- Phase 1: SP response (student is waiting on this) ---
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
        })

        # --- Phase 2: Concurrent eval + tutor ---
        eval_task = evaluate_exchange(
            student_message=content,
            patient_response=sp_response,
            conversation_history=self.conversation_history,
            already_checked=self._already_checked,
        )

        if self._should_check_tutor():
            tutor_task = evaluate_need_for_intervention(
                case_data=self.case_data,
                conversation_history=self.conversation_history,
                checklist_state=self.checklist,
                completion_rate=compute_score(self.checklist)[1],
                last_student_message_time=self.last_student_message_time,
                student_message_count=self.student_message_count,
            )
            eval_result, tutor_result = await asyncio.gather(eval_task, tutor_task)
        else:
            eval_result = await eval_task
            tutor_result = {"should_intervene": False}

        newly_checked = eval_result.get("checked_items", [])
        delta: dict = {}
        if newly_checked:
            delta = update_checklist(self.checklist, newly_checked)
            self._already_checked.extend(newly_checked)

        score, completion_rate, _missed_critical = compute_score(self.checklist)

        student_msg.evaluator_delta_json = {
            "checked_items": newly_checked,
            "reasoning": eval_result.get("reasoning", ""),
        }

        snapshot = EvaluationSnapshot(
            session_id=self.session_id,
            message_id=student_msg.id,
            checklist_state_json=self.checklist,
            completion_rate=completion_rate,
        )
        db.add(snapshot)

        await emit({
            "type": "eval_update",
            "checklist": self.checklist,
            "completion_rate": completion_rate,
            "score": score,
            "delta": delta,
        })

        if tutor_result.get("should_intervene"):
            self.tutor_intervention_count += 1
            self._last_intervention_at_msg = self.student_message_count
            hint_content = tutor_result.get("hint_content", "")

            self._append_history("tutor", hint_content)
            await self._persist_message(db, "tutor", hint_content)

            await emit({
                "type": "tutor_hint",
                "content": hint_content,
                "hint_level": tutor_result.get("hint_level", "moderate"),
                "intervention_type": tutor_result.get("intervention_type"),
            })

        session = await db.get(TrainingSession, self.session_id)
        if session is not None:
            session.total_messages = len(self.conversation_history)
            session.student_messages = self.student_message_count
            session.tutor_interventions_count = self.tutor_intervention_count
            session.checklist_json = self.checklist

        await db.flush()
        return responses

    def _should_check_tutor(self) -> bool:
        if self.student_message_count < self.TUTOR_MIN_MESSAGES_BEFORE_FIRST:
            return False
        if self.tutor_intervention_count >= self.TUTOR_MAX_INTERVENTIONS:
            return False
        msgs_since_last = self.student_message_count - self._last_intervention_at_msg
        if self._last_intervention_at_msg > 0 and msgs_since_last < self.TUTOR_COOLDOWN_MESSAGES:
            return False
        return True

    # ------------------------------------------------------------------- end
    async def end_session(self, db: AsyncSession) -> dict:
        score, completion_rate, missed_critical = compute_score(self.checklist)

        # 拉取 worksheet
        session_obj = await db.get(TrainingSession, self.session_id)
        worksheet = (session_obj.worksheet_json if session_obj else None) or None

        started, ended = await self._close_session_record(
            db,
            final_score=score,
            checklist_json=self.checklist,
            student_message_count=self.student_message_count,
            tutor_intervention_count=self.tutor_intervention_count,
        )

        strengths: list[str] = []
        improvements: list[str] = []
        for cat_data in self.checklist.values():
            cat_checked = sum(1 for i in cat_data["items"].values() if i["checked"])
            cat_total = len(cat_data["items"])
            cat_rate = cat_checked / cat_total if cat_total > 0 else 0
            display = cat_data["display_name"]
            if cat_rate >= 0.8:
                strengths.append(f"{display}覆盖充分")
            elif cat_rate < 0.5:
                improvements.append(f"{display}需要加强")

        if not missed_critical:
            strengths.append("所有关键项目均已覆盖")
        else:
            improvements.append(f"遗漏关键项: {', '.join(missed_critical)}")

        # ---- 额外：worksheet 感知的整体诊断推理评估 ----
        # 这一步可能会失败（LLM 超时 / 网络抖动），失败时仍能返回 live-checklist 总结。
        final_eval_payload: dict | None = None
        try:
            fe_result, fe_raw = await evaluate_exam(
                case_data=self.case_data,
                conversation_history=self.conversation_history,
                worksheet=worksheet,
            )
            existing = await db.execute(
                FinalEvaluation.__table__.select().where(
                    FinalEvaluation.session_id == self.session_id
                )
            )
            if existing.first() is None:
                db.add(
                    FinalEvaluation(
                        session_id=self.session_id,
                        checklist_results_json=fe_result["checklist_results"],
                        holistic_scores_json=fe_result["holistic_scores"],
                        diagnosis_given=fe_result["diagnosis_given"],
                        diagnosis_correct=fe_result["diagnosis_correct"],
                        differentials_given_json=fe_result["differentials_given"],
                        strengths_json=fe_result["strengths"],
                        improvements_json=fe_result["improvements"],
                        narrative_feedback=fe_result["narrative_feedback"],
                        raw_llm_output=fe_raw,
                        prompt_version=PromptRegistry.get_version("final_evaluator"),
                    )
                )
                await db.flush()
            final_eval_payload = fe_result
        except Exception:
            # 不让总评失败拖垮 MA 学习的最终响应；前端仍可看到 live-checklist 部分
            final_eval_payload = None

        duration = int((ended - started).total_seconds())
        summary: dict = {
            "type": "session_summary",
            "method": self.METHOD,
            "session_id": str(self.session_id),
            "case_id": self.case_id,
            "final_score": score,
            "completion_rate": completion_rate,
            "total_messages": len(self.conversation_history),
            "student_messages": self.student_message_count,
            "tutor_interventions_count": self.tutor_intervention_count,
            "duration_seconds": duration,
            "checklist": self.checklist,
            "critical_missed": missed_critical,
            "strengths": strengths,
            "improvements": improvements,
            "worksheet": worksheet,
        }
        if final_eval_payload:
            summary.update(
                {
                    "holistic_scores": final_eval_payload["holistic_scores"],
                    "diagnosis_given": final_eval_payload["diagnosis_given"],
                    "diagnosis_correct": final_eval_payload["diagnosis_correct"],
                    "differentials_given": final_eval_payload["differentials_given"],
                    "narrative_feedback": final_eval_payload["narrative_feedback"],
                    "final_eval_strengths": final_eval_payload["strengths"],
                    "final_eval_improvements": final_eval_payload["improvements"],
                }
            )
        return summary
