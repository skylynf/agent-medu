import asyncio
import json
import logging

import dashscope
from dashscope import Generation

from app.config import get_settings

settings = get_settings()
dashscope.api_key = settings.DASHSCOPE_API_KEY

logger = logging.getLogger(__name__)

# DashScope SDK 是同步阻塞 API。直接在 async 函数里调用会冻结整个事件循环，
# 进而导致并发的 WebSocket 心跳 / 其他请求全部停滞，触发反向代理 idle timeout
# 并在客户端显示为「connection closed」。所以这里统一用 to_thread 把它丢到线程池。
LLM_CALL_TIMEOUT_SECONDS = 60.0
# 会话结束时 final_evaluator 单次整评（报告）体量较大，单独放宽上限
FINAL_EVALUATION_LLM_TIMEOUT_SECONDS = 120.0


def _sync_call(kwargs: dict):
    return Generation.call(**kwargs)


async def call_qwen(
    system_prompt: str,
    messages: list[dict],
    temperature: float = 0.7,
    response_format: str | None = None,
    timeout: float = LLM_CALL_TIMEOUT_SECONDS,
) -> str:
    """Call Qwen model via DashScope API in a worker thread, with timeout."""
    full_messages = [{"role": "system", "content": system_prompt}] + messages

    kwargs = {
        "model": settings.QWEN_MODEL,
        "messages": full_messages,
        "temperature": temperature,
        "result_format": "message",
    }

    if response_format == "json":
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(_sync_call, kwargs),
            timeout=timeout,
        )
    except asyncio.TimeoutError as exc:
        logger.warning("Qwen call timed out after %.1fs", timeout)
        raise RuntimeError(f"LLM 调用超时 (>{int(timeout)}s)，请稍后重试") from exc

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
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines)
    return json.loads(text)
