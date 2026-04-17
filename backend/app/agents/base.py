import json
import dashscope
from dashscope import Generation
from app.config import get_settings

settings = get_settings()
dashscope.api_key = settings.DASHSCOPE_API_KEY


async def call_qwen(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.7,
    response_format: str | None = None,
) -> str:
    """Call Qwen model via DashScope API."""
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    kwargs = {
        "model": settings.QWEN_MODEL,
        "messages": full_messages,
        "temperature": temperature,
        "result_format": "message",
    }

    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    response = Generation.call(**kwargs)

    if response.status_code != 200:
        raise RuntimeError(
            f"Qwen API error: {response.code} - {response.message}"
        )

    return response.output.choices[0].message.content


def parse_json_response(text: str) -> dict:
    """Extract JSON from LLM response, handling markdown code fences."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)
