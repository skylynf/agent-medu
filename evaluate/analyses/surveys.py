"""SUS / UES 总分与分量表的组间比较 + 逐题描述。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.scoring import sus_item_ids, ues_item_ids
from evaluate.stats_utils import compare_continuous_groups, describe_continuous

TITLE = "Survey outcomes — SUS & UES"

SUS_VARS = ("sus_total",)
UES_VARS = ("ues_overall", "ues_fa_mean", "ues_pu_mean", "ues_ae_mean", "ues_rw_mean")


def analyze(ds: Dataset, settings: Settings) -> dict:
    s = ds.surveys_wide.copy()
    if s.empty:
        return {"title": TITLE, "note": "无问卷数据"}

    s = s[s["group"].isin(("multi_agent", "single_agent", "control"))]
    s["group_label"] = s["group_label"].fillna(s["group"])

    descriptive: dict[str, pd.DataFrame] = {}
    tests: dict[str, dict] = {}
    item_descriptive: dict[str, pd.DataFrame] = {}

    for var in SUS_VARS + UES_VARS:
        if var not in s.columns:
            continue
        rows = []
        groups = {}
        for g, sub in s.groupby("group_label"):
            d = describe_continuous(sub[var])
            d["group"] = g
            rows.append(d)
            groups[g] = sub[var].dropna().to_numpy()
        descriptive[var] = pd.DataFrame(rows).set_index("group").reset_index()
        tests[var] = compare_continuous_groups(groups)

    # 逐题分量表均值（仅描述）
    for prefix, items in (("sus", sus_item_ids()), ("ues", ues_item_ids())):
        rows = []
        for q in items:
            col = f"{prefix}_{q}"
            if col not in s.columns:
                continue
            for g, sub in s.groupby("group_label"):
                vals = pd.to_numeric(sub[col], errors="coerce").dropna()
                rows.append({
                    "item": q,
                    "group": g,
                    "n": int(len(vals)),
                    "mean": float(vals.mean()) if len(vals) else None,
                    "sd": float(vals.std(ddof=1)) if len(vals) > 1 else None,
                })
        item_descriptive[prefix] = pd.DataFrame(rows)

    completion_rate = {
        "sus_complete_rate": round(s["sus_complete"].fillna(0).mean(), 3) if "sus_complete" in s.columns else None,
        "ues_complete_rate": round(s["ues_complete"].fillna(0).mean(), 3) if "ues_complete" in s.columns else None,
    }

    return {
        "title": TITLE,
        "n_students": int(len(s)),
        "completion_rate": completion_rate,
        "descriptive": descriptive,
        "tests": tests,
        "item_descriptive": item_descriptive,
    }
