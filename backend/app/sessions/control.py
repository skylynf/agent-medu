"""ControlSession：对照组（渐进式披露 / Progressive Disclosure）模式。

设计要点
--------
- 4 个固定阶段，全部从现有病例 YAML 自动推导：
  1. 接诊：人口学 + voluntary 主诉
  2. 系统询问结果：合并渲染 on_inquiry 的 trigger→response
  3. 深入追问结果：合并渲染 deep_inquiry 的 trigger→response
  4. 答案揭示（只读）：disease + key_differentials + pathophysiology
- 阶段 1-3 要求学生书面填写下一步问诊提问 / 鉴别 / 最终诊断推断；阶段 4 只读。
- 所有持久化都通过 `CTStep` 行实现；没有 LLM 调用。
- 本类不通过 WS 互动，REST 处理函数会直接调用本模块的 `build_ct_stages` 与
  `submit_stage` 静态方法。`SessionStrategy` 抽象方法保留极简实现以便统一接口。
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ct_step import CTStep
from app.models.session import TrainingSession
from app.sessions.base import SendFn, SessionStrategy

CT_PROMPTS = [
    "请写下你接下来想问病人的 5 个问题。",
    "结合上一阶段的回答，写出你目前考虑的鉴别诊断方向，以及还想继续追问的 3 个细节。",
    "基于全部信息，写出你最可能的主诊断、关键依据，以及下一步处置建议。",
    None,  # 阶段 4 只读
]

CT_STAGE_TITLES = [
    "阶段 1 · 接诊：主诉与基本情况",
    "阶段 2 · 系统询问结果",
    "阶段 3 · 深入追问结果",
    "阶段 4 · 答案揭示与教学要点",
]


def _render_voluntary(case_data: dict) -> str:
    voluntary = case_data["information_layers"].get("voluntary", [])
    profile = case_data.get("patient_profile", {})
    header = (
        f"患者：{profile.get('name', '')}，"
        f"{profile.get('gender', '')}，{profile.get('age', '')}岁，"
        f"{profile.get('occupation', '')}\n"
        f"外观：{profile.get('appearance', '')}\n\n"
    )
    body = "病人主动陈述：\n- " + "\n- ".join(voluntary)
    return header + body


def _render_layer(layer: list[dict], heading: str) -> str:
    if not layer:
        return f"（无{heading}内容）"
    lines = [f"## {heading}"]
    for item in layer:
        trigger = item.get("trigger", "")
        response = item.get("response", "")
        # trigger 是医生方向；response 是病人回答
        lines.append(f"- 当问到「{trigger}」时，病人答：{response}")
    return "\n".join(lines)


def _render_reveal(case_data: dict) -> str:
    disease = case_data.get("disease", "未提供")
    expected = case_data.get("expected_diagnosis", disease)
    key_diff = case_data.get("key_differentials", [])
    diff_text = "\n".join(f"- {d}" for d in key_diff) if key_diff else "（未列出）"
    patho = case_data.get("pathophysiology", "").strip()
    return (
        f"## 答案揭示\n"
        f"主诊断：{expected}\n"
        f"疾病：{disease}\n\n"
        f"## 重要鉴别诊断\n{diff_text}\n\n"
        f"## 病理生理学要点\n{patho}"
    )


def build_ct_stages(case_data: dict) -> list[dict]:
    """把现有 case YAML 自动切成 4 个 CT 阶段，无需修改病例文件。"""
    layers = case_data["information_layers"]
    return [
        {
            "stage_index": 0,
            "title": CT_STAGE_TITLES[0],
            "disclosed_content": _render_voluntary(case_data),
            "prompt_to_student": CT_PROMPTS[0],
            "requires_input": True,
        },
        {
            "stage_index": 1,
            "title": CT_STAGE_TITLES[1],
            "disclosed_content": _render_layer(layers.get("on_inquiry", []), "病人对常规询问的回答"),
            "prompt_to_student": CT_PROMPTS[1],
            "requires_input": True,
        },
        {
            "stage_index": 2,
            "title": CT_STAGE_TITLES[2],
            "disclosed_content": _render_layer(layers.get("deep_inquiry", []), "病人对深入追问的回答"),
            "prompt_to_student": CT_PROMPTS[2],
            "requires_input": True,
        },
        {
            "stage_index": 3,
            "title": CT_STAGE_TITLES[3],
            "disclosed_content": _render_reveal(case_data),
            "prompt_to_student": CT_PROMPTS[3],
            "requires_input": False,
        },
    ]


class ControlSession(SessionStrategy):
    METHOD = "control"
    PROMPT_KEYS = ()  # 对照组不调用 LLM

    def __init__(self, session_id: uuid.UUID, case_id: str, user_id: uuid.UUID):
        super().__init__(session_id, case_id, user_id)
        self.stages = build_ct_stages(self.case_data)

    @property
    def total_stages(self) -> int:
        return len(self.stages)

    def stage_payload(self, index: int) -> dict:
        if index < 0 or index >= len(self.stages):
            raise IndexError(f"stage index {index} out of range")
        s = self.stages[index]
        return {
            "stage_index": s["stage_index"],
            "title": s["title"],
            "disclosed_content": s["disclosed_content"],
            "prompt_to_student": s["prompt_to_student"],
            "requires_input": s["requires_input"],
            "total_stages": self.total_stages,
            "is_final": index == self.total_stages - 1,
        }

    async def current_stage_index(self, db: AsyncSession) -> int:
        result = await db.execute(
            select(CTStep).where(CTStep.session_id == self.session_id)
        )
        rows = result.scalars().all()
        return len(rows)

    async def submit_stage(
        self, db: AsyncSession, stage_index: int, student_input: str
    ) -> dict:
        if stage_index < 0 or stage_index >= len(self.stages):
            raise IndexError(f"stage index {stage_index} out of range")
        stage = self.stages[stage_index]

        await self._save_prompt_versions(db)

        # 防重复提交：相同 stage_index 已存在则覆盖 student_input
        existing = await db.execute(
            select(CTStep).where(
                CTStep.session_id == self.session_id,
                CTStep.stage_index == stage_index,
            )
        )
        existing_row = existing.scalar_one_or_none()
        if existing_row is None:
            db.add(
                CTStep(
                    session_id=self.session_id,
                    stage_index=stage_index,
                    stage_title=stage["title"],
                    disclosed_content=stage["disclosed_content"],
                    prompt_to_student=stage["prompt_to_student"],
                    student_input=student_input or "",
                )
            )
        else:
            existing_row.student_input = student_input or ""

        # 更新 session 元数据
        session = await db.get(TrainingSession, self.session_id)
        if session is not None:
            session.student_messages = max(session.student_messages or 0, stage_index + 1)
            session.total_messages = stage_index + 1

        await db.flush()

        next_index = stage_index + 1
        if next_index >= self.total_stages:
            return {"completed": True, "next_stage": None}
        return {"completed": False, "next_stage": self.stage_payload(next_index)}

    # ----------------------------------------------------- abstract overrides
    async def get_opening(self) -> dict:
        return {"type": "ct_stage", **self.stage_payload(0)}

    async def process_student_message(
        self, content: str, db: AsyncSession, send_fn: SendFn = None
    ) -> list[dict]:
        raise RuntimeError("ControlSession 不通过 WebSocket 处理消息，请使用 REST /api/sessions/control/* 接口")

    async def end_session(self, db: AsyncSession) -> dict:
        # 标记完成；不计算 score（CT 模式无系统反馈）
        from datetime import datetime, timezone

        session = await db.get(TrainingSession, self.session_id)
        if session is not None and session.ended_at is None:
            session.ended_at = datetime.now(timezone.utc)
            await db.flush()

        steps_result = await db.execute(
            select(CTStep)
            .where(CTStep.session_id == self.session_id)
            .order_by(CTStep.stage_index)
        )
        steps = steps_result.scalars().all()

        return {
            "type": "session_summary",
            "method": self.METHOD,
            "session_id": str(self.session_id),
            "case_id": self.case_id,
            "total_stages": self.total_stages,
            "completed_stages": len(steps),
            "stages": [
                {
                    "stage_index": s.stage_index,
                    "title": s.stage_title,
                    "student_input": s.student_input,
                }
                for s in steps
            ],
        }
