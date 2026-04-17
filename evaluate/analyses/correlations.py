"""考试结局 ↔ 学习过程 / 体验 的 Spearman 相关矩阵。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.stats_utils import correlation_table

TITLE = "Correlations: process ↔ outcome ↔ experience"


def analyze(ds: Dataset, settings: Settings) -> dict:
    L = ds.learning.copy()
    E = ds.exams.copy()
    S = ds.surveys_wide.copy()

    if E.empty:
        return {"title": TITLE, "note": "无考试数据"}

    # 每学生 → 学习过程均值
    proc_cols = [c for c in (
        "duration_seconds", "n_messages", "n_student_msgs",
        "mean_student_msg_chars", "weighted_score_pct", "completion_rate",
        "items_checked", "snap_final_completion",
        "ct_stages_completed", "ct_total_chars",
    ) if c in L.columns]

    L_per = L.groupby("user_id")[proc_cols].mean(numeric_only=True).reset_index()
    L_per = L_per.rename(columns={c: f"L_{c}" for c in proc_cols})

    # 考试结局
    exam_cols = [c for c in (
        "final_score", "osce_history_completeness", "osce_communication",
        "osce_clinical_reasoning", "osce_diagnostic_accuracy",
        "osce_total", "weighted_score_pct", "completion_rate",
        "items_checked", "missed_critical", "duration_seconds",
        "n_student_msgs",
    ) if c in E.columns]
    E_per = E.groupby("user_id")[exam_cols].mean(numeric_only=True).reset_index()
    E_per = E_per.rename(columns={c: f"E_{c}" for c in exam_cols})

    surv_cols = [c for c in ("sus_total", "ues_overall", "ues_fa_mean", "ues_pu_mean",
                              "ues_ae_mean", "ues_rw_mean") if c in S.columns]
    if surv_cols:
        S_per = S[["user_id", *surv_cols]].copy()
        S_per = S_per.rename(columns={c: f"S_{c}" for c in surv_cols})
    else:
        S_per = pd.DataFrame(columns=["user_id"])

    # 合并
    L_per["user_id"] = L_per["user_id"].astype(str)
    E_per["user_id"] = E_per["user_id"].astype(str)
    if not S_per.empty:
        S_per["user_id"] = S_per["user_id"].astype(str)

    merged = L_per.merge(E_per, on="user_id", how="outer")
    if not S_per.empty:
        merged = merged.merge(S_per, on="user_id", how="outer")

    cols = [c for c in merged.columns if c != "user_id"]
    if not cols:
        return {"title": TITLE, "note": "无可分析变量"}

    corr = correlation_table(merged, cols, method="spearman")
    return {
        "title": TITLE,
        "merged_table": merged,
        "correlation_long": corr,
    }
