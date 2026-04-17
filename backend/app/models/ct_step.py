import uuid
from datetime import datetime
from sqlalchemy import Integer, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CTStep(Base):
    """对照组 (Control / Progressive Disclosure) 学习中每个阶段的快照。
    记录系统当时披露的内容、对学生的提示、以及学生填写的答复。"""

    __tablename__ = "ct_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("training_sessions.id"), index=True
    )
    stage_index: Mapped[int] = mapped_column(Integer)
    stage_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    disclosed_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_to_student: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    session = relationship("TrainingSession", back_populates="ct_steps")
