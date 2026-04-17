from app.agents.base import call_qwen, parse_json_response
from app.prompts import PromptRegistry


async def evaluate_need_for_intervention(
    case_data: dict,
    conversation_history: list[dict],
    checklist_state: dict,
    completion_rate: float,
    last_student_message_time: float | None,
    student_message_count: int,
) -> dict:
    """Evaluate if tutor should intervene. """
    no_intervention = {
        "should_intervene": False,
        "intervention_type": None,
        "hint_level": None,
        "hint_content": None,
    }

    if student_message_count < 3:
        return no_intervention

    unchecked_critical = []
    total_checked = 0
    total_items = 0
    for cat_data in checklist_state.values():
        for item_name, item_state in cat_data["items"].items():
            total_items += 1
            if item_state["checked"]:
                total_checked += 1
            elif item_state.get("critical", False):
                unchecked_critical.append(item_name)

    recent_conversation = (
        conversation_history[-12:]
        if len(conversation_history) > 12
        else conversation_history
    )
    conv_text = "\n".join(
        f"{'医学生' if m['role'] == 'student' else '病人' if m['role'] == 'patient' else '导师'}: {m['content']}"
        for m in recent_conversation
    )

    context_msg = f"""## 对话记录（最近）
{conv_text}

## 统计信息（仅供你判断参考，不要在提示中提及）
已覆盖信息数: {total_checked}/{total_items}
完成率: {completion_rate:.0%}
学生已提问次数: {student_message_count}
尚未被问到的关键信息数: {len(unchecked_critical)}

请判断是否需要干预。记住：默认是「不干预」。"""

    messages = [{"role": "user", "content": context_msg}]
    system_prompt = PromptRegistry.get("tutor_agent")

    try:
        response = await call_qwen(
            system_prompt=system_prompt,
            messages=messages,
            temperature=0.3,
            response_format="json",
        )
        result = parse_json_response(response)
        if not isinstance(result.get("should_intervene"), bool):
            result["should_intervene"] = False
        return result
    except Exception:
        return no_intervention
