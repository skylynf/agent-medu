"""考试模式总评结果的查询接口。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.final_evaluation import FinalEvaluation
from app.models.session import TrainingSession
from app.models.user import User

router = APIRouter(prefix="/api/sessions", tags=["final_evaluation"])


@router.get("/{session_id}/final-evaluation")
async def get_final_evaluation(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != user.id and user.role == "student":
        raise HTTPException(status_code=403, detail="无权访问他人会话")

    result = await db.execute(
        select(FinalEvaluation).where(FinalEvaluation.session_id == session_id)
    )
    fe = result.scalar_one_or_none()
    if fe is None:
        raise HTTPException(status_code=404, detail="该会话还没有总评结果")

    return {
        "session_id": str(session_id),
        "method": session.method,
        "case_id": session.case_id,
        "checklist_results": fe.checklist_results_json,
        "holistic_scores": fe.holistic_scores_json,
        "diagnosis_given": fe.diagnosis_given,
        "diagnosis_correct": fe.diagnosis_correct,
        "differentials_given": fe.differentials_given_json or [],
        "strengths": fe.strengths_json or [],
        "improvements": fe.improvements_json or [],
        "narrative_feedback": fe.narrative_feedback,
        "prompt_version": fe.prompt_version,
        "created_at": fe.created_at.isoformat() if fe.created_at else None,
    }
