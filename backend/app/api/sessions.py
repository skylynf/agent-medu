from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.session import TrainingSession
from app.models.message import Message
from app.api.auth import get_current_user
from app.schemas.session import SessionResponse
from app.schemas.message import MessageResponse

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionResponse])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role in ("teacher", "researcher"):
        result = await db.execute(
            select(TrainingSession).order_by(TrainingSession.started_at.desc())
        )
    else:
        result = await db.execute(
            select(TrainingSession)
            .where(TrainingSession.user_id == user.id)
            .order_by(TrainingSession.started_at.desc())
        )
    return [SessionResponse.model_validate(s) for s in result.scalars().all()]


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if user.role == "student" and session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权限查看")
    return SessionResponse.model_validate(session)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if user.role == "student" and session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权限查看")

    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.timestamp)
    )
    return [MessageResponse.model_validate(m) for m in result.scalars().all()]
