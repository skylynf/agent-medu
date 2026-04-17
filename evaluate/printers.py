"""为各 analyses 模块写人类可读的命令行展示。"""
from __future__ import annotations

import pandas as pd

from evaluate import report as r


def print_cohort(res: dict) -> None:
    r.section(res["title"])
    r.kv(res["summary"], title="Overview")
    r.df(res["groups"], title="Group composition")
    r.df(res["pipeline_completeness"], title="Pipeline completeness per group")
    r.df(res["learning_by_case"], title="Learning sessions × case")
    r.df(res["exam_by_case"], title="Exam sessions × case")
    if res.get("flagged_students") is not None and len(res["flagged_students"]):
        r.df(res["flagged_students"], title="⚠ Flagged students (incomplete or mixed-method)")
    else:
        r.df(pd.DataFrame([{"status": "all clean"}]), title="No flagged students")


def print_demographics(res: dict) -> None:
    r.section(res["title"])
    if not res.get("categorical_tables"):
        r.df(pd.DataFrame([{"note": "无人口学字段"}]), title="N/A")
        return
    for var, tbl in res["categorical_tables"].items():
        r.df(tbl, title=f"Distribution — {var}")
        test = res["categorical_tests"].get(var, {})
        if test.get("test"):
            r.kv({k: test.get(k) for k in ("test", "statistic", "p", "dof", "cramers_v")},
                 title=f"Test — {var}")
    if res.get("continuous_descriptive"):
        for var, per_group in res["continuous_descriptive"].items():
            rows = [{"group": g, **d} for g, d in per_group.items()]
            r.df(pd.DataFrame(rows), title=f"{var} by group (descriptive)")


def _print_omnibus(name: str, test_res: dict) -> None:
    omn = test_res.get("omnibus", {})
    r.kv({"variable": name, **omn}, title=f"Omnibus — {name}")
    eff = test_res.get("effect_size") or test_res.get("effect_size_omnibus") or {}
    if eff:
        r.kv(eff, title=f"Effect size — {name}")
    posthoc = test_res.get("posthoc") or []
    if posthoc:
        r.df(pd.DataFrame(posthoc), title=f"Pairwise posthoc — {name}")


def print_continuous_block(descriptive: dict[str, pd.DataFrame], tests: dict[str, dict]) -> None:
    for var, desc_df in descriptive.items():
        r.df(desc_df, title=f"Descriptive — {var}")
        _print_omnibus(var, tests.get(var, {}))


def print_exam(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    r.kv({"n_exams": res["n_exams"]})
    print_continuous_block(res.get("continuous", {}), res.get("continuous_tests", {}))
    for var, blk in res.get("binary", {}).items():
        r.df(blk["descriptive"], title=f"Binary outcome — {var}")
        t = blk["test"]
        if isinstance(t, dict):
            tbl = t.pop("table", None)
            if tbl is not None:
                r.df(tbl.reset_index().rename(columns={"index": var}),
                     title=f"Contingency — {var}")
            r.kv({k: v for k, v in t.items() if k != "table"}, title=f"Test — {var}")


def print_learning_process(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    r.kv({
        "n_students_analyzed": res["n_students_analyzed"],
        "n_sessions_analyzed": res["n_sessions_analyzed"],
    })
    print_continuous_block(res.get("descriptive", {}), res.get("tests", {}))


def print_learning_gain(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    for v, per_method in res.get("within_paired", {}).items():
        r.section(f"Within-group session1 vs session2 — {v}", subtitle="paired t / Wilcoxon")
        for grp, info in per_method.items():
            if "note" in info:
                r.kv({"group": grp, **info})
                continue
            r.kv({"group": grp, "n": info["n"], "mean_delta": info["mean_delta"]},
                 title=f"{v} — {grp}")
            r.kv(info["test"], title=f"Test — {v} — {grp}")
            if info.get("effect"):
                r.kv(info["effect"], title=f"Effect size — {v} — {grp}")
    for v, between in res.get("between_delta", {}).items():
        r.section(f"Between-group Δ ({v})", subtitle="learning gain comparison")
        _print_omnibus(f"Δ {v}", between)


def print_checklist(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    r.df(res["descriptive"], title="Per-item coverage by group", max_rows=200)
    r.df(res["item_tests"], title="Per-item tests (Holm/BH adjusted)", max_rows=200)


def print_surveys(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    r.kv({"n_students": res["n_students"], **res.get("completion_rate", {})})
    print_continuous_block(res.get("descriptive", {}), res.get("tests", {}))
    for prefix, df_ in res.get("item_descriptive", {}).items():
        r.df(df_, title=f"{prefix.upper()} per-item × group means", max_rows=200)


def print_reliability(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    if "sus" in res:
        r.kv(res["sus"]["overall"], title="SUS Cronbach α (overall)")
        rows = [{"group": g, **v} for g, v in res["sus"]["by_group"].items()]
        r.df(pd.DataFrame(rows), title="SUS α by group")
    if "ues" in res:
        r.kv(res["ues"]["overall"], title="UES Cronbach α (overall)")
        rows = [{"subscale": k, **v} for k, v in res["ues"]["by_subscale"].items()]
        r.df(pd.DataFrame(rows), title="UES α by subscale")
        rows = [{"group": g, **v} for g, v in res["ues"]["overall_by_group"].items()]
        r.df(pd.DataFrame(rows), title="UES overall α by group")


def print_correlations(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    r.df(res["correlation_long"], title="Spearman correlations (Holm/BH-adjusted)", max_rows=300)


def print_mixed_models(res: dict) -> None:
    r.section(res["title"])
    if not res.get("models"):
        r.kv({"note": "无模型可拟合"})
        return
    for k, m in res["models"].items():
        r.section(f"Model: {k}")
        if "note" in m:
            r.kv({"note": m["note"]})
            continue
        meta = {kk: m.get(kk) for kk in ("formula", "n_obs", "n_subjects", "aic", "bic", "loglike",
                                         "r2", "r2_adj", "f_p", "deviance")
                if m.get(kk) is not None}
        if meta:
            r.kv(meta, title="Fit summary")
        if isinstance(m.get("fixed_effects_df"), pd.DataFrame):
            r.df(m["fixed_effects_df"], title="Fixed effects", max_rows=200)
        if isinstance(m.get("odds_ratio_df"), pd.DataFrame):
            r.df(m["odds_ratio_df"], title="Odds ratios", max_rows=200)


def print_dialogue(res: dict) -> None:
    r.section(res["title"])
    if "note" in res:
        r.kv({"note": res["note"]})
        return
    if "tutor_interventions" in res:
        r.kv(res["tutor_interventions"], title="Tutor interventions per MA session")
    if "student_msg_chars" in res:
        _print_omnibus("mean_student_msg_chars", res["student_msg_chars"])
    if "mean_latency_ms" in res:
        _print_omnibus("mean_latency_ms", res["mean_latency_ms"])


PRINTERS = {
    "cohort": print_cohort,
    "demographics": print_demographics,
    "exam": print_exam,
    "learning_process": print_learning_process,
    "learning_gain": print_learning_gain,
    "checklist_items": print_checklist,
    "surveys": print_surveys,
    "reliability": print_reliability,
    "correlations": print_correlations,
    "mixed_models": print_mixed_models,
    "dialogue": print_dialogue,
}
