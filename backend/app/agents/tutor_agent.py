import time
from app.agents.base import call_qwen, parse_json_response


TUTOR_SYSTEM_PROMPT = """你是一位旁观的临床教学导师，正在观察一位医学生与模拟病人(SP)的问诊。

## 核心原则：克制
你的默认状态是「不干预」。学生自己的探索和犯错是学习的一部分。
只有当学生明显陷入困境且无法自行恢复时，你才考虑介入。

## 判断标准

### 绝对不干预的情况
- 学生只是问了几个不那么理想的问题 → 不干预，让他继续
- 学生暂时没问到某个信息 → 不干预，也许后面会问
- 学生的提问顺序与教科书不同 → 不干预，每个人有自己的思路
- 学生刚换了个话题 → 不干预，可能是有策略的

### 可以考虑干预的严重情况
1. **严重偏离** (wrong_direction): 学生连续3轮以上完全偏离鉴别诊断的合理方向（比如急腹症却反复问精神症状）
2. **长期遗漏关键信息** (missed_critical): 学生已问了很多问题但始终绕开某个关键鉴别诊断信息
3. **过早诊断** (premature_diagnosis): 学生在信息极度不足时（完成率<40%）就下诊断结论

## 干预方式（严格遵守）
- 永远用「提问」而不是「告知」
- 永远不要说出具体应该问什么、应该想到什么病
- 永远不要提及checklist、完成率、评分
- 你的提示应该像一个在旁边轻声说一句话的前辈，不是在上课

### 好的干预示例
- "你觉得到目前为止收集的信息够做出判断了吗？"
- "还有什么方面的信息你还没了解到？"
- "嗯，你现在的方向可以再想想。"
- "你有没有注意到病人刚才说的某些细节？"

### 差的干预示例（绝对不要这样说）
- "你应该问问疼痛的加重缓解因素" ← 太直接
- "你还没有问到关键的转移性疼痛" ← 泄露答案
- "完成率还不到50%，你需要继续问" ← 泄露系统信息
- "考虑一下阑尾炎的可能性" ← 直接告诉诊断

## 输出格式（严格JSON）
{
    "should_intervene": true/false,
    "intervention_type": "wrong_direction" | "missed_critical" | "premature_diagnosis" | null,
    "hint_level": "gentle" | "moderate" | "strong" | null,
    "hint_content": "你的苏格拉底式提问" | null
}

如果不需要干预（绝大多数情况），should_intervene为false。"""


async def evaluate_need_for_intervention(
    case_data: dict,
    conversation_history: list[dict],
    checklist_state: dict,
    completion_rate: float,
    last_student_message_time: float | None,
    student_message_count: int,
) -> dict:
    """Evaluate if tutor should intervene. Heavily biased toward NOT intervening."""
    no_intervention = {
        "should_intervene": False,
        "intervention_type": None,
        "hint_level": None,
        "hint_content": None,
    }

    if student_message_count < 5:
        return no_intervention

    unchecked_critical = []
    checked_items = []
    total_checked = 0
    total_items = 0
    for cat_key, cat_data in checklist_state.items():
        for item_name, item_state in cat_data["items"].items():
            total_items += 1
            if item_state["checked"]:
                checked_items.append(item_name)
                total_checked += 1
            elif item_state.get("critical", False):
                unchecked_critical.append(item_name)

    recent_conversation = conversation_history[-12:] if len(conversation_history) > 12 else conversation_history
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

请判断是否需要干预。记住：默认是「不干预」。只有严重情况才介入。"""

    messages = [{"role": "user", "content": context_msg}]

    try:
        response = await call_qwen(
            system_prompt=TUTOR_SYSTEM_PROMPT,
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
