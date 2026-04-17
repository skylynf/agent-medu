import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(100), index=True)
    # 训练方法：multi_agent | control | exam
    method: Mapped[str] = mapped_column(String(20), default="multi_agent", server_default="multi_agent", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    student_messages: Mapped[int] = mapped_column(Integer, default=0)
    tutor_interventions_count: Mapped[int] = mapped_column(Integer, default=0)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    checklist_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    pre_survey_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    post_survey_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 本会话使用的 prompt 版本快照，例如 {"sp_agent": "v2", "tutor_agent": "v1", ...}
    prompt_versions_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # 学生在 MA / Exam 模式下边问诊边填写的临床表单（鉴别诊断、最终诊断、处置等）。
    # 终评时与对话记录一并送入 final_evaluator，作为评判依据。
    worksheet_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    user = relationship("User", back_populates="sessions")
    messages = relationship(
        "Message", back_populates="session", lazy="selectin", order_by="Message.timestamp"
    )
    snapshots = relationship("EvaluationSnapshot", back_populates="session", lazy="selectin")
    final_evaluation = relationship(
        "FinalEvaluation", back_populates="session", uselist=False, lazy="selectin"
    )
    ct_steps = relationship(
        "CTStep", back_populates="session", lazy="selectin", order_by="CTStep.stage_index"
    )
