"""考试 checklist 14 项逐条 χ²，控制多重比较。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.scoring import checklist_item_meta
from evaluate.stats_utils import compare_categorical, multipletests_df, proportion_ci

TITLE = "Per-checklist-item coverage by group (Exam scope)"


def analyze(ds: Dataset, settings: Settings) -> dict:
    cl = ds.checklist_long
    if cl.empty:
        return {"title": TITLE, "note": "无 checklist 数据"}

    cl = cl[cl["scope"] == "exam"]
    cl = cl[cl["group"].isin(("multi_agent", "single_agent", "control"))]
    if cl.empty:
        return {"title": TITLE, "note": "考试 scope 无数据"}

    meta = checklist_item_meta()
    rows = []
    descriptive_rows = []
    for item, sub in cl.groupby("item"):
        # 比例
        for g, sub2 in sub.groupby("group_label"):
            n = int(sub2["checked"].sum())
            tot = int(len(sub2))
            ci_lo, ci_hi = proportion_ci(n, tot)
            descriptive_rows.append({
                "item": item,
                "category": meta.get(item, {}).get("category_display", ""),
                "critical": meta.get(item, {}).get("critical", False),
                "group": g,
                "n_yes": n, "n_total": tot,
                "rate": round(n / tot, 4) if tot else None,
                "ci_low": round(ci_lo, 4), "ci_high": round(ci_hi, 4),
            })
        ctab = pd.crosstab(sub["checked"], sub["group_label"])
        # 行 = 0/1，列 = group
        for v in (0, 1):
            if v not in ctab.index:
                ctab.loc[v] = 0
        ctab = ctab.sort_index()
        res = compare_categorical(ctab)
        rows.append({
            "item": item,
            "category": meta.get(item, {}).get("category_display", ""),
            "critical": meta.get(item, {}).get("critical", False),
            "test": res.get("test"),
            "statistic": res.get("statistic"),
            "p_raw": res.get("p"),
            "cramers_v": res.get("cramers_v"),
        })

    item_test_df = multipletests_df(pd.DataFrame(rows), "p_raw")
    descriptive_df = pd.DataFrame(descriptive_rows)

    return {
        "title": TITLE,
        "descriptive": descriptive_df,
        "item_tests": item_test_df,
    }
