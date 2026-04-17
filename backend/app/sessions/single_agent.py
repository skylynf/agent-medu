"""SingleAgentSession：单智能体学习模式 — 仅与 AI-SP 自由对话。

与 MultiAgent 的区别：
- 不调用 Tutor Agent（无苏格拉底式提示）
- 不调用 Turn Evaluator（无逐轮 checklist 打勾）
- 不调用 Final Evaluator（结束时不出 OSCE/诊断评分）

与 Exam 的区别：
- 结束时不显示评分、不进行总评 LLM 调用，只返回用时、对话轮数等元信息
- 用于「单智能体 vs 多智能体」的消融对照

UI 上学生看不到任何分数（与 MA 模式结尾屏蔽 final_score 的设计一致：
学生看到的是「本次共问诊 N 次，用时 M 分钟」之类的回顾页）。
"""

from __future__ import annotations

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.sp_agent import generate_sp_response
from app.models.session import TrainingSession
from app.sessions.base import SendFn, SessionStrategy


class SingleAgentSession(SessionStrategy):
    METHOD = "single_agent"
    # 单智能体只用 SP 一个 prompt
    PROMPT_KEYS = ("sp_agent",)

    def __init__(self, session_id: uuid.UUID, case_id: str, user_id: uuid.UUID):
        super().__init__(session_id, case_id, user_id)
        self.current_emotion = "baseline"
        self.student_message_count = 0
        self.last_student_message_time: float | None = None

    # ---------------------------------------------------------------- opening
    async def get_opening(self) -> dict:
        voluntary = self.case_data["information_layers"]["voluntary"]
        opening = "，".join(voluntary)
        self._append_history("patient", opening)
        return {
            "type": "patient_response",
            "content": opening,
            "emotion": self.current_emotion,
            "single_agent_mode": True,
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
            "single_agent_mode": True,
        })

        session = await db.get(TrainingSession, self.session_id)
        if session is not None:
            session.total_messages = len(self.conversation_history)
            session.student_messages = self.student_message_count

        await db.flush()
        return responses

    # ------------------------------------------------------------------- end
    async def end_session(self, db: AsyncSession) -> dict:
        await self._save_prompt_versions(db)

        session_obj = await db.get(TrainingSession, self.session_id)
        worksheet = (session_obj.worksheet_json if session_obj else None) or None

        # 单智能体模式不出分：final_score / checklist 都置空
        started, ended = await self._close_session_record(
            db,
            final_score=None,
            checklist_json=None,
            student_message_count=self.student_message_count,
            tutor_intervention_count=0,
        )

        duration = int((ended - started).total_seconds())
        return {
            "type": "session_summary",
            "method": self.METHOD,
            "session_id": str(self.session_id),
            "case_id": self.case_id,
            "single_agent_mode": True,
            "total_messages": len(self.conversation_history),
            "student_messages": self.student_message_count,
            "tutor_interventions_count": 0,
            "duration_seconds": duration,
            "worksheet": worksheet,
            # 显式不返回 final_score / checklist / holistic_scores —— 学生看不到任何分数
        }
