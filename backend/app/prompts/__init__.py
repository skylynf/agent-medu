"""Prompt 库：YAML 默认值 + DB 版本覆盖。

设计要点
--------
- 进程启动时 (`PromptRegistry.load_yaml_defaults`) 把 YAML 默认 prompt 装进进程内缓存。
- 紧接着调用 `PromptRegistry.seed_db_from_yaml(db)`：若某个 key 在 DB 中没有 active 行，则把
  YAML 的 v1 写入 `prompts` 表并标记 active；已有 active 行则保持不动。
- `PromptRegistry.reload_from_db(db)` 把 DB 的 active 模板覆写回缓存（管理员改 prompt
  之后调用，下一次推理立即生效）。
- 业务代码统一通过 `PromptRegistry.get(key)` / `get_version(key)` 同步取值，避免每次
  推理都查 DB。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt import Prompt

PROMPTS_DIR = Path(__file__).parent
KNOWN_KEYS = ("sp_agent", "tutor_agent", "turn_evaluator", "final_evaluator")


class PromptRegistry:
    _templates: dict[str, str] = {}
    _versions: dict[str, str] = {}
    _notes: dict[str, str] = {}
    _loaded: bool = False

    # ------------------------------------------------------------------ load
    @classmethod
    def load_yaml_defaults(cls) -> None:
        cls._templates.clear()
        cls._versions.clear()
        cls._notes.clear()
        for f in sorted(PROMPTS_DIR.glob("*.yaml")):
            with open(f, "r", encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            key = data.get("key")
            template = data.get("template")
            if not key or template is None:
                continue
            cls._templates[key] = template
            cls._versions[key] = str(data.get("version", "v1"))
            cls._notes[key] = data.get("notes", "") or ""
        cls._loaded = True

    @classmethod
    async def seed_db_from_yaml(cls, db: AsyncSession) -> None:
        """同步 YAML 默认值到 DB:

        - DB 中没有任何 active 行 → 插入 YAML 版本为 active；
        - DB 中存在 active 行，但 version 与 YAML 中不一致 → 视为代码侧
          升级了 prompt（例如 v1 → v2），将旧 active 置为 false，并插入
          YAML 新版本作为新 active；
        - 版本一致 → 不动（即使内容不同也尊重管理员可能的人工编辑）。
        """
        if not cls._loaded:
            cls.load_yaml_defaults()
        for key, template in cls._templates.items():
            existing = await db.execute(
                select(Prompt).where(Prompt.key == key, Prompt.active.is_(True))
            )
            current = existing.scalar_one_or_none()
            yaml_version = cls._versions[key]
            if current is None:
                db.add(
                    Prompt(
                        key=key,
                        version=yaml_version,
                        template=template,
                        notes=cls._notes.get(key) or "seeded from YAML",
                        active=True,
                    )
                )
                continue
            if current.version != yaml_version:
                current.active = False
                db.add(
                    Prompt(
                        key=key,
                        version=yaml_version,
                        template=template,
                        notes=cls._notes.get(key) or f"auto-upgraded from {current.version}",
                        active=True,
                    )
                )
        await db.commit()

    @classmethod
    async def reload_from_db(cls, db: AsyncSession) -> None:
        """把 DB 中所有 active 行同步回内存缓存。"""
        if not cls._loaded:
            cls.load_yaml_defaults()
        result = await db.execute(select(Prompt).where(Prompt.active.is_(True)))
        for p in result.scalars().all():
            cls._templates[p.key] = p.template
            cls._versions[p.key] = p.version

    # ------------------------------------------------------------------ read
    @classmethod
    def get(cls, key: str) -> str:
        if not cls._loaded:
            cls.load_yaml_defaults()
        if key not in cls._templates:
            raise KeyError(f"Unknown prompt key: {key!r}. Known: {list(cls._templates)}")
        return cls._templates[key]

    @classmethod
    def get_version(cls, key: str) -> str:
        if not cls._loaded:
            cls.load_yaml_defaults()
        return cls._versions.get(key, "v1")

    @classmethod
    def all_versions(cls) -> dict[str, str]:
        if not cls._loaded:
            cls.load_yaml_defaults()
        return dict(cls._versions)

    @classmethod
    def known_keys(cls) -> Iterable[str]:
        return KNOWN_KEYS
