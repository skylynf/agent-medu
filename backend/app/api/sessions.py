from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
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

# 学生临床表单字段 schema —— 仅做白名单 + 截断，不做严格校验。
WORKSHEET_FIELDS: tuple[str, ...] = (
    "chief_complaint",
    "hpi",
    "past_history",
    "physical_exam",
    "differentials",
    "diagnosis",
    "diagnostic_reasoning",
    "investigations",
    "management",
)
WORKSHEET_FIELD_MAX_LEN = 4000


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


@router.get("/{session_id}/worksheet")
async def get_worksheet(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if user.role == "student" and session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权限查看")
    worksheet = session.worksheet_json or {}
    return {
        "session_id": str(session_id),
        "method": session.method,
        "case_id": session.case_id,
        "fields": WORKSHEET_FIELDS,
        "worksheet": worksheet,
    }


@router.put("/{session_id}/worksheet")
async def upsert_worksheet(
    session_id: UUID,
    payload: dict = Body(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != user.id and user.role == "student":
        raise HTTPException(status_code=403, detail="无权限修改")

    incoming = payload.get("worksheet") if isinstance(payload, dict) else None
    if not isinstance(incoming, dict):
        raise HTTPException(status_code=422, detail="worksheet 必须是对象")

    cleaned: dict[str, str] = {}
    for key in WORKSHEET_FIELDS:
        v = incoming.get(key, "")
        if v is None:
            v = ""
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if len(v) > WORKSHEET_FIELD_MAX_LEN:
            v = v[:WORKSHEET_FIELD_MAX_LEN]
        if v:
            cleaned[key] = v

    cleaned["_updated_at"] = datetime.now(timezone.utc).isoformat()

    session.worksheet_json = cleaned
    await db.commit()
    return {
        "session_id": str(session_id),
        "worksheet": cleaned,
    }


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
