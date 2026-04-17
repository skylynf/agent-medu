"""学习阶段过程指标在三组之间的差异（合并 2 次学习取 mean / sum）。

用于揭示：MA 是否产生比 SA 更多的轮次 / 更长的对话 / 更高的 checklist 覆盖；
CT 与对话组的比较以阶段答复字符数等为代表。
"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.stats_utils import compare_continuous_groups, describe_continuous

TITLE = "Learning-phase process indicators (per student average across 2 sessions)"

PER_SESSION_NUMERIC = (
    "duration_seconds",
    "total_messages",
    "student_messages",
    "tutor_interventions_count",
    "n_messages",
    "n_student_msgs",
    "n_patient_msgs",
    "n_tutor_msgs",
    "mean_latency_ms",
    "median_latency_ms",
    "mean_student_msg_chars",
    "snap_final_completion",
    "weighted_score_pct",
    "completion_rate",
    "items_checked",
    "missed_critical",
    "ct_stages_completed",
    "ct_total_chars",
)


def analyze(ds: Dataset, settings: Settings) -> dict:
    L = ds.learning.copy()
    if L.empty:
        return {"title": TITLE, "note": "无学习会话"}

    # 仅保留 method ∈ MA/SA/CT
    L = L[L["method"].isin(("multi_agent", "single_agent", "control"))]

    # 每学生 × 2 次学习 → 取 mean
    keep_cols = [c for c in PER_SESSION_NUMERIC if c in L.columns]
    if not keep_cols:
        return {"title": TITLE, "note": "无可用过程指标"}

    per_student = (
        L.groupby(["user_id", "method"])[keep_cols]
        .mean(numeric_only=True)
        .reset_index()
    )
    per_student["group_label"] = per_student["method"].map({
        "multi_agent": "MA", "single_agent": "SA", "control": "CT"
    })

    descriptive: dict[str, pd.DataFrame] = {}
    tests: dict[str, dict] = {}
    for var in keep_cols:
        rows = []
        groups: dict = {}
        for g, sub in per_student.groupby("group_label"):
            d = describe_continuous(sub[var])
            d["group"] = g
            rows.append(d)
            groups[g] = sub[var].dropna().to_numpy()
        descriptive[var] = pd.DataFrame(rows).set_index("group").reset_index()
        tests[var] = compare_continuous_groups(groups)

    return {
        "title": TITLE,
        "n_students_analyzed": int(per_student["user_id"].nunique()),
        "n_sessions_analyzed": int(L.shape[0]),
        "per_student_means": per_student,
        "descriptive": descriptive,
        "tests": tests,
    }
