import csv
import io
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.session import TrainingSession
from app.models.message import Message
from app.models.evaluation import EvaluationSnapshot
from app.api.auth import get_current_user
from app.evaluation.checklist import load_rubrics

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _require_researcher(user: User):
    if user.role not in ("teacher", "researcher"):
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="仅教师/研究员可访问")


@router.get("/sessions")
async def get_all_sessions_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_researcher(user)
    result = await db.execute(
        select(TrainingSession).order_by(TrainingSession.started_at.desc())
    )
    sessions = result.scalars().all()
    stats = []
    for s in sessions:
        duration = None
        if s.ended_at and s.started_at:
            duration = int((s.ended_at - s.started_at).total_seconds())

        # Compute completion rate from checklist
        completion_rate = None
        if s.checklist_json:
            total = 0
            checked = 0
            for cat in s.checklist_json.values():
                if isinstance(cat, dict) and "items" in cat:
                    for item in cat["items"].values():
                        total += 1
                        if item.get("checked"):
                            checked += 1
            completion_rate = round(checked / total, 3) if total > 0 else 0

        stats.append({
            "session_id": str(s.id),
            "user_id": str(s.user_id),
            "case_id": s.case_id,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "duration_seconds": duration,
            "final_score": s.final_score,
            "completion_rate": completion_rate,
            "student_messages": s.student_messages,
            "tutor_interventions_count": s.tutor_interventions_count,
        })
    return stats


@router.get("/sessions/{session_id}/timeline")
async def get_session_timeline(
    session_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_researcher(user)
    result = await db.execute(
        select(EvaluationSnapshot)
        .where(EvaluationSnapshot.session_id == session_id)
        .order_by(EvaluationSnapshot.timestamp)
    )
    snapshots = result.scalars().all()
    return [
        {
            "message_id": str(s.message_id),
            "completion_rate": s.completion_rate,
            "timestamp": s.timestamp.isoformat(),
        }
        for s in snapshots
    ]


@router.get("/learning-curve")
async def get_learning_curve(
    user_id: UUID = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role == "student" and user.id != user_id:
        _require_researcher(user)

    result = await db.execute(
        select(TrainingSession)
        .where(TrainingSession.user_id == user_id)
        .order_by(TrainingSession.started_at)
    )
    sessions = result.scalars().all()
    return [
        {
            "session_index": i + 1,
            "case_id": s.case_id,
            "score": s.final_score,
            "started_at": s.started_at.isoformat(),
            "student_messages": s.student_messages,
            "tutor_interventions": s.tutor_interventions_count,
        }
        for i, s in enumerate(sessions)
        if s.final_score is not None
    ]


@router.get("/checklist-heatmap")
async def get_checklist_heatmap(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_researcher(user)
    result = await db.execute(
        select(TrainingSession).where(TrainingSession.checklist_json.isnot(None))
    )
    sessions = result.scalars().all()

    rubrics = load_rubrics()
    item_stats: dict[str, dict] = {}

    for cat_key, cat_data in rubrics["history_taking_checklist"].items():
        for item_def in cat_data["items"]:
            item_stats[item_def["item"]] = {
                "category": cat_data["display_name"],
                "checked_count": 0,
                "total_sessions": 0,
            }

    for s in sessions:
        cj = s.checklist_json
        if not cj:
            continue
        for cat_key, cat_data in cj.items():
            if not isinstance(cat_data, dict) or "items" not in cat_data:
                continue
            for item_name, item_state in cat_data["items"].items():
                if item_name in item_stats:
                    item_stats[item_name]["total_sessions"] += 1
                    if item_state.get("checked"):
                        item_stats[item_name]["checked_count"] += 1

    return [
        {
            "item_name": name,
            "category": data["category"],
            "coverage_rate": round(data["checked_count"] / data["total_sessions"], 3)
            if data["total_sessions"] > 0 else 0,
            "total_sessions": data["total_sessions"],
        }
        for name, data in item_stats.items()
    ]


@router.get("/tutor-interventions")
async def get_tutor_interventions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_researcher(user)
    result = await db.execute(
        select(Message).where(Message.role == "tutor").order_by(Message.timestamp)
    )
    messages = result.scalars().all()
    return [
        {
            "session_id": str(m.session_id),
            "content": m.content,
            "timestamp": m.timestamp.isoformat(),
        }
        for m in messages
    ]


@router.get("/export/csv")
async def export_csv(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_researcher(user)
    result = await db.execute(
        select(TrainingSession).order_by(TrainingSession.started_at)
    )
    sessions = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "session_id", "user_id", "case_id", "started_at", "ended_at",
        "duration_seconds", "total_messages", "student_messages",
        "tutor_interventions_count", "final_score",
    ])

    for s in sessions:
        duration = None
        if s.ended_at and s.started_at:
            duration = int((s.ended_at - s.started_at).total_seconds())
        writer.writerow([
            str(s.id), str(s.user_id), s.case_id,
            s.started_at.isoformat() if s.started_at else "",
            s.ended_at.isoformat() if s.ended_at else "",
            duration, s.total_messages, s.student_messages,
            s.tutor_interventions_count, s.final_score,
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=spagent_sessions.csv"},
    )
