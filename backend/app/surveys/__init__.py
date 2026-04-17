"""问卷题目装载与 SUS 评分计算。"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

SURVEYS_DIR = Path(__file__).parent
KNOWN_INSTRUMENTS = ("sus", "open_ended")


@lru_cache
def load_instrument(instrument: str) -> dict:
    f = SURVEYS_DIR / f"{instrument}.yaml"
    if not f.exists():
        raise FileNotFoundError(f"Unknown survey instrument: {instrument}")
    with open(f, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def list_instruments() -> list[dict]:
    out = []
    for inst in KNOWN_INSTRUMENTS:
        out.append(load_instrument(inst))
    return out


def compute_sus_score(responses: dict) -> dict | None:
    """SUS 标准计算：奇数题 (score-1)，偶数题 (5-score)，求和×2.5，得 0-100 分。"""
    spec = load_instrument("sus")
    items = spec.get("items", [])
    total = 0
    answered = 0
    per_item: dict[str, int] = {}
    for item in items:
        qid = item["id"]
        raw = responses.get(qid)
        if raw is None:
            continue
        try:
            v = int(raw)
        except (TypeError, ValueError):
            continue
        if v < 1 or v > 5:
            continue
        per_item[qid] = v
        contribution = (5 - v) if item.get("reverse") else (v - 1)
        total += contribution
        answered += 1
    if answered < len(items):
        # 不足全题不出 SUS 总分（避免误导）
        return {
            "answered": answered,
            "total_items": len(items),
            "per_item": per_item,
            "sus_score": None,
            "complete": False,
        }
    return {
        "answered": answered,
        "total_items": len(items),
        "per_item": per_item,
        "sus_score": total * 2.5,
        "complete": True,
    }
