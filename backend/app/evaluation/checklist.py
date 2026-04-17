import yaml
from pathlib import Path
from functools import lru_cache

RUBRICS_PATH = Path(__file__).parent / "rubrics.yaml"


@lru_cache
def load_rubrics() -> dict:
    with open(RUBRICS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_empty_checklist() -> dict:
    """Create a fresh checklist with all items unchecked."""
    rubrics = load_rubrics()
    checklist = {}
    for category_key, category_data in rubrics["history_taking_checklist"].items():
        checklist[category_key] = {
            "display_name": category_data["display_name"],
            "items": {}
        }
        for item_def in category_data["items"]:
            checklist[category_key]["items"][item_def["item"]] = {
                "checked": False,
                "weight": item_def["weight"],
                "critical": item_def.get("critical", False),
            }
    return checklist


def compute_score(checklist: dict) -> tuple[float, float, list[str]]:
    """
    Compute score from checklist state.
    Returns: (weighted_score_percent, completion_rate, missed_critical_items)
    """
    total_weight = 0
    earned_weight = 0
    total_items = 0
    checked_items = 0
    missed_critical = []

    for category_key, category_data in checklist.items():
        for item_name, item_state in category_data["items"].items():
            w = item_state["weight"]
            total_weight += w
            total_items += 1
            if item_state["checked"]:
                earned_weight += w
                checked_items += 1
            elif item_state.get("critical", False):
                missed_critical.append(item_name)

    score = (earned_weight / total_weight * 100) if total_weight > 0 else 0
    completion_rate = (checked_items / total_items) if total_items > 0 else 0
    return round(score, 1), round(completion_rate, 3), missed_critical


def update_checklist(checklist: dict, items_to_check: list[str]) -> dict:
    """Mark specific items as checked and return the delta."""
    delta = {}
    for category_key, category_data in checklist.items():
        for item_name in category_data["items"]:
            if item_name in items_to_check and not category_data["items"][item_name]["checked"]:
                category_data["items"][item_name]["checked"] = True
                delta[item_name] = {
                    "category": category_key,
                    "weight": category_data["items"][item_name]["weight"],
                    "critical": category_data["items"][item_name].get("critical", False),
                }
    return delta
