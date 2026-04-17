import os
import yaml
from pathlib import Path
from functools import lru_cache

CASES_DIR = Path(__file__).parent


@lru_cache
def load_case(case_id: str) -> dict:
    filepath = CASES_DIR / f"{case_id}.yaml"
    if not filepath.exists():
        raise FileNotFoundError(f"Case '{case_id}' not found")
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def list_cases() -> list[dict]:
    """List cases with scenario info only — no disease/diagnosis revealed."""
    cases = []
    for f in sorted(CASES_DIR.glob("*.yaml")):
        with open(f, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
            voluntary = data.get("information_layers", {}).get("voluntary", [])
            chief_complaint = voluntary[0] if voluntary else "患者前来就诊"
            cases.append({
                "case_id": data["case_id"],
                "chief_complaint": chief_complaint,
                "difficulty": data.get("difficulty", 1),
                "patient_name": data["patient_profile"]["name"],
                "patient_age": data["patient_profile"]["age"],
                "patient_gender": data["patient_profile"]["gender"],
                "patient_occupation": data["patient_profile"].get("occupation", ""),
            })
    return cases
