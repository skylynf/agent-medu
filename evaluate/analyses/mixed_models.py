"""线性混合效应模型 + 序数 / 二元 logistic 回归。

把组别 (MA/SA/CT) 作为固定效应，case_id 作为固定效应（控制病例难度），
学生 id 作为随机截距。
"""
from __future__ import annotations

import pandas as pd
import numpy as np

from evaluate.build_dataset import Dataset
from evaluate.config import Settings

import statsmodels.api as sm
import statsmodels.formula.api as smf

TITLE = "Multivariable models — adjusting for case and student"


def _fit_lmm(df: pd.DataFrame, dep: str, *, group_col="group_label", case_col="case_id", subject="user_id"):
    sub = df.dropna(subset=[dep, group_col, subject]).copy()
    if sub[group_col].nunique() < 2 or len(sub) < 8:
        return {"note": f"样本不足或组别不足 (n={len(sub)})"}
    sub[group_col] = sub[group_col].astype("category")
    sub[case_col] = sub[case_col].astype("category")
    formula = f"{dep} ~ C({group_col}, Treatment(reference='SA')) + C({case_col})"
    try:
        m = smf.mixedlm(formula, sub, groups=sub[subject]).fit(reml=False, method="lbfgs")
    except Exception as e:
        return {"note": f"拟合失败：{e}"}
    coefs = m.summary().tables[1]
    return {
        "n_obs": int(len(sub)),
        "n_groups": int(sub[subject].nunique()),
        "aic": float(m.aic) if m.aic is not None else None,
        "bic": float(m.bic) if m.bic is not None else None,
        "loglike": float(m.llf),
        "fixed_effects": coefs.to_html(classes="dataframe"),
        "fixed_effects_text": coefs.to_string(),
        "fixed_effects_df": _coef_df(m),
    }


def _coef_df(m) -> pd.DataFrame:
    df = pd.DataFrame({
        "coef": m.params,
        "std_err": m.bse,
        "z": m.tvalues,
        "p": m.pvalues,
    })
    try:
        ci = m.conf_int()
        df["ci_low"] = ci[0]
        df["ci_high"] = ci[1]
    except Exception:
        pass
    return df.reset_index().rename(columns={"index": "term"})


def _fit_logit(df: pd.DataFrame, dep: str, *, group_col="group_label", case_col="case_id"):
    sub = df.dropna(subset=[dep, group_col]).copy()
    if sub[group_col].nunique() < 2 or len(sub) < 8:
        return {"note": f"样本不足或组别不足 (n={len(sub)})"}
    sub[dep] = pd.to_numeric(sub[dep], errors="coerce")
    sub = sub.dropna(subset=[dep])
    if sub[dep].nunique() < 2:
        return {"note": f"因变量缺乏方差 (n={len(sub)})"}
    sub[group_col] = sub[group_col].astype("category")
    sub[case_col] = sub[case_col].astype("category")
    formula = f"{dep} ~ C({group_col}, Treatment(reference='SA')) + C({case_col})"
    try:
        m = smf.glm(formula, data=sub, family=sm.families.Binomial()).fit()
    except Exception as e:
        return {"note": f"拟合失败：{e}"}
    return {
        "n_obs": int(len(sub)),
        "aic": float(m.aic),
        "deviance": float(m.deviance),
        "fixed_effects_text": m.summary().tables[1].as_text(),
        "fixed_effects_df": _coef_df(m),
        "odds_ratio_df": _odds_ratio_df(m),
    }


def _odds_ratio_df(m) -> pd.DataFrame:
    or_ = pd.DataFrame({"OR": np.exp(m.params)})
    try:
        ci = np.exp(m.conf_int())
        or_["OR_ci_low"] = ci[0]
        or_["OR_ci_high"] = ci[1]
    except Exception:
        pass
    or_["p"] = m.pvalues
    return or_.reset_index().rename(columns={"index": "term"})


def analyze(ds: Dataset, settings: Settings) -> dict:
    out: dict = {"title": TITLE, "models": {}}

    # === 1) 学习阶段重复测量：以 session_index 与 group 双因素 ===
    L = ds.learning.copy()
    if not L.empty:
        L = L[L["method"].isin(("multi_agent", "single_agent", "control"))]
        L = L.dropna(subset=["session_index"])
        L["session_index"] = L["session_index"].astype(int)
        L["group_label"] = L["method"].map({
            "multi_agent": "MA", "single_agent": "SA", "control": "CT"
        })
        for dep in ("duration_seconds", "n_student_msgs", "weighted_score_pct",
                    "completion_rate", "items_checked"):
            if dep not in L.columns:
                continue
            sub = L.dropna(subset=[dep])
            if len(sub) < 12:
                out["models"][f"learning::{dep}"] = {"note": f"样本不足 n={len(sub)}"}
                continue
            sub[dep] = pd.to_numeric(sub[dep], errors="coerce")
            sub = sub.dropna(subset=[dep])
            sub["group_label"] = sub["group_label"].astype("category")
            sub["case_id"] = sub["case_id"].astype("category")
            formula = (
                f"{dep} ~ C(group_label, Treatment(reference='SA'))"
                f" * C(session_index)"
                f" + C(case_id)"
            )
            try:
                m = smf.mixedlm(formula, sub, groups=sub["user_id"]).fit(reml=False, method="lbfgs")
                out["models"][f"learning::{dep}"] = {
                    "formula": formula,
                    "n_obs": int(len(sub)),
                    "n_subjects": int(sub["user_id"].nunique()),
                    "aic": float(m.aic) if m.aic is not None else None,
                    "loglike": float(m.llf),
                    "fixed_effects_text": m.summary().tables[1].as_text(),
                    "fixed_effects_df": _coef_df(m),
                }
            except Exception as e:
                out["models"][f"learning::{dep}"] = {"note": f"拟合失败：{e}"}

    # === 2) 考试阶段：每学生 1 次考试，固定效应回归即可 ===
    E = ds.exams.copy()
    if not E.empty:
        E = E[E["group"].isin(("multi_agent", "single_agent", "control"))]
        E["group_label"] = E["group_label"].fillna(E["group"])
        for dep in ("osce_total", "weighted_score_pct", "final_score",
                    "osce_history_completeness", "osce_communication",
                    "osce_clinical_reasoning", "osce_diagnostic_accuracy"):
            if dep not in E.columns:
                continue
            sub = E.dropna(subset=[dep, "group_label"]).copy()
            if len(sub) < 6 or sub["group_label"].nunique() < 2:
                out["models"][f"exam::{dep}"] = {"note": f"样本不足 n={len(sub)}"}
                continue
            sub[dep] = pd.to_numeric(sub[dep], errors="coerce")
            sub = sub.dropna(subset=[dep])
            sub["group_label"] = sub["group_label"].astype("category")
            sub["case_id"] = sub["case_id"].astype("category")
            formula = f"{dep} ~ C(group_label, Treatment(reference='SA')) + C(case_id)"
            try:
                m = smf.ols(formula, data=sub).fit()
                out["models"][f"exam::{dep}"] = {
                    "formula": formula,
                    "n_obs": int(len(sub)),
                    "r2": float(m.rsquared),
                    "r2_adj": float(m.rsquared_adj),
                    "f_p": float(m.f_pvalue),
                    "fixed_effects_text": m.summary().tables[1].as_text(),
                    "fixed_effects_df": _coef_df(m),
                }
            except Exception as e:
                out["models"][f"exam::{dep}"] = {"note": f"拟合失败：{e}"}

        # 二元结局：诊断正误
        if "diagnosis_correct" in E.columns:
            res = _fit_logit(E, "diagnosis_correct")
            out["models"]["exam::diagnosis_correct (logit)"] = res

    return out
