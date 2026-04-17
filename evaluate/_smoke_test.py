"""离线烟雾测试：用合成数据跑通 build → 所有 analyses → printers，
不依赖真实数据库。仅用于本地开发调试。

用法： python -m evaluate._smoke_test
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone

import pandas as pd

from evaluate.build_dataset import build
from evaluate.config import get_settings
from evaluate.loader import RawData
from evaluate.scoring import (
    checklist_item_names,
    sus_item_ids,
    ues_item_ids,
)


def _make_users(n_per_group=8):
    rows = []
    for grp in ("multi_agent", "single_agent", "control"):
        for i in range(n_per_group):
            rows.append({
                "id": uuid.uuid4(),
                "username": f"{grp[:2]}_{i:02d}",
                "hashed_password": "x",
                "full_name": f"Stu {grp[:2]}{i}",
                "role": "student",
                "institution": random.choice(["Univ A", "Univ B"]),
                "grade": random.choice(["大三", "大四"]),
                "consent_given": True,
                "created_at": datetime.now(timezone.utc),
                "_group": grp,
            })
    return pd.DataFrame(rows)


def _make_sessions(users):
    cases = ["acute_appendicitis", "acute_pancreatitis", "acute_cholecystitis"]
    sessions = []
    for _, u in users.iterrows():
        # 2 学习
        for s in range(2):
            sessions.append({
                "id": uuid.uuid4(), "user_id": u["id"], "case_id": random.choice(cases),
                "method": u["_group"],
                "started_at": datetime.now(timezone.utc) - timedelta(days=10 - s),
                "ended_at": datetime.now(timezone.utc) - timedelta(days=10 - s) + timedelta(minutes=random.randint(8, 25)),
                "total_messages": random.randint(15, 40),
                "student_messages": random.randint(8, 20),
                "tutor_interventions_count": random.randint(0, 4) if u["_group"] == "multi_agent" else 0,
                "final_score": None,
                "checklist_json": _fake_checklist_nested(u["_group"], s) if u["_group"] == "multi_agent" else None,
                "pre_survey_json": None,
                "post_survey_json": None,
                "prompt_versions_json": {"sp_agent": "v1"},
                "worksheet_json": None,
            })
        # 1 考试
        sessions.append({
            "id": uuid.uuid4(), "user_id": u["id"], "case_id": random.choice(cases),
            "method": "exam",
            "started_at": datetime.now(timezone.utc) - timedelta(days=2),
            "ended_at": datetime.now(timezone.utc) - timedelta(days=2) + timedelta(minutes=random.randint(15, 30)),
            "total_messages": random.randint(20, 60),
            "student_messages": random.randint(12, 30),
            "tutor_interventions_count": 0,
            "final_score": random.uniform(50, 95) + (10 if u["_group"] == "multi_agent" else 0),
            "checklist_json": None,
            "pre_survey_json": None,
            "post_survey_json": None,
            "prompt_versions_json": {"sp_agent": "v1", "final_evaluator": "v1"},
            "worksheet_json": {"diagnosis": "急性阑尾炎"},
        })
    return pd.DataFrame(sessions)


def _fake_checklist_nested(grp, s_idx):
    """模拟 training_sessions.checklist_json 的嵌套结构。"""
    base = 0.4 + 0.15 * s_idx  # session 2 比 1 高
    if grp == "multi_agent":
        base += 0.15
    return {
        "chief_complaint": {
            "display_name": "主诉",
            "items": {
                "诱因": {"checked": random.random() < base, "weight": 1, "critical": False},
                "主要症状": {"checked": random.random() < base + 0.2, "weight": 2, "critical": False},
                "持续时间": {"checked": random.random() < base, "weight": 1, "critical": False},
            },
        },
    }


def _make_messages(sessions):
    rows = []
    for _, s in sessions.iterrows():
        n = int(s["total_messages"])
        for k in range(n):
            role = "student" if k % 2 == 0 else "patient"
            rows.append({
                "id": uuid.uuid4(),
                "session_id": s["id"],
                "role": role,
                "content": "示例消息" * random.randint(2, 8),
                "timestamp": s["started_at"] + timedelta(seconds=k * 30),
                "response_latency_ms": random.randint(800, 4000),
                "evaluator_delta_json": None,
                "emotion": random.choice(["neutral", "anxious", "calm"]) if role == "patient" else None,
            })
    return pd.DataFrame(rows)


def _make_finals(sessions, users):
    rows = []
    user_grp = {u["id"]: u["_group"] for _, u in users.iterrows()}
    items = checklist_item_names()
    for _, s in sessions[sessions["method"] == "exam"].iterrows():
        grp = user_grp.get(s["user_id"], "single_agent")
        boost = {"multi_agent": 0.18, "single_agent": 0.0, "control": 0.05}[grp]
        rows.append({
            "id": uuid.uuid4(),
            "session_id": s["id"],
            "checklist_results_json": {it: (random.random() < (0.45 + boost + random.uniform(-0.05, 0.05))) for it in items},
            "holistic_scores_json": {
                "history_completeness": min(5, max(1, int(round(random.gauss(3.0 + boost * 5, 0.7))))),
                "communication": min(5, max(1, int(round(random.gauss(3.2 + boost * 4, 0.7))))),
                "clinical_reasoning": min(5, max(1, int(round(random.gauss(3.0 + boost * 6, 0.8))))),
                "diagnostic_accuracy": min(5, max(1, int(round(random.gauss(3.1 + boost * 5, 0.8))))),
            },
            "diagnosis_given": "急性阑尾炎",
            "diagnosis_correct": random.random() < (0.55 + boost),
            "differentials_given_json": ["急性胃肠炎", "右侧输尿管结石"],
            "strengths_json": ["问诊系统"],
            "improvements_json": ["过早收敛"],
            "narrative_feedback": "总体合格。",
            "raw_llm_output": None,
            "prompt_version": "v1",
            "created_at": datetime.now(timezone.utc),
        })
    return pd.DataFrame(rows)


def _make_surveys(users):
    rows = []
    for _, u in users.iterrows():
        boost = {"multi_agent": 0.5, "single_agent": 0.0, "control": -0.3}[u["_group"]]
        sus_resp = {qid: max(1, min(5, int(round(random.gauss(3.5 + boost, 0.7))))) for qid in sus_item_ids()}
        ues_resp = {qid: max(1, min(5, int(round(random.gauss(3.7 + boost, 0.6))))) for qid in ues_item_ids()}
        rows.append({
            "id": uuid.uuid4(), "user_id": u["id"], "related_session_id": None,
            "instrument": "sus", "responses_json": sus_resp,
            "submitted_at": datetime.now(timezone.utc),
        })
        rows.append({
            "id": uuid.uuid4(), "user_id": u["id"], "related_session_id": None,
            "instrument": "ues", "responses_json": ues_resp,
            "submitted_at": datetime.now(timezone.utc),
        })
    return pd.DataFrame(rows)


def main():
    random.seed(42)
    users = _make_users(n_per_group=10)
    sessions = _make_sessions(users)
    messages = _make_messages(sessions)
    finals = _make_finals(sessions, users)
    surveys = _make_surveys(users)
    raw = RawData(
        users=users.drop(columns=["_group"]),
        sessions=sessions,
        messages=messages,
        snapshots=pd.DataFrame(),
        finals=finals,
        ct_steps=pd.DataFrame(),
        surveys=surveys,
        prompts=pd.DataFrame(),
    )
    print("[smoke] raw row counts:", raw.info())
    ds = build(raw)
    print("[smoke] dataset:",
          f"students={len(ds.students)} learning={len(ds.learning)} "
          f"exams={len(ds.exams)} cl_long={len(ds.checklist_long)} surveys={len(ds.surveys_wide)}")

    # 跑所有分析模块
    from evaluate.analyses import REGISTRY
    from evaluate.printers import PRINTERS
    settings = get_settings()
    for name, mod in REGISTRY.items():
        print(f"\n========== {name} ==========")
        try:
            res = mod.analyze(ds, settings)
        except Exception as e:
            print(f"  FAILED: {e!r}")
            continue
        printer = PRINTERS.get(name)
        if printer:
            printer(res)


if __name__ == "__main__":
    main()
