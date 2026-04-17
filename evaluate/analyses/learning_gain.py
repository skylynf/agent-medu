"""第 1 次 vs 第 2 次学习：组内 paired 比较 + 组间 Δ（learning gain）比较。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.stats_utils import compare_continuous_groups, describe_continuous

TITLE = "Within-student learning gain: session 1 → session 2"

OUTCOMES = (
    "duration_seconds",
    "n_messages",
    "n_student_msgs",
    "mean_student_msg_chars",
    "weighted_score_pct",
    "completion_rate",
    "items_checked",
    "snap_final_completion",
    "ct_stages_completed",
    "ct_total_chars",
)


def analyze(ds: Dataset, settings: Settings) -> dict:
    L = ds.learning.copy()
    if L.empty:
        return {"title": TITLE, "note": "无学习会话"}

    L = L[L["method"].isin(("multi_agent", "single_agent", "control"))]

    # 仅保留 session_index ∈ {1, 2}
    L = L[L["session_index"].isin([1, 2])]
    if L.empty:
        return {"title": TITLE, "note": "无 session_index ∈ {1,2} 的会话"}

    # pivot 成 (user_id × method × var × {s1, s2})
    keep = [c for c in OUTCOMES if c in L.columns]
    pivot = L.pivot_table(
        index=["user_id", "method"],
        columns="session_index",
        values=keep,
        aggfunc="mean",
    )
    # MultiIndex 列：(var, session_index) → 重命名
    pivot.columns = [f"{v}__s{int(i)}" for v, i in pivot.columns.to_flat_index()]
    pivot = pivot.reset_index()
    pivot["group_label"] = pivot["method"].map({
        "multi_agent": "MA", "single_agent": "SA", "control": "CT"
    })

    # 计算 Δ
    delta_cols = []
    for v in keep:
        c1 = f"{v}__s1"
        c2 = f"{v}__s2"
        if c1 in pivot.columns and c2 in pivot.columns:
            pivot[f"{v}__delta"] = pivot[c2] - pivot[c1]
            delta_cols.append(v)

    # 组内 paired
    within: dict[str, dict] = {}
    for v in delta_cols:
        per_method: dict[str, dict] = {}
        for g, sub in pivot.groupby("group_label"):
            both = sub.dropna(subset=[f"{v}__s1", f"{v}__s2"])
            if len(both) < 2:
                per_method[g] = {"n": len(both), "note": "样本<2"}
                continue
            res = compare_continuous_groups(
                {"s1": both[f"{v}__s1"].to_numpy(), "s2": both[f"{v}__s2"].to_numpy()},
                paired=True,
            )
            per_method[g] = {
                "n": int(len(both)),
                "describe_s1": describe_continuous(both[f"{v}__s1"]),
                "describe_s2": describe_continuous(both[f"{v}__s2"]),
                "mean_delta": float(both[f"{v}__delta"].mean()),
                "test": res["omnibus"],
                "effect": res.get("effect_size"),
            }
        within[v] = per_method

    # 组间 Δ
    between: dict[str, dict] = {}
    for v in delta_cols:
        col = f"{v}__delta"
        if col not in pivot.columns:
            continue
        groups = {g: sub[col].dropna().to_numpy() for g, sub in pivot.groupby("group_label")}
        between[v] = compare_continuous_groups(groups)

    return {
        "title": TITLE,
        "outcomes_analyzed": delta_cols,
        "wide_table": pivot,
        "within_paired": within,
        "between_delta": between,
    }
