from app.agents.base import call_qwen, parse_json_response
from app.evaluation.checklist import load_rubrics


EVALUATOR_SYSTEM_PROMPT = """你是一位资深的 OSCE（客观结构化临床考试）评分专家。你的任务是分析医学生与标准化病人(SP)之间的每一轮问答交换，判断该轮交换覆盖了评分量表中的哪些项目。

## 评分量表项目
{checklist_items}

## 核心评分原则

### 1. 评估的是「问答对」，不只是学生的话
- 学生提问 + 病人回答 = 一个完整信息交换
- 如果学生问了"哪里疼"，病人回答了"右下腹"，则同时触发"主要症状"和"Location 部位"
- 学生的问题决定方向，病人的回答确认信息已被采集

### 2. 一轮交换可以触发多个项目
- "你好我是XX医生，请问哪里不舒服？"→ 同时触发"自我介绍"+"主要症状"+"开放式提问使用"
- "除了疼，还有没有恶心、呕吐、发烧？"→ 可能同时触发"恶心呕吐"和"发热"
- 不要吝啬，只要合理就应该打勾

### 3. 关注信息采集意图，不要求精确措辞
- 学生不需要说出checklist的原话
- "疼了多久了"→ "Duration 持续时间" ✓
- "怎么疼的"→ "Character 性质" ✓
- "痛不痛得厉害，1到10分打几分"→ "Severity 严重程度" ✓
- "以前有没有得过什么病"→ "慢性病史" + "既往类似发作" ✓

### 4. 沟通技巧的识别要宽松
- "自我介绍": 任何形式的自报身份（"我是XX"、"你好我姓X"）
- "开放式提问使用": "能说说吗"、"怎么了"、"感觉怎样"等不限定答案的问法
- "共情表达": "别担心"、"我理解"、"一定很难受吧"、"没事的"等
- "总结确认": "所以你是说…"、"让我确认一下…"、"也就是…对吗"

### 5. 回顾上下文，但只输出新触发的项目
- 上下文帮你理解对话走向，但只返回本轮新触发的
- 已触发列表中的项目绝不重复

## 输出格式（严格JSON）
{{
    "checked_items": ["项目名1", "项目名2", ...],
    "reasoning": "简要说明触发理由"
}}"""


def _build_checklist_items_text() -> str:
    rubrics = load_rubrics()
    lines = []
    for cat_key, cat_data in rubrics["history_taking_checklist"].items():
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
    """
    Evaluate a student-patient exchange pair against the checklist.
    Sees both the student's question AND the SP's response to judge
    what information was actually elicited.
    """
    checklist_items_text = _build_checklist_items_text()
    system_prompt = EVALUATOR_SYSTEM_PROMPT.format(checklist_items=checklist_items_text)

    already_text = ", ".join(already_checked) if already_checked else "无"

    recent = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
    context_lines = []
    for m in recent[:-2]:
        role_label = "医学生" if m["role"] == "student" else "病人" if m["role"] == "patient" else "导师"
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
