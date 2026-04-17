"""会话策略包：MultiAgent / Exam / Control 三种学习方法的运行时实现。"""

from app.sessions.base import SessionStrategy
from app.sessions.multi_agent import MultiAgentSession
from app.sessions.single_agent import SingleAgentSession
from app.sessions.exam import ExamSession
from app.sessions.control import ControlSession, build_ct_stages

__all__ = [
    "SessionStrategy",
    "MultiAgentSession",
    "SingleAgentSession",
    "ExamSession",
    "ControlSession",
    "build_ct_stages",
    "create_strategy",
]


def create_strategy(method: str, **kwargs) -> SessionStrategy:
    """根据 method 字符串构造对应策略。未知 method 默认按 multi_agent 处理。"""
    method = (method or "multi_agent").lower()
    if method == "exam":
        return ExamSession(**kwargs)
    if method == "single_agent":
        return SingleAgentSession(**kwargs)
    if method == "control":
        # ControlSession 通过 REST 调用，不会走 WS create_strategy 路径，
        # 这里仍然提供以便统一接口。
        return ControlSession(**kwargs)
    return MultiAgentSession(**kwargs)
