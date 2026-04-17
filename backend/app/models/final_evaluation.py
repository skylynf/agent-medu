import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class FinalEvaluation(Base):
    """考试方法 (ExamSession) 结束后由 final_evaluator 一次性产出的总评。"""

    __tablename__ = "final_evaluations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_sessions.id"), index=True, unique=True
    )
    checklist_results_json: Mapped[dict] = mapped_column(JSONB)
    holistic_scores_json: Mapped[dict] = mapped_column(JSONB)
    diagnosis_given: Mapped[str | None] = mapped_column(Text, nullable=True)
    diagnosis_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    differentials_given_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    strengths_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    improvements_json: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    narrative_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_llm_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TrainingSession", back_populates="final_evaluation")
