"""SessionStrategy 抽象基类与公共工具。

三种学习方法 (MultiAgent / Exam / Control) 共享:
- session_id / case_id / user_id / case_data
- conversation_history（单进程内存中的对话历史）
- DB 写入 Message 的辅助方法

子类至少需实现 `get_opening` / `process_student_message` / `end_session`。
ControlSession 不通过 WS 互动，会重写部分接口，但仍继承本基类便于持久化复用。
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.cases import load_case
from app.models.message import Message
from app.models.session import TrainingSession
from app.prompts import PromptRegistry

SendFn = Optional[Callable[[dict], Awaitable[None]]]


class SessionStrategy(ABC):
    """所有学习方法的策略基类。"""

    METHOD: str = "base"
    # 每个策略声明它使用了哪些 prompt key，写入 TrainingSession.prompt_versions_json
    PROMPT_KEYS: tuple[str, ...] = ()

    def __init__(self, session_id: uuid.UUID, case_id: str, user_id: uuid.UUID):
        self.session_id = session_id
        self.case_id = case_id
        self.user_id = user_id
        self.case_data = load_case(case_id)
        self.conversation_history: list[dict] = []

    # ---------------------------------------------------------------- helpers
    def prompt_versions_snapshot(self) -> dict:
        return {key: PromptRegistry.get_version(key) for key in self.PROMPT_KEYS}

    @staticmethod
    async def _emit(send_fn: SendFn, msg: dict, sink: list[dict] | None = None) -> None:
        if send_fn:
            await send_fn(msg)
        if sink is not None:
            sink.append(msg)

    def _append_history(self, role: str, content: str, **extra) -> dict:
        entry = {"role": role, "content": content, "timestamp": time.time(), **extra}
        self.conversation_history.append(entry)
        return entry

    async def _persist_message(
        self,
        db: AsyncSession,
        role: str,
        content: str,
        *,
        response_latency_ms: int | None = None,
        evaluator_delta_json: dict | None = None,
        emotion: str | None = None,
    ) -> Message:
        msg = Message(
            session_id=self.session_id,
            role=role,
            content=content,
            response_latency_ms=response_latency_ms,
            evaluator_delta_json=evaluator_delta_json,
            emotion=emotion,
        )
        db.add(msg)
        await db.flush()
        return msg

    async def _save_prompt_versions(self, db: AsyncSession) -> None:
        session = await db.get(TrainingSession, self.session_id)
        if session and not session.prompt_versions_json:
            session.prompt_versions_json = self.prompt_versions_snapshot()
            await db.flush()

    # ----------------------------------------------------------------- API
    @abstractmethod
    async def get_opening(self) -> dict:
        ...

    @abstractmethod
    async def process_student_message(
        self, content: str, db: AsyncSession, send_fn: SendFn = None
    ) -> list[dict]:
        ...

    @abstractmethod
    async def end_session(self, db: AsyncSession) -> dict:
        ...

    # --------------------------------------------------------- shared utility
    async def _close_session_record(
        self,
        db: AsyncSession,
        *,
        final_score: float | None,
        checklist_json: dict | None,
        student_message_count: int,
        tutor_intervention_count: int,
    ) -> tuple[datetime, datetime]:
        session = await db.get(TrainingSession, self.session_id)
        if session is None:
            now = datetime.now(timezone.utc)
            return now, now
        session.ended_at = datetime.now(timezone.utc)
        if final_score is not None:
            session.final_score = final_score
        if checklist_json is not None:
            session.checklist_json = checklist_json
        session.total_messages = len(self.conversation_history)
        session.student_messages = student_message_count
        session.tutor_interventions_count = tutor_intervention_count
        await db.flush()
        return session.started_at or datetime.now(timezone.utc), session.ended_at
