import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SurveyResponse(Base):
    """问卷回答（SUS / 开放题 / 人口学）。
    related_session_id 可空：例如学生在完成全部 pipeline 后单独填写。"""

    __tablename__ = "survey_responses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    related_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_sessions.id"), nullable=True, index=True
    )
    instrument: Mapped[str] = mapped_column(String(50), index=True)
    responses_json: Mapped[dict] = mapped_column(JSONB)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")
