from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.session import TrainingSession
from app.models.survey import SurveyResponse
from app.models.user import User
from app.surveys import (
    KNOWN_INSTRUMENTS,
    compute_sus_score,
    compute_ues_score,
    list_instruments,
    load_instrument,
)

router = APIRouter(prefix="/api/surveys", tags=["surveys"])


class SurveySubmit(BaseModel):
    instrument: str
    related_session_id: UUID | None = None
    responses: dict = Field(default_factory=dict)


@router.get("/instruments")
async def get_instruments():
    return list_instruments()


@router.get("/instruments/{instrument}")
async def get_instrument(instrument: str):
    if instrument not in KNOWN_INSTRUMENTS:
        raise HTTPException(status_code=404, detail="未知问卷")
    return load_instrument(instrument)


@router.post("")
async def submit_survey(
    payload: SurveySubmit,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if payload.instrument not in KNOWN_INSTRUMENTS:
        raise HTTPException(status_code=400, detail="未知问卷")

    if payload.instrument == "open_ended":
        spec = load_instrument("open_ended")
        for item in spec.get("items", []):
            if not item.get("required"):
                continue
            qid = item["id"]
            raw = payload.responses.get(qid)
            if raw is None or (isinstance(raw, str) and not str(raw).strip()):
                raise HTTPException(
                    status_code=400,
                    detail="请填写全部标注为必填的主观题后再提交。",
                )

    if payload.related_session_id is not None:
        sess = await db.get(TrainingSession, payload.related_session_id)
        if sess is None or sess.user_id != user.id:
            raise HTTPException(status_code=400, detail="related_session_id 无效")

    response_to_store = dict(payload.responses)
    if payload.instrument == "sus":
        scoring = compute_sus_score(payload.responses)
        if scoring is not None:
            response_to_store["_scoring"] = scoring
    elif payload.instrument == "ues":
        scoring = compute_ues_score(payload.responses)
        if scoring is not None:
            response_to_store["_scoring"] = scoring

    row = SurveyResponse(
        user_id=user.id,
        related_session_id=payload.related_session_id,
        instrument=payload.instrument,
        responses_json=response_to_store,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {
        "id": str(row.id),
        "instrument": row.instrument,
        "submitted_at": row.submitted_at.isoformat() if row.submitted_at else None,
        "scoring": response_to_store.get("_scoring"),
    }


@router.get("/mine")
async def list_my_surveys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SurveyResponse)
        .where(SurveyResponse.user_id == user.id)
        .order_by(SurveyResponse.submitted_at.desc())
    )
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "instrument": r.instrument,
            "related_session_id": str(r.related_session_id) if r.related_session_id else None,
            "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            "responses": r.responses_json,
        }
        for r in rows
    ]
