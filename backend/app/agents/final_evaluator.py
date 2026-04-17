"""考试方法 (ExamSession) 结束时的一次性整体评估 agent。

输出严格 JSON：checklist 命中情况 + 4 维 OSCE rubric (1-5) + 诊断准确性 + 叙述反馈。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.agents.base import call_qwen, parse_json_response
from app.evaluation.checklist import load_rubrics
from app.prompts import PromptRegistry

HOLISTIC_RUBRIC_PATH = Path(__file__).parents[1] / "evaluation" / "holistic_rubric.yaml"


def _load_holistic_rubric() -> list[dict]:
    with open(HOLISTIC_RUBRIC_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("holistic_rubric", [])


def _render_checklist_items() -> str:
    rubrics = load_rubrics()
    lines: list[str] = []
    for cat_data in rubrics["history_taking_checklist"].values():
        lines.append(f"\n### {cat_data['display_name']}")
        for item in cat_data["items"]:
            mark = " [关键项]" if item.get("critical") else ""
            lines.append(f"  - {item['item']}{mark} (权重: {item['weight']})")
    return "\n".join(lines)


def _render_holistic_rubric() -> str:
    rubric = _load_holistic_rubric()
    blocks: list[str] = []
    for dim in rubric:
        anchors = dim.get("anchors", {})
        anchor_lines = "\n".join(
            f"    - {score} 分: {desc}" for score, desc in anchors.items()
        )
        blocks.append(
            f"### {dim['display_name']} ({dim['dimension']})\n"
            f"  描述: {dim.get('description', '').strip()}\n"
            f"  评分锚点:\n{anchor_lines}"
        )
    return "\n\n".join(blocks)


_WORKSHEET_LABELS: dict[str, str] = {
    "chief_complaint": "主诉概括",
    "hpi": "现病史汇总",
    "past_history": "既往史 / 个人史 / 家族史",
    "physical_exam": "体格检查重点",
    "differentials": "鉴别诊断",
    "diagnosis": "最可能诊断",
    "diagnostic_reasoning": "诊断依据 / 推理过程",
    "investigations": "下一步检查",
    "management": "处置 / 治疗计划",
}


def _render_worksheet(worksheet: dict | None) -> str:
    if not worksheet or not isinstance(worksheet, dict):
        return "（学生未填写任何临床表单内容）"
    blocks: list[str] = []
    for key, label in _WORKSHEET_LABELS.items():
        v = worksheet.get(key)
        if not v:
            continue
        if not isinstance(v, str):
            v = str(v)
        v = v.strip()
        if not v:
            continue
        blocks.append(f"### {label}\n{v}")
    if not blocks:
        return "（学生未填写任何临床表单内容）"
    return "\n\n".join(blocks)


def _render_transcript(conversation_history: list[dict]) -> str:
    lines: list[str] = []
    for m in conversation_history:
        role = m.get("role")
        content = m.get("content", "")
        if role == "student":
            label = "医学生"
        elif role == "patient":
            label = "病人"
        elif role == "tutor":
            label = "导师"
        else:
            label = role or "未知"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


def _all_checklist_item_names() -> list[str]:
    rubrics = load_rubrics()
    names: list[str] = []
    for cat_data in rubrics["history_taking_checklist"].values():
        for item in cat_data["items"]:
            names.append(item["item"])
    return names


def _normalize_result(result: dict) -> dict:
    """把 LLM 输出对齐到稳定 schema。缺字段用合理默认。"""
    item_names = _all_checklist_item_names()
    raw_checked = result.get("checklist_results") or {}
    if not isinstance(raw_checked, dict):
        raw_checked = {}
    checklist_results = {name: bool(raw_checked.get(name, False)) for name in item_names}

    raw_scores = result.get("holistic_scores") or {}
    if not isinstance(raw_scores, dict):
        raw_scores = {}
    holistic_scores: dict[str, int] = {}
    for dim in ("history_completeness", "communication", "clinical_reasoning", "diagnostic_accuracy"):
        try:
            v = int(raw_scores.get(dim, 0))
        except (TypeError, ValueError):
            v = 0
        holistic_scores[dim] = max(0, min(5, v))

    diagnosis_given = result.get("diagnosis_given")
    if isinstance(diagnosis_given, str):
        diagnosis_given = diagnosis_given.strip() or None
    elif diagnosis_given is not None:
        diagnosis_given = str(diagnosis_given)

    diagnosis_correct = bool(result.get("diagnosis_correct", False))

    differentials = result.get("differentials_given") or []
    if not isinstance(differentials, list):
        differentials = []
    differentials = [str(x) for x in differentials if x]

    strengths = result.get("strengths") or []
    if not isinstance(strengths, list):
        strengths = []
    strengths = [str(x) for x in strengths if x]

    improvements = result.get("improvements") or []
    if not isinstance(improvements, list):
        improvements = []
    improvements = [str(x) for x in improvements if x]

    narrative = result.get("narrative_feedback") or ""
    if not isinstance(narrative, str):
        narrative = str(narrative)

    return {
        "checklist_results": checklist_results,
        "holistic_scores": holistic_scores,
        "diagnosis_given": diagnosis_given,
        "diagnosis_correct": diagnosis_correct,
        "differentials_given": differentials,
        "strengths": strengths,
        "improvements": improvements,
        "narrative_feedback": narrative,
    }


def _empty_result_with_error(reason: str) -> dict:
    return {
        "checklist_results": {name: False for name in _all_checklist_item_names()},
        "holistic_scores": {
            "history_completeness": 0,
            "communication": 0,
            "clinical_reasoning": 0,
            "diagnostic_accuracy": 0,
        },
        "diagnosis_given": None,
        "diagnosis_correct": False,
        "differentials_given": [],
        "strengths": [],
        "improvements": [],
        "narrative_feedback": f"自动评分失败: {reason}",
    }


async def evaluate_exam(
    case_data: dict,
    conversation_history: list[dict],
    worksheet: dict | None = None,
) -> tuple[dict, str]:
    """对一次完整的考试问诊做一次性整评。

    `worksheet` 为学生在问诊期间填写的临床表单（鉴别诊断 / 处置等）。它直接进入
    评估提示词，是判定「临床推理」与「诊断准确性」两个维度的主要依据。

    Returns: (normalized_result_dict, raw_llm_text)
    """
    expected_diagnosis = case_data.get("expected_diagnosis", "未提供")
    key_diff = case_data.get("key_differentials", [])
    if isinstance(key_diff, list):
        key_diff_text = ", ".join(str(x) for x in key_diff) or "未提供"
    else:
        key_diff_text = str(key_diff)

    template = PromptRegistry.get("final_evaluator")
    system_prompt = template.format(
        checklist_items=_render_checklist_items(),
        holistic_rubric=_render_holistic_rubric(),
        expected_diagnosis=expected_diagnosis,
        key_differentials=key_diff_text,
        transcript=_render_transcript(conversation_history),
        worksheet=_render_worksheet(worksheet),
    )

    user_msg = "请按系统提示词中的输出格式严格输出 JSON，不要任何额外文字。"

    try:
        raw = await call_qwen(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
            temperature=0.2,
            response_format="json",
        )
    except Exception as exc:
        return _empty_result_with_error(f"LLM 调用失败: {exc}"), ""

    try:
        parsed = parse_json_response(raw)
    except Exception as exc:
        return _empty_result_with_error(f"JSON 解析失败: {exc}"), raw

    return _normalize_result(parsed), raw
