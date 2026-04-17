"""Control (对照学习) 模式的 REST 端点。"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.cases import load_case
from app.database import get_db
from app.models.session import TrainingSession
from app.models.user import User
from app.sessions.control import ControlSession

router = APIRouter(prefix="/api/sessions/control", tags=["control"])


class ControlStartRequest(BaseModel):
    case_id: str


class ControlSubmitRequest(BaseModel):
    stage_index: int
    student_input: str


def _instantiate(session: TrainingSession) -> ControlSession:
    return ControlSession(
        session_id=session.id,
        case_id=session.case_id,
        user_id=session.user_id,
    )


@router.post("/start")
async def start_control(
    payload: ControlStartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        load_case(payload.case_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="病例不存在")

    session = TrainingSession(
        user_id=user.id,
        case_id=payload.case_id,
        method="control",
    )
    db.add(session)
    await db.flush()

    cs = _instantiate(session)
    return {
        "session_id": str(session.id),
        "case_id": session.case_id,
        "method": "control",
        "total_stages": cs.total_stages,
        "current_stage": cs.stage_payload(0),
    }


@router.get("/{session_id}/state")
async def control_state(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != user.id and user.role == "student":
        raise HTTPException(status_code=403, detail="无权访问")
    if session.method != "control":
        raise HTTPException(status_code=400, detail="该会话不是对照学习模式")

    cs = _instantiate(session)
    next_index = await cs.current_stage_index(db)
    completed = next_index >= cs.total_stages
    return {
        "session_id": str(session.id),
        "method": "control",
        "case_id": session.case_id,
        "total_stages": cs.total_stages,
        "next_stage_index": next_index,
        "completed": completed,
        "current_stage": None if completed else cs.stage_payload(next_index),
    }


@router.post("/{session_id}/submit")
async def submit_control(
    session_id: UUID,
    payload: ControlSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作他人会话")
    if session.method != "control":
        raise HTTPException(status_code=400, detail="该会话不是对照学习模式")

    cs = _instantiate(session)
    try:
        result = await cs.submit_stage(db, payload.stage_index, payload.student_input)
    except IndexError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if result["completed"]:
        await cs.end_session(db)
        await db.commit()
        return {
            "completed": True,
            "next_stage": None,
            "session_id": str(session.id),
        }

    await db.commit()
    return {
        "completed": False,
        "next_stage": result["next_stage"],
        "session_id": str(session.id),
    }


@router.get("/{session_id}/steps")
async def list_control_steps(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """返回学生在每个阶段的输入，研究员或本人可访问。"""
    session = await db.get(TrainingSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session.user_id != user.id and user.role == "student":
        raise HTTPException(status_code=403, detail="无权访问")

    cs = _instantiate(session)
    summary = await cs.end_session(db)
    return summary
