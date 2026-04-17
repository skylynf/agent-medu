from fastapi import APIRouter

router = APIRouter(prefix="/api/methods", tags=["methods"])


METHODS = [
    {
        "id": "multi_agent",
        "name": "多智能体学习 (MA)",
        "short": "MA",
        "description": "完整的三智能体协作：AI-SP 模拟病人，旁观导师在你陷入困境时给出苏格拉底式提问，隐形评估器实时为 OSCE 量表打勾。",
        "interactive": True,
        "uses_ws": True,
        "shows_evaluation": True,
        "shows_tutor": True,
        "needs_case": True,
    },
    {
        "id": "single_agent",
        "name": "单智能体学习 (SA)",
        "short": "SA",
        "description": "只与 AI-SP 自由对话，没有导师提示也没有任何评分反馈。用于研究「无脚手架的纯对话练习」与多智能体方法的对照。",
        "interactive": True,
        "uses_ws": True,
        "shows_evaluation": False,
        "shows_tutor": False,
        "needs_case": True,
    },
    {
        "id": "control",
        "name": "对照学习 (CT)",
        "short": "CT",
        "description": "渐进式披露：4 个固定阶段，每个阶段先阅读病人当前可知信息，再写下你接下来想问的问题或鉴别诊断思路。无系统反馈，仅在最末展示参考答案。",
        "interactive": False,
        "uses_ws": False,
        "shows_evaluation": False,
        "shows_tutor": False,
        "needs_case": True,
    },
    {
        "id": "exam",
        "name": "考试方法 (Exam)",
        "short": "Exam",
        "description": "只与 AI-SP 自由对话，不显示评分与导师提示。结束时由总评 agent 一次性给出 checklist 命中、4 维 OSCE 评分、诊断正误与定性反馈。",
        "interactive": True,
        "uses_ws": True,
        "shows_evaluation": False,
        "shows_tutor": False,
        "needs_case": True,
    },
    {
        "id": "post_test",
        "name": "后测问卷",
        "short": "PostTest",
        "description": "包含系统可用性量表 (SUS) 与开放性问题，研究结束时填写。",
        "interactive": False,
        "uses_ws": False,
        "shows_evaluation": False,
        "shows_tutor": False,
        "needs_case": False,
    },
]


@router.get("")
async def list_methods():
    return METHODS
