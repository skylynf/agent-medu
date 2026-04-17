"""人口学（Table 1）+ 组间基线平衡检验。"""
from __future__ import annotations

import pandas as pd

from evaluate.build_dataset import Dataset
from evaluate.config import Settings
from evaluate.stats_utils import compare_categorical, describe_categorical, describe_continuous

TITLE = "Demographics & baseline balance (Table 1)"

CATEGORICAL_VARS = ("role", "institution", "grade")


def _try_to_age(series: pd.Series) -> pd.Series | None:
    """grade 字段在我们的 schema 是字符串，没有数值年龄；如果系统里是数字（年级）也可分析。"""
    s = pd.to_numeric(series, errors="coerce")
    if s.notna().sum() >= 3:
        return s
    return None


def analyze(ds: Dataset, settings: Settings) -> dict:
    s = ds.students.copy()

    # 仅保留组别 ∈ MA/SA/CT 的学生，MIXED / NaN 单独列
    groups = sorted([g for g in s["group"].dropna().unique() if g in ("multi_agent", "single_agent", "control")])

    cat_tables: dict[str, pd.DataFrame] = {}
    cat_tests: dict[str, dict] = {}
    for var in CATEGORICAL_VARS:
        if var not in s.columns:
            continue
        ct = pd.crosstab(s[var].fillna("NA"), s["group_label"])
        cat_tables[var] = ct.reset_index().rename(columns={"index": var})
        cat_tests[var] = compare_categorical(ct)

    # consent
    if "consent_given" in s.columns:
        ct = pd.crosstab(s["consent_given"], s["group_label"])
        cat_tables["consent_given"] = ct.reset_index().rename(columns={"index": "consent_given"})
        cat_tests["consent_given"] = compare_categorical(ct)

    # 数值年龄（如果 grade 列里有数字）
    cont = {}
    age = _try_to_age(s["grade"]) if "grade" in s.columns else None
    if age is not None:
        s2 = s.copy()
        s2["age_numeric"] = age
        per_group = {}
        for g, sub in s2.dropna(subset=["age_numeric"]).groupby("group_label"):
            per_group[g] = describe_continuous(sub["age_numeric"])
        cont["age_numeric"] = per_group

    return {
        "title": TITLE,
        "groups": groups,
        "categorical_tables": cat_tables,
        "categorical_tests": cat_tests,
        "continuous_descriptive": cont,
    }
