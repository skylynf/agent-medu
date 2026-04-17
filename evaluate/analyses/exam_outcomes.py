"""主要结局分析：考试成绩在 MA / SA / CT 之间的差异。

结局变量：
- final_score（如果存在）
- osce_history_completeness / communication / clinical_reasoning / diagnostic_accuracy
- osce_total / osce_mean
- diagnosis_correct（二分类）
- weighted_score_pct / completion_rate / items_checked / missed_critical
- n_differentials_given / worksheet_filled
"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.stats_utils import (
    compare_categorical,
    compare_continuous_groups,
    describe_continuous,
    proportion_ci,
)

TITLE = "Primary outcomes — Exam scores by learning group"

CONTINUOUS_OUTCOMES = (
    "final_score",
    "osce_history_completeness",
    "osce_communication",
    "osce_clinical_reasoning",
    "osce_diagnostic_accuracy",
    "osce_total",
    "osce_mean",
    "weighted_score_pct",
    "completion_rate",
    "items_checked",
    "missed_critical",
    "n_differentials_given",
    "duration_seconds",
    "n_messages",
    "n_student_msgs",
)

BINARY_OUTCOMES = (
    "diagnosis_correct",
    "worksheet_filled",
)


def analyze(ds: Dataset, settings: Settings) -> dict:
    e = ds.exams.copy()
    if e.empty:
        return {"title": TITLE, "note": "无考试数据"}

    # 仅有完整 final_evaluation 的学生
    e = e[e["group"].isin(("multi_agent", "single_agent", "control"))]
    e["group_label"] = e["group_label"].fillna(e["group"])

    descriptive: dict[str, pd.DataFrame] = {}
    tests: dict[str, dict] = {}

    for var in CONTINUOUS_OUTCOMES:
        if var not in e.columns:
            continue
        rows = []
        groups = {}
        for g, sub in e.groupby("group_label"):
            d = describe_continuous(sub[var])
            d["group"] = g
            rows.append(d)
            groups[g] = sub[var].dropna().to_numpy()
        descriptive[var] = pd.DataFrame(rows).set_index("group").reset_index()
        tests[var] = compare_continuous_groups(groups)

    binary: dict[str, dict] = {}
    for var in BINARY_OUTCOMES:
        if var not in e.columns:
            continue
        col = pd.to_numeric(e[var], errors="coerce")
        # 比例
        rows = []
        per_group_counts = []
        for g, sub in e.groupby("group_label"):
            v = pd.to_numeric(sub[var], errors="coerce").dropna().astype(int)
            n = int(v.sum())
            tot = int(v.size)
            ci_lo, ci_hi = proportion_ci(n, tot)
            rows.append({"group": g, "n_yes": n, "n_total": tot,
                         "rate": round(n / tot, 4) if tot else None,
                         "ci_low": round(ci_lo, 4), "ci_high": round(ci_hi, 4)})
            per_group_counts.append((g, n, tot))
        # χ²
        ctab = pd.DataFrame(0, index=["yes", "no"], columns=[g for g, _, _ in per_group_counts])
        for g, n, tot in per_group_counts:
            ctab.loc["yes", g] = n
            ctab.loc["no", g] = tot - n
        binary[var] = {
            "descriptive": pd.DataFrame(rows),
            "test": compare_categorical(ctab),
        }

    return {
        "title": TITLE,
        "n_exams": len(e),
        "continuous": descriptive,
        "continuous_tests": tests,
        "binary": binary,
    }
