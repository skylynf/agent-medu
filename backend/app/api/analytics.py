"""分析与导出端点。供研究员（role in teacher/researcher）下载实验数据。"""

from __future__ import annotations

import csv
import io
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.evaluation.checklist import load_rubrics
from app.models.ct_step import CTStep
from app.models.evaluation import EvaluationSnapshot
from app.models.final_evaluation import FinalEvaluation
from app.models.message import Message
from app.models.session import TrainingSession
from app.models.survey import SurveyResponse
from app.models.user import User
from app.surveys import compute_sus_score, load_instrument

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _require_researcher(user: User):
    if user.role not in ("teacher", "researcher"):
        raise HTTPException(status_code=403, detail="仅教师/研究员可访问")


# --------------------------------------------------------------- legacy reads

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

        completion_rate = _completion_rate(s.checklist_json)
        stats.append({
            "session_id": str(s.id),
            "user_id": str(s.user_id),
            "case_id": s.case_id,
            "method": s.method,
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
            "method": s.method,
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

    for cat_data in rubrics["history_taking_checklist"].values():
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
        for cat_data in cj.values():
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


# --------------------------------------------------------------- helpers

def _completion_rate(checklist_json: dict | None) -> float | None:
    if not checklist_json:
        return None
    total = 0
    checked = 0
    for cat in checklist_json.values():
        if isinstance(cat, dict) and "items" in cat:
            for item in cat["items"].values():
                total += 1
                if item.get("checked"):
                    checked += 1
    return round(checked / total, 3) if total > 0 else 0


def _sorted_checklist_item_names() -> list[str]:
    rubrics = load_rubrics()
    names: list[str] = []
    for cat_data in rubrics["history_taking_checklist"].values():
        for item in cat_data["items"]:
            names.append(item["item"])
    return names


def _streamed_csv(rows: list[list], filename: str) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.writer(output)
    for r in rows:
        writer.writerow(r)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ------------------------------------------------------------- exports — paper

@router.get("/export/csv")
async def export_csv_legacy(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """旧的精简 CSV 导出（保留兼容）。新代码请用 /export/sessions.csv。"""
    _require_researcher(user)
    result = await db.execute(
        select(TrainingSession).order_by(TrainingSession.started_at)
    )
    sessions = result.scalars().all()

    rows = [[
        "session_id", "user_id", "case_id", "method",
        "started_at", "ended_at", "duration_seconds",
        "total_messages", "student_messages",
        "tutor_interventions_count", "final_score",
    ]]
    for s in sessions:
        duration = None
        if s.ended_at and s.started_at:
            duration = int((s.ended_at - s.started_at).total_seconds())
        rows.append([
            str(s.id), str(s.user_id), s.case_id, s.method,
            s.started_at.isoformat() if s.started_at else "",
            s.ended_at.isoformat() if s.ended_at else "",
            duration, s.total_messages, s.student_messages,
            s.tutor_interventions_count, s.final_score,
        ])
    return _streamed_csv(rows, "spagent_sessions.csv")


@router.get("/export/sessions.csv")
async def export_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """每行一个 session 的宽表，含人口学、方法、整体评分、诊断正误。"""
    _require_researcher(user)
    result = await db.execute(
        select(TrainingSession).order_by(TrainingSession.started_at)
    )
    sessions = result.scalars().all()

    user_ids = {s.user_id for s in sessions}
    user_rows = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in user_rows.scalars().all()}

    fe_rows = await db.execute(
        select(FinalEvaluation).where(FinalEvaluation.session_id.in_([s.id for s in sessions]))
    )
    fe_map = {fe.session_id: fe for fe in fe_rows.scalars().all()}

    header = [
        "session_id", "user_id", "username", "full_name", "institution", "grade", "role",
        "method", "case_id",
        "started_at", "ended_at", "duration_seconds",
        "total_messages", "student_messages", "tutor_interventions_count",
        "final_score", "completion_rate",
        "diagnosis_given", "diagnosis_correct",
        "h_history_completeness", "h_communication", "h_clinical_reasoning", "h_diagnostic_accuracy",
        "prompt_versions",
    ]
    rows: list[list] = [header]
    for s in sessions:
        u = users_map.get(s.user_id)
        fe = fe_map.get(s.id)
        duration = None
        if s.ended_at and s.started_at:
            duration = int((s.ended_at - s.started_at).total_seconds())
        h = (fe.holistic_scores_json or {}) if fe else {}
        rows.append([
            str(s.id),
            str(s.user_id),
            u.username if u else "",
            u.full_name if u else "",
            u.institution if u else "",
            u.grade if u else "",
            u.role if u else "",
            s.method,
            s.case_id,
            s.started_at.isoformat() if s.started_at else "",
            s.ended_at.isoformat() if s.ended_at else "",
            duration if duration is not None else "",
            s.total_messages or 0,
            s.student_messages or 0,
            s.tutor_interventions_count or 0,
            s.final_score if s.final_score is not None else "",
            _completion_rate(s.checklist_json) if s.checklist_json else "",
            fe.diagnosis_given if fe else "",
            fe.diagnosis_correct if fe else "",
            h.get("history_completeness", ""),
            h.get("communication", ""),
            h.get("clinical_reasoning", ""),
            h.get("diagnostic_accuracy", ""),
            json.dumps(s.prompt_versions_json, ensure_ascii=False) if s.prompt_versions_json else "",
        ])
    return _streamed_csv(rows, "medu_spagent_sessions.csv")


@router.get("/export/messages.jsonl")
async def export_messages(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """每行一条 message 的 JSONL，便于定性编码与对话级分析。"""
    _require_researcher(user)
    result = await db.execute(
        select(Message).order_by(Message.session_id, Message.timestamp)
    )
    messages = result.scalars().all()

    def _gen():
        for m in messages:
            yield json.dumps(
                {
                    "session_id": str(m.session_id),
                    "message_id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "emotion": m.emotion,
                    "response_latency_ms": m.response_latency_ms,
                    "evaluator_delta": m.evaluator_delta_json,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                },
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(
        _gen(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=medu_spagent_messages.jsonl"},
    )


@router.get("/export/checklist_matrix.csv")
async def export_checklist_matrix(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """session × checklist_item 的 0/1 宽表（含 method 标签，便于在 SPSS/R 做组间对比）。"""
    _require_researcher(user)

    item_names = _sorted_checklist_item_names()
    result = await db.execute(
        select(TrainingSession).order_by(TrainingSession.started_at)
    )
    sessions = result.scalars().all()

    fe_rows = await db.execute(
        select(FinalEvaluation).where(FinalEvaluation.session_id.in_([s.id for s in sessions]))
    )
    fe_map = {fe.session_id: fe for fe in fe_rows.scalars().all()}

    header = ["session_id", "user_id", "method", "case_id", *item_names]
    rows: list[list] = [header]
    for s in sessions:
        flags: dict[str, int] = {name: 0 for name in item_names}
        # MA 模式优先用 checklist_json；考试模式用 final_evaluation.checklist_results_json
        checklist_json = s.checklist_json
        if checklist_json:
            for cat in checklist_json.values():
                if not isinstance(cat, dict) or "items" not in cat:
                    continue
                for name, st in cat["items"].items():
                    if name in flags and st.get("checked"):
                        flags[name] = 1
        else:
            fe = fe_map.get(s.id)
            if fe and fe.checklist_results_json:
                for name, v in fe.checklist_results_json.items():
                    if name in flags and v:
                        flags[name] = 1

        rows.append([str(s.id), str(s.user_id), s.method, s.case_id] + [flags[n] for n in item_names])

    return _streamed_csv(rows, "medu_spagent_checklist_matrix.csv")


@router.get("/export/surveys.csv")
async def export_surveys(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """SUS 全部 10 题原值 + 反向计分总分；开放题原文。"""
    _require_researcher(user)
    sus_spec = load_instrument("sus")
    sus_item_ids = [it["id"] for it in sus_spec.get("items", [])]
    open_spec = load_instrument("open_ended")
    open_item_ids = [it["id"] for it in open_spec.get("items", [])]

    result = await db.execute(
        select(SurveyResponse).order_by(SurveyResponse.submitted_at)
    )
    rows_db = result.scalars().all()

    user_ids = {r.user_id for r in rows_db}
    u_rows = await db.execute(select(User).where(User.id.in_(user_ids)))
    users_map = {u.id: u for u in u_rows.scalars().all()}

    header = (
        ["response_id", "user_id", "username", "full_name", "institution", "grade",
         "instrument", "related_session_id", "submitted_at"]
        + [f"sus_{qid}" for qid in sus_item_ids]
        + ["sus_total_score", "sus_complete"]
        + [f"open_{qid}" for qid in open_item_ids]
    )

    rows: list[list] = [header]
    for r in rows_db:
        u = users_map.get(r.user_id)
        responses = r.responses_json or {}
        sus_vals = [responses.get(qid, "") for qid in sus_item_ids]
        sus_total = ""
        sus_complete = ""
        if r.instrument == "sus":
            scoring = compute_sus_score(responses) or {}
            sus_total = scoring.get("sus_score") if scoring.get("sus_score") is not None else ""
            sus_complete = "1" if scoring.get("complete") else "0"
        open_vals = [responses.get(qid, "") for qid in open_item_ids]
        rows.append([
            str(r.id),
            str(r.user_id),
            u.username if u else "",
            u.full_name if u else "",
            u.institution if u else "",
            u.grade if u else "",
            r.instrument,
            str(r.related_session_id) if r.related_session_id else "",
            r.submitted_at.isoformat() if r.submitted_at else "",
            *sus_vals,
            sus_total,
            sus_complete,
            *open_vals,
        ])

    return _streamed_csv(rows, "medu_spagent_surveys.csv")


@router.get("/export/ct_steps.jsonl")
async def export_ct_steps(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对照学习每个阶段学生填写的原文，供论文定性分析。"""
    _require_researcher(user)
    result = await db.execute(
        select(CTStep).order_by(CTStep.session_id, CTStep.stage_index)
    )
    steps = result.scalars().all()

    def _gen():
        for s in steps:
            yield json.dumps(
                {
                    "session_id": str(s.session_id),
                    "stage_index": s.stage_index,
                    "title": s.stage_title,
                    "prompt_to_student": s.prompt_to_student,
                    "student_input": s.student_input,
                    "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                },
                ensure_ascii=False,
            ) + "\n"

    return StreamingResponse(
        _gen(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=medu_spagent_ct_steps.jsonl"},
    )
