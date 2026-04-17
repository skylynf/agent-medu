import re
import yaml
from app.agents.base import call_qwen


def _build_info_summary(case_data: dict) -> str:
    """Build the information layer rules for the SP prompt."""
    layers = case_data["information_layers"]

    voluntary_text = "\n".join(f"  - {v}" for v in layers["voluntary"])

    on_inquiry_text = ""
    for item in layers["on_inquiry"]:
        on_inquiry_text += (
            f"  - 当医生问到关键词 [{item['trigger']}] 时，回答: \"{item['response']}\"\n"
        )

    deep_text = ""
    for item in layers["deep_inquiry"]:
        deep_text += (
            f"  - 当医生深入追问 [{item['trigger']}] 时，回答: \"{item['response']}\"\n"
        )

    return f"""### 主动信息（开场白可用）
{voluntary_text}

### 问到才说的信息
{on_inquiry_text}
### 深入追问才说的信息
{deep_text}"""


def build_sp_system_prompt(case_data: dict, current_emotion: str = "baseline") -> str:
    profile = case_data["patient_profile"]
    emo = case_data["emotional_model"]
    emotion_state = emo.get(f"if_doctor_{current_emotion}", emo["baseline"])
    if current_emotion == "baseline":
        emotion_state = emo["baseline"]

    info_summary = _build_info_summary(case_data)

    return f"""你是一个标准化病人(SP)，正在接受医学生的问诊训练。你需要高度真实地扮演这个角色。

## 你的角色
- 姓名: {profile['name']}
- 年龄: {profile['age']}岁
- 性别: {profile['gender']}
- 职业: {profile['occupation']}
- 性格特点: {profile['personality']}
- 外观: {profile.get('appearance', '普通')}

## 病理生理学背景（你不需要知道这些医学知识，但这决定了你的症状）
{case_data['pathophysiology']}

## 信息分层规则（必须严格遵守）
{info_summary}

## 核心规则
1. 开场时只说"主动信息"层的内容
2. "问到才说"的信息，只有当医生的问题涉及相应关键词/话题时才回答
3. "深入追问"的信息，只有当医生非常具体地追问时才回答
4. 绝对不能主动透露未被问到的医学信息
5. 用口语化、符合患者身份的语言回答，不使用医学术语
6. 每次回答控制在1-3句话
7. 可以有"嗯"、"啊"、"那个"等口语词让对话更真实
8. 如果医生问了你信息层中没有的问题，可以合理发挥但不能编造关键症状

## 当前情绪状态: {emotion_state}
根据这个情绪状态调整你的语气和回答详细程度。

## 情绪响应规则
- 如果医生表现出关心、共情: {emo['if_doctor_empathetic']}
- 如果医生态度冷漠: {emo['if_doctor_cold']}
- 如果医生催促急躁: {emo['if_doctor_rushing']}"""


def detect_emotion_shift(message: str) -> str:
    """Detect doctor's attitude from their message to adjust SP emotion."""
    empathetic_patterns = [
        r"别[担着]心", r"没事", r"放松", r"慢慢说", r"理解",
        r"辛苦", r"不要紧张", r"我[会来]帮", r"别怕",
    ]
    cold_patterns = [
        r"快[说点]", r"简单说", r"直接[说回]答", r"下一个",
    ]
    rushing_patterns = [
        r"赶紧", r"快[点些]", r"抓紧", r"还有别的吗就这些",
    ]

    for p in empathetic_patterns:
        if re.search(p, message):
            return "empathetic"
    for p in cold_patterns:
        if re.search(p, message):
            return "cold"
    for p in rushing_patterns:
        if re.search(p, message):
            return "rushing"
    return "baseline"


async def generate_sp_response(
    case_data: dict,
    conversation_history: list[dict],
    current_emotion: str = "baseline",
) -> tuple[str, str]:
    """
    Generate SP response.
    Returns: (response_text, updated_emotion)
    """
    if conversation_history:
        last_msg = conversation_history[-1].get("content", "")
        new_emotion = detect_emotion_shift(last_msg)
        if new_emotion != "baseline":
            current_emotion = new_emotion

    system_prompt = build_sp_system_prompt(case_data, current_emotion)

    messages = []
    for msg in conversation_history:
        role = "user" if msg["role"] == "student" else "assistant"
        messages.append({"role": role, "content": msg["content"]})

    if not messages:
        voluntary = case_data["information_layers"]["voluntary"]
        return "，".join(voluntary), current_emotion

    response = await call_qwen(
        system_prompt=system_prompt,
        messages=messages,
        temperature=0.8,
    )

    return response, current_emotion
