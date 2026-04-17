"""复算 SUS / UES / Checklist 评分。
不依赖 backend，把 YAML 复制读取，便于离线运行。"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import yaml

_BACKEND_SURVEYS = Path(__file__).resolve().parent.parent / "backend" / "app" / "surveys"
_BACKEND_RUBRICS = Path(__file__).resolve().parent.parent / "backend" / "app" / "evaluation"


@lru_cache
def load_survey(instrument: str) -> dict:
    f = _BACKEND_SURVEYS / f"{instrument}.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8"))


@lru_cache
def load_rubrics() -> dict:
    f = _BACKEND_RUBRICS / "rubrics.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8"))


@lru_cache
def load_holistic_rubric() -> dict:
    f = _BACKEND_RUBRICS / "holistic_rubric.yaml"
    return yaml.safe_load(f.read_text(encoding="utf-8"))


# ----------------------------------------------------------------- SUS
def sus_item_ids() -> list[str]:
    return [it["id"] for it in load_survey("sus")["items"]]


def compute_sus(responses: dict) -> dict[str, Any]:
    spec = load_survey("sus")
    items = spec["items"]
    contributions = []
    answered = 0
    per_item: dict[str, int] = {}
    for it in items:
        raw = responses.get(it["id"])
        try:
            v = int(raw)
        except (TypeError, ValueError):
            continue
        if not 1 <= v <= 5:
            continue
        per_item[it["id"]] = v
        contrib = (5 - v) if it.get("reverse") else (v - 1)
        contributions.append(contrib)
        answered += 1
    out: dict[str, Any] = {
        "answered": answered,
        "total_items": len(items),
        "per_item": per_item,
        "complete": answered == len(items),
    }
    if out["complete"]:
        out["sus_score"] = sum(contributions) * 2.5
    else:
        out["sus_score"] = None
    return out


# ----------------------------------------------------------------- UES
def ues_item_ids() -> list[str]:
    return [it["id"] for it in load_survey("ues")["items"]]


def ues_subscale_map() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"fa": [], "pu": [], "ae": [], "rw": []}
    for it in load_survey("ues")["items"]:
        sub = it.get("subscale")
        if sub in out:
            out[sub].append(it["id"])
    return out


def compute_ues(responses: dict) -> dict[str, Any]:
    spec = load_survey("ues")
    items = spec["items"]
    per_item: dict[str, int] = {}
    coded_by_sub: dict[str, list[float]] = {"fa": [], "pu": [], "ae": [], "rw": []}
    for it in items:
        raw = responses.get(it["id"])
        try:
            v = int(raw)
        except (TypeError, ValueError):
            continue
        if not 1 <= v <= 5:
            continue
        per_item[it["id"]] = v
        coded = float(6 - v) if it.get("reverse") else float(v)
        sub = it.get("subscale")
        if sub in coded_by_sub:
            coded_by_sub[sub].append(coded)
    answered = len(per_item)
    complete = answered == len(items)
    out: dict[str, Any] = {
        "answered": answered,
        "total_items": len(items),
        "per_item": per_item,
        "complete": complete,
    }
    if complete:
        means = {k: (sum(v) / len(v)) for k, v in coded_by_sub.items() if v}
        out.update({
            "fa_mean": means.get("fa"),
            "pu_mean": means.get("pu"),
            "ae_mean": means.get("ae"),
            "rw_mean": means.get("rw"),
            "ues_overall": sum(means.values()),
        })
    return out


def open_ended_ids() -> list[str]:
    return [it["id"] for it in load_survey("open_ended")["items"]]


# ----------------------------------------------------------------- Checklist
def checklist_item_names() -> list[str]:
    """按 rubrics.yaml 顺序返回所有条目名。"""
    out: list[str] = []
    for cat in load_rubrics()["history_taking_checklist"].values():
        for it in cat["items"]:
            out.append(it["item"])
    return out


def checklist_item_meta() -> dict[str, dict]:
    """item_name → {category, weight, critical}"""
    out: dict[str, dict] = {}
    for cat_key, cat in load_rubrics()["history_taking_checklist"].items():
        for it in cat["items"]:
            out[it["item"]] = {
                "category": cat_key,
                "category_display": cat["display_name"],
                "weight": it["weight"],
                "critical": it.get("critical", False),
            }
    return out


def flatten_checklist_json(checklist_json: dict | None) -> dict[str, int]:
    """把 training_sessions.checklist_json（嵌套结构）拍平成 {item: 0/1}"""
    flags = {n: 0 for n in checklist_item_names()}
    if not checklist_json:
        return flags
    for cat in checklist_json.values():
        if not isinstance(cat, dict) or "items" not in cat:
            continue
        for name, st in cat["items"].items():
            if name in flags and isinstance(st, dict) and st.get("checked"):
                flags[name] = 1
    return flags


def flatten_final_checklist(checklist_results_json: dict | None) -> dict[str, int]:
    """final_evaluations.checklist_results_json 已是 {item: bool}。"""
    flags = {n: 0 for n in checklist_item_names()}
    if not checklist_results_json:
        return flags
    for name, v in checklist_results_json.items():
        if name in flags and v:
            flags[name] = 1
    return flags


def checklist_score(flags: dict[str, int]) -> dict[str, float]:
    """加权得分 + 完成率 + 漏掉的 critical 项数。"""
    meta = checklist_item_meta()
    total_weight = 0
    earned_weight = 0
    total = 0
    checked = 0
    missed_critical = 0
    for name, m in meta.items():
        total_weight += m["weight"]
        total += 1
        if flags.get(name):
            earned_weight += m["weight"]
            checked += 1
        elif m["critical"]:
            missed_critical += 1
    return {
        "weighted_score_pct": round(100 * earned_weight / total_weight, 2) if total_weight else 0.0,
        "completion_rate": round(checked / total, 4) if total else 0.0,
        "items_checked": checked,
        "items_total": total,
        "missed_critical": missed_critical,
    }
