"""对话级过程分析：tutor 介入、SP 情绪轨迹、turn-level 评估增量。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.stats_utils import compare_continuous_groups, describe_continuous

TITLE = "Dialogue-level diagnostics (tutor / emotion / latency)"


def analyze(ds: Dataset, settings: Settings) -> dict:
    if ds.learning.empty and ds.exams.empty:
        return {"title": TITLE, "note": "无对话数据"}

    out: dict = {"title": TITLE}

    L = ds.learning.copy()
    L = L[L["method"].isin(("multi_agent", "single_agent", "control"))]

    # ---------- Tutor 介入（仅 MA）
    ma = L[L["method"] == "multi_agent"]
    if not ma.empty:
        out["tutor_interventions"] = describe_continuous(ma["tutor_interventions_count"])

    # ---------- 学生消息长度（按组）
    if "mean_student_msg_chars" in L.columns:
        per_group = {g: sub["mean_student_msg_chars"].dropna().to_numpy()
                     for g, sub in L.groupby("user_group_label")}
        out["student_msg_chars"] = compare_continuous_groups(per_group)

    # ---------- 响应延迟
    if "mean_latency_ms" in L.columns:
        per_group = {g: sub["mean_latency_ms"].dropna().to_numpy()
                     for g, sub in L.groupby("user_group_label")}
        out["mean_latency_ms"] = compare_continuous_groups(per_group)

    # ---------- 情绪轨迹（messages.emotion，仅 patient role）
    msgs_in_learning_or_exam = pd.concat([L[["id"]].rename(columns={"id": "session_id"}),
                                          ds.exams[["id"]].rename(columns={"id": "session_id"})])
    sids = set(msgs_in_learning_or_exam["session_id"].astype(str).tolist())
    if not getattr(ds, "_messages_df", None) is None:
        pass

    return out
