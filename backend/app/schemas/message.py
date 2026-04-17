from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    timestamp: datetime
    response_latency_ms: int | None
    evaluator_delta_json: dict | None
    emotion: str | None

    model_config = {"from_attributes": True}


class WSMessage(BaseModel):
    type: str
    content: str | None = None
    case_id: str | None = None


class WSResponse(BaseModel):
    type: str
    content: str | None = None
    emotion: str | None = None
    hint_level: str | None = None
    checklist: dict | None = None
    completion_rate: float | None = None
    final_score: float | None = None
    report: dict | None = None
