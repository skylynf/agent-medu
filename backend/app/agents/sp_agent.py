import re

from app.agents.base import call_qwen
from app.prompts import PromptRegistry


def _build_info_summary(case_data: dict) -> str:
    """Build the information layer rules block for the SP prompt."""
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
    template = PromptRegistry.get("sp_agent")
    return template.format(
        name=profile["name"],
        age=profile["age"],
        gender=profile["gender"],
        occupation=profile["occupation"],
        personality=profile["personality"],
        appearance=profile.get("appearance", "普通"),
        pathophysiology=case_data["pathophysiology"],
        info_summary=info_summary,
        emotion_state=emotion_state,
        emo_empathetic=emo["if_doctor_empathetic"],
        emo_cold=emo["if_doctor_cold"],
        emo_rushing=emo["if_doctor_rushing"],
    )


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
        if msg.get("role") == "tutor":
            continue  # tutor 提示不应进入 SP 上下文
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
