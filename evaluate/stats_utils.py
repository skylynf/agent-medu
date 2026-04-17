"""统计工具：描述、正态性、组间比较、效应量、CI、多重校正。

设计成纯函数 + 返回 dict / DataFrame，便于打印与落表。
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

# scipy 在数据范围为 0 / 完全相同时会发噪音 warning，不会影响结果，统一静默
warnings.filterwarnings("ignore", category=RuntimeWarning, module=r"scipy\..*")
warnings.filterwarnings("ignore", category=UserWarning, module=r"scipy\..*")

try:
    import scikit_posthocs as sp
except ImportError:  # pragma: no cover
    sp = None


# ============================================================ 描述统计
def describe_continuous(values: Sequence[float]) -> dict[str, float | int | None]:
    arr = pd.to_numeric(pd.Series(values), errors="coerce").dropna().to_numpy()
    n = int(arr.size)
    if n == 0:
        return dict(n=0, mean=None, sd=None, median=None, q1=None, q3=None,
                    min=None, max=None, ci_low=None, ci_high=None, sem=None, iqr=None)
    mean = float(arr.mean())
    sd = float(arr.std(ddof=1)) if n > 1 else 0.0
    sem = sd / math.sqrt(n) if n > 1 else 0.0
    if n > 1:
        ci = stats.t.interval(0.95, df=n - 1, loc=mean, scale=sem)
    else:
        ci = (mean, mean)
    q1, med, q3 = np.percentile(arr, [25, 50, 75])
    return dict(
        n=n,
        mean=round(mean, 4),
        sd=round(sd, 4),
        sem=round(sem, 4),
        median=round(float(med), 4),
        q1=round(float(q1), 4),
        q3=round(float(q3), 4),
        iqr=round(float(q3 - q1), 4),
        min=round(float(arr.min()), 4),
        max=round(float(arr.max()), 4),
        ci_low=round(float(ci[0]), 4),
        ci_high=round(float(ci[1]), 4),
    )


def describe_categorical(values: Sequence) -> pd.DataFrame:
    s = pd.Series(values).dropna()
    if s.empty:
        return pd.DataFrame(columns=["category", "n", "pct"])
    counts = s.value_counts(dropna=False)
    pct = (counts / counts.sum() * 100).round(2)
    return pd.DataFrame({"category": counts.index.astype(str), "n": counts.values, "pct": pct.values})


def proportion_ci(n_success: int, n_total: int) -> tuple[float, float]:
    """Wilson 95% 区间。"""
    if n_total == 0:
        return (0.0, 0.0)
    z = 1.959963984540054
    p = n_success / n_total
    denom = 1 + z * z / n_total
    centre = (p + z * z / (2 * n_total)) / denom
    half = z * math.sqrt((p * (1 - p) + z * z / (4 * n_total)) / n_total) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# ============================================================ 正态性 / 方差齐性
def normality_test(values: Sequence[float]) -> dict[str, float | None | bool]:
    arr = pd.to_numeric(pd.Series(values), errors="coerce").dropna().to_numpy()
    n = int(arr.size)
    if n < 3:
        return dict(test="shapiro", n=n, statistic=None, p=None, normal=None, note="n<3")
    # 范围为 0（常量）→ 视作"正态"以避免散播警告并不破坏后续逻辑
    if float(np.ptp(arr)) == 0.0:
        return dict(test="shapiro", n=n, statistic=None, p=None, normal=True, note="zero variance")
    if n > 5000:
        # 大样本退化为 D'Agostino's K^2
        st, p = stats.normaltest(arr)
        return dict(test="dagostino", n=n, statistic=float(st), p=float(p), normal=p > 0.05, note=None)
    st, p = stats.shapiro(arr)
    return dict(test="shapiro", n=n, statistic=float(st), p=float(p), normal=p > 0.05, note=None)


def variance_homogeneity(*groups: Sequence[float]) -> dict[str, float | None | bool]:
    cleaned = [pd.to_numeric(pd.Series(g), errors="coerce").dropna().to_numpy() for g in groups]
    cleaned = [g for g in cleaned if g.size >= 2]
    if len(cleaned) < 2:
        return dict(test="levene", statistic=None, p=None, equal_var=None, note="<2 groups with n>=2")
    st, p = stats.levene(*cleaned, center="median")
    return dict(test="levene", statistic=float(st), p=float(p), equal_var=p > 0.05, note=None)


# ============================================================ 组间比较（连续）
def compare_continuous_groups(
    groups: Mapping[str, Sequence[float]],
    *,
    paired: bool = False,
) -> dict:
    """对 ≥2 组连续变量做组间比较：自动选 t / Welch / Mann-Whitney / ANOVA / Kruskal-Wallis。
    返回 omnibus 与 posthoc。"""
    groups = {k: pd.to_numeric(pd.Series(v), errors="coerce").dropna().to_numpy() for k, v in groups.items()}
    groups = {k: v for k, v in groups.items() if v.size >= 1}
    keys = list(groups.keys())
    out: dict = {"groups": {k: describe_continuous(v) for k, v in groups.items()}}

    if len(keys) < 2:
        out["omnibus"] = {"test": None, "p": None, "note": "<2 groups"}
        out["posthoc"] = []
        return out

    normal_flags = []
    for k in keys:
        n = normality_test(groups[k])
        normal_flags.append(bool(n.get("normal")))
    all_normal = all(normal_flags)
    var_h = variance_homogeneity(*[groups[k] for k in keys])
    equal_var = bool(var_h.get("equal_var"))

    if len(keys) == 2:
        a, b = groups[keys[0]], groups[keys[1]]
        if paired and a.size == b.size:
            if all_normal:
                st, p = stats.ttest_rel(a, b)
                test = "paired_t"
            else:
                try:
                    st, p = stats.wilcoxon(a, b)
                    test = "wilcoxon"
                except ValueError:
                    st, p = (None, None)
                    test = "wilcoxon_failed"
        else:
            if all_normal:
                st, p = stats.ttest_ind(a, b, equal_var=equal_var)
                test = "students_t" if equal_var else "welch_t"
            else:
                st, p = stats.mannwhitneyu(a, b, alternative="two-sided")
                test = "mann_whitney_u"
        eff = effect_size_two(a, b, paired=paired, parametric=all_normal)
        out["omnibus"] = {
            "test": test,
            "statistic": float(st) if st is not None else None,
            "p": float(p) if p is not None else None,
            "all_normal": all_normal,
            "equal_var": equal_var,
        }
        out["effect_size"] = eff
        out["posthoc"] = []
        return out

    # ≥3 组
    if all_normal and equal_var:
        st, p = stats.f_oneway(*[groups[k] for k in keys])
        test = "anova"
        eff = eta_squared_oneway([groups[k] for k in keys])
    elif all_normal and not equal_var:
        # Welch ANOVA：手动实现（statsmodels 没现成简洁版）
        st, p = welch_anova([groups[k] for k in keys])
        test = "welch_anova"
        eff = eta_squared_oneway([groups[k] for k in keys])
    else:
        st, p = stats.kruskal(*[groups[k] for k in keys])
        test = "kruskal_wallis"
        eff = epsilon_squared_kw([groups[k] for k in keys], st)

    out["omnibus"] = {
        "test": test,
        "statistic": float(st) if st is not None else None,
        "p": float(p) if p is not None else None,
        "all_normal": all_normal,
        "equal_var": equal_var,
    }
    out["effect_size_omnibus"] = eff

    # posthoc
    posthoc = []
    for a_key, b_key in combinations(keys, 2):
        a, b = groups[a_key], groups[b_key]
        if test in ("anova", "welch_t", "students_t", "welch_anova"):
            s, pval = stats.ttest_ind(a, b, equal_var=(test == "anova"))
            sub = "tukey_t" if test == "anova" else "welch_t_pair"
        else:
            try:
                s, pval = stats.mannwhitneyu(a, b, alternative="two-sided")
                sub = "mann_whitney_pair"
            except ValueError:
                s, pval = (None, None)
                sub = "mann_whitney_pair_failed"
        eff = effect_size_two(a, b, paired=False, parametric=all_normal)
        posthoc.append({
            "group_a": a_key, "group_b": b_key, "test": sub,
            "statistic": float(s) if s is not None else None,
            "p_raw": float(pval) if pval is not None else None,
            **{f"effect_{k}": v for k, v in eff.items()},
        })

    if posthoc:
        ps = [r["p_raw"] for r in posthoc if r["p_raw"] is not None]
        if ps:
            _, padj_holm, _, _ = multipletests(ps, method="holm")
            _, padj_bh, _, _ = multipletests(ps, method="fdr_bh")
            j = 0
            for row in posthoc:
                if row["p_raw"] is not None:
                    row["p_holm"] = float(padj_holm[j])
                    row["p_fdr_bh"] = float(padj_bh[j])
                    j += 1

    out["posthoc"] = posthoc
    return out


# ============================================================ 效应量
def cohens_d(a: np.ndarray, b: np.ndarray, *, paired: bool = False) -> float | None:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if a.size < 2 or b.size < 2:
        return None
    if paired and a.size == b.size:
        diff = a - b
        sd = diff.std(ddof=1)
        if sd == 0:
            return 0.0
        return float(diff.mean() / sd)
    n1, n2 = a.size, b.size
    s1, s2 = a.var(ddof=1), b.var(ddof=1)
    pooled = math.sqrt(((n1 - 1) * s1 + (n2 - 1) * s2) / (n1 + n2 - 2))
    if pooled == 0:
        return 0.0
    return float((a.mean() - b.mean()) / pooled)


def hedges_g(a: np.ndarray, b: np.ndarray) -> float | None:
    d = cohens_d(a, b)
    if d is None:
        return None
    n = len(a) + len(b)
    j = 1 - (3 / (4 * n - 9))
    return float(d * j)


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float | None:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if a.size == 0 or b.size == 0:
        return None
    # O(n*m) implementation；对几百样本足够
    gt = 0
    lt = 0
    for x in a:
        gt += int((b < x).sum())
        lt += int((b > x).sum())
    return float((gt - lt) / (a.size * b.size))


def rank_biserial_u(a: np.ndarray, b: np.ndarray) -> float | None:
    """Mann-Whitney U 的效应量（等价于 2 * AUC - 1，或 Cliff's delta）。"""
    return cliffs_delta(a, b)


def effect_size_two(a, b, *, paired=False, parametric=True) -> dict[str, float | None]:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return {
        "mean_diff": float(np.nanmean(a) - np.nanmean(b)) if a.size and b.size else None,
        "cohens_d": cohens_d(a, b, paired=paired),
        "hedges_g": hedges_g(a, b),
        "cliffs_delta": cliffs_delta(a, b),
    }


def eta_squared_oneway(groups: Sequence[Sequence[float]]) -> dict:
    arrays = [np.asarray(g, dtype=float) for g in groups]
    arrays = [a[~np.isnan(a)] for a in arrays]
    grand = np.concatenate(arrays)
    if grand.size == 0:
        return {"eta_squared": None, "omega_squared": None}
    grand_mean = grand.mean()
    ss_between = sum(len(a) * (a.mean() - grand_mean) ** 2 for a in arrays if a.size)
    ss_within = sum(((a - a.mean()) ** 2).sum() for a in arrays if a.size)
    ss_total = ss_between + ss_within
    eta = ss_between / ss_total if ss_total else None
    df_between = len(arrays) - 1
    df_within = grand.size - len(arrays)
    ms_within = ss_within / df_within if df_within else None
    omega = ((ss_between - df_between * ms_within) / (ss_total + ms_within)) if ms_within else None
    return {"eta_squared": float(eta) if eta is not None else None,
            "omega_squared": float(omega) if omega is not None else None}


def epsilon_squared_kw(groups: Sequence[Sequence[float]], h_stat: float) -> dict:
    n = sum(len(g) for g in groups)
    if n < 2:
        return {"epsilon_squared": None}
    return {"epsilon_squared": float(h_stat / ((n ** 2 - 1) / (n + 1)))}


def welch_anova(groups: Sequence[Sequence[float]]) -> tuple[float, float]:
    """Welch ANOVA。返回 (F, p)。某组方差为 0 时 fall back 到普通 1-way ANOVA。"""
    arrays = [np.asarray(g, dtype=float) for g in groups]
    arrays = [a[~np.isnan(a)] for a in arrays]
    arrays = [a for a in arrays if a.size >= 2]
    k = len(arrays)
    if k < 2:
        return (float("nan"), float("nan"))
    ns = np.array([a.size for a in arrays], dtype=float)
    means = np.array([a.mean() for a in arrays])
    vars_ = np.array([a.var(ddof=1) for a in arrays])
    if np.any(vars_ == 0):
        try:
            F, p = stats.f_oneway(*arrays)
            return float(F), float(p)
        except Exception:
            return (float("nan"), float("nan"))
    w = ns / vars_
    grand = (w * means).sum() / w.sum()
    numerator = (w * (means - grand) ** 2).sum() / (k - 1)
    tmp = ((1 - w / w.sum()) ** 2 / (ns - 1)).sum()
    if tmp == 0:
        return (float("nan"), float("nan"))
    denom_factor = 1 + (2 * (k - 2) / (k ** 2 - 1)) * tmp
    F = numerator / denom_factor
    df1 = k - 1
    df2 = (k ** 2 - 1) / (3 * tmp)
    p = 1 - stats.f.cdf(F, df1, df2)
    return float(F), float(p)


# ============================================================ 分类变量比较
def compare_categorical(table: pd.DataFrame) -> dict:
    """table: rows=group, cols=category, cells=count. 自动选 χ² 或 Fisher."""
    tbl = table.fillna(0).astype(int)
    out = {"table": tbl}
    if tbl.shape[0] < 2 or tbl.shape[1] < 2:
        out["test"] = None
        out["p"] = None
        out["note"] = "table degenerate"
        return out
    expected_min = stats.contingency.expected_freq(tbl.values).min()
    if tbl.shape == (2, 2) and expected_min < 5:
        odds, p = stats.fisher_exact(tbl.values)
        out["test"] = "fisher_exact"
        out["statistic"] = float(odds)
        out["p"] = float(p)
    else:
        chi2, p, dof, expected = stats.chi2_contingency(tbl.values)
        out["test"] = "chi_square"
        out["statistic"] = float(chi2)
        out["p"] = float(p)
        out["dof"] = int(dof)
        # Cramér's V
        n = tbl.values.sum()
        denom = n * (min(tbl.shape) - 1)
        out["cramers_v"] = float(math.sqrt(chi2 / denom)) if denom else None
    return out


# ============================================================ 信度
def cronbach_alpha(items_df: pd.DataFrame) -> dict:
    """items_df 列 = 题目，行 = 受测者；缺失行删除。"""
    df = items_df.apply(pd.to_numeric, errors="coerce").dropna(how="any")
    n_items = df.shape[1]
    n_resp = df.shape[0]
    if n_items < 2 or n_resp < 2:
        return {"alpha": None, "n_items": n_items, "n_respondents": n_resp, "note": "数据不足"}
    item_vars = df.var(axis=0, ddof=1)
    total_var = df.sum(axis=1).var(ddof=1)
    if total_var == 0:
        return {"alpha": None, "n_items": n_items, "n_respondents": n_resp, "note": "总分方差=0"}
    alpha = (n_items / (n_items - 1)) * (1 - item_vars.sum() / total_var)
    return {"alpha": float(alpha), "n_items": n_items, "n_respondents": n_resp,
            "interpretation": _alpha_interpretation(alpha)}


def _alpha_interpretation(alpha: float) -> str:
    if alpha >= 0.9: return "excellent"
    if alpha >= 0.8: return "good"
    if alpha >= 0.7: return "acceptable"
    if alpha >= 0.6: return "questionable"
    if alpha >= 0.5: return "poor"
    return "unacceptable"


# ============================================================ 多重校正
def multipletests_df(df: pd.DataFrame, p_col: str, methods=("holm", "fdr_bh")) -> pd.DataFrame:
    out = df.copy()
    if p_col not in out.columns:
        return out
    valid_mask = out[p_col].notna()
    valid_p = out.loc[valid_mask, p_col].astype(float).to_numpy()
    if valid_p.size == 0:
        return out
    for m in methods:
        _, padj, _, _ = multipletests(valid_p, method=m)
        col = f"{p_col}_{m}"
        out[col] = np.nan
        out.loc[valid_mask, col] = padj
    return out


# ============================================================ 相关
def correlation_table(df: pd.DataFrame, cols: Sequence[str], method="spearman") -> pd.DataFrame:
    sub = df[cols].apply(pd.to_numeric, errors="coerce")
    rows = []
    for a, b in combinations(cols, 2):
        x = sub[a].dropna()
        y = sub[b].dropna()
        joint = sub[[a, b]].dropna()
        if len(joint) < 3:
            rows.append({"var_a": a, "var_b": b, "n": len(joint), "method": method, "rho": None, "p": None})
            continue
        if method == "spearman":
            r, p = stats.spearmanr(joint[a], joint[b])
        else:
            r, p = stats.pearsonr(joint[a], joint[b])
        rows.append({"var_a": a, "var_b": b, "n": len(joint), "method": method,
                     "rho": float(r), "p": float(p)})
    out = pd.DataFrame(rows)
    if not out.empty and out["p"].notna().any():
        out = multipletests_df(out, "p")
    return out
