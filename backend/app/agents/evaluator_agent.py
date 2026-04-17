from app.agents.base import call_qwen, parse_json_response
from app.evaluation.checklist import load_rubrics
from app.prompts import PromptRegistry


def _build_checklist_items_text() -> str:
    rubrics = load_rubrics()
    lines = []
    for cat_data in rubrics["history_taking_checklist"].values():
        lines.append(f"\n### {cat_data['display_name']}")
        for item in cat_data["items"]:
            critical_mark = " [关键项]" if item.get("critical") else ""
            lines.append(f"  - {item['item']}{critical_mark} (权重: {item['weight']})")
    return "\n".join(lines)


async def evaluate_exchange(
    student_message: str,
    patient_response: str,
    conversation_history: list[dict],
    already_checked: list[str],
) -> dict:
    """Evaluate a student-patient exchange pair against the checklist."""
    checklist_items_text = _build_checklist_items_text()
    system_prompt = PromptRegistry.get("turn_evaluator").format(
        checklist_items=checklist_items_text
    )

    already_text = ", ".join(already_checked) if already_checked else "无"

    recent = (
        conversation_history[-8:]
        if len(conversation_history) > 8
        else conversation_history
    )
    context_lines = []
    for m in recent[:-2]:
        role_label = (
            "医学生" if m["role"] == "student"
            else "病人" if m["role"] == "patient"
            else "导师"
        )
        context_lines.append(f"{role_label}: {m['content']}")
    context_text = "\n".join(context_lines) if context_lines else "（对话刚开始）"

    user_msg = f"""## 已触发的项目（不要重复）
{already_text}

## 之前的对话上下文
{context_text}

## 本轮问答交换（需要评估的）
医学生: {student_message}
病人回答: {patient_response}

请分析这轮问答交换覆盖了哪些新的checklist项目。记住：一轮交换可以触发多个项目。"""

    messages = [{"role": "user", "content": user_msg}]

    try:
        response = await call_qwen(
            system_prompt=system_prompt,
            messages=messages,
            temperature=0.1,
            response_format="json",
        )
        result = parse_json_response(response)
        checked = result.get("checked_items", [])
        if not isinstance(checked, list):
            checked = []
        result["checked_items"] = [
            item for item in checked
            if isinstance(item, str) and item not in already_checked
        ]
        return result
    except Exception:
        return {"checked_items": [], "reasoning": "evaluation failed"}
