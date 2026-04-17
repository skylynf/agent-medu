from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class SessionCreate(BaseModel):
    case_id: str
    method: str = "multi_agent"


class SessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    case_id: str
    method: str
    started_at: datetime
    ended_at: datetime | None
    total_messages: int
    student_messages: int
    tutor_interventions_count: int
    final_score: float | None
    checklist_json: dict | None
    prompt_versions_json: dict | None = None
    worksheet_json: dict | None = None

    model_config = {"from_attributes": True}


class SessionSummary(BaseModel):
    session_id: UUID
    case_id: str
    method: str = "multi_agent"
    final_score: float
    completion_rate: float
    total_messages: int
    student_messages: int
    tutor_interventions_count: int
    duration_seconds: int
    checklist: dict
    critical_missed: list[str]
    strengths: list[str]
    improvements: list[str]
