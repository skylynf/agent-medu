"""SUS / UES 信度分析（Cronbach α）+ 整体与分量表。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.scoring import sus_item_ids, ues_item_ids, ues_subscale_map, load_survey
from evaluate.stats_utils import cronbach_alpha

TITLE = "Internal consistency reliability (Cronbach α)"


def _reverse_score_5pt(series: pd.Series) -> pd.Series:
    return 6 - pd.to_numeric(series, errors="coerce")


def analyze(ds: Dataset, settings: Settings) -> dict:
    s = ds.surveys_wide.copy()
    if s.empty:
        return {"title": TITLE, "note": "无问卷数据"}

    out: dict = {"title": TITLE}

    # ---------- SUS
    sus_spec = load_survey("sus")
    sus_items = sus_spec["items"]
    sus_df = pd.DataFrame()
    for it in sus_items:
        col = f"sus_{it['id']}"
        if col not in s.columns:
            continue
        v = pd.to_numeric(s[col], errors="coerce")
        if it.get("reverse"):
            v = _reverse_score_5pt(v)
        sus_df[it["id"]] = v
    out["sus"] = {
        "overall": cronbach_alpha(sus_df),
        "by_group": {
            g: cronbach_alpha(sus_df.loc[s["group_label"] == g])
            for g in s["group_label"].dropna().unique()
        },
    }

    # ---------- UES（按分量表 + 整体）
    ues_spec = load_survey("ues")
    ues_items = ues_spec["items"]
    ues_df = pd.DataFrame()
    sub_dfs: dict[str, pd.DataFrame] = {"fa": pd.DataFrame(), "pu": pd.DataFrame(),
                                        "ae": pd.DataFrame(), "rw": pd.DataFrame()}
    for it in ues_items:
        col = f"ues_{it['id']}"
        if col not in s.columns:
            continue
        v = pd.to_numeric(s[col], errors="coerce")
        if it.get("reverse"):
            v = _reverse_score_5pt(v)
        ues_df[it["id"]] = v
        sub = it.get("subscale")
        if sub in sub_dfs:
            sub_dfs[sub][it["id"]] = v
    out["ues"] = {
        "overall": cronbach_alpha(ues_df),
        "by_subscale": {k: cronbach_alpha(df) for k, df in sub_dfs.items()},
        "overall_by_group": {
            g: cronbach_alpha(ues_df.loc[s["group_label"] == g])
            for g in s["group_label"].dropna().unique()
        },
    }

    return out
