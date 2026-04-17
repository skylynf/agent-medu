from fastapi import APIRouter
from app.cases import list_cases, load_case

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("")
async def get_cases():
    return list_cases()


@router.get("/{case_id}")
async def get_case_detail(case_id: str):
    """Return case info without revealing disease/diagnosis to student."""
    case = load_case(case_id)
    voluntary = case.get("information_layers", {}).get("voluntary", [])
    chief_complaint = voluntary[0] if voluntary else "患者前来就诊"
    return {
        "case_id": case["case_id"],
        "chief_complaint": chief_complaint,
        "difficulty": case.get("difficulty", 1),
        "patient_profile": {
            "name": case["patient_profile"]["name"],
            "age": case["patient_profile"]["age"],
            "gender": case["patient_profile"]["gender"],
            "occupation": case["patient_profile"]["occupation"],
            "appearance": case["patient_profile"].get("appearance", ""),
        },
    }
