from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SessionStats(BaseModel):
    session_id: UUID
    case_id: str
    user_id: UUID
    username: str
    started_at: datetime
    duration_seconds: int | None
    final_score: float | None
    completion_rate: float | None
    student_messages: int
    tutor_interventions_count: int


class LearningCurvePoint(BaseModel):
    session_index: int
    case_id: str
    score: float
    completion_rate: float
    timestamp: datetime


class ChecklistHeatmapItem(BaseModel):
    item_name: str
    category: str
    coverage_rate: float
    total_sessions: int


class TutorInterventionStats(BaseModel):
    intervention_type: str
    count: int
    avg_session_index: float
