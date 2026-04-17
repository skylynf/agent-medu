"""Prompt 库管理接口（researcher/teacher 可访问）。

每次保存即插入新版本行；激活某一版本时把同 key 的旧 active 行置为 false。
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.models.prompt import Prompt
from app.models.user import User
from app.prompts import KNOWN_KEYS, PromptRegistry

router = APIRouter(prefix="/api/admin/prompts", tags=["admin_prompts"])


def _require_editor(user: User) -> None:
    if user.role not in ("teacher", "researcher"):
        raise HTTPException(status_code=403, detail="仅教师/研究员可管理 prompt")


class PromptCreate(BaseModel):
    key: str
    template: str
    notes: str | None = None
    activate: bool = True


@router.get("/keys")
async def list_keys(user: User = Depends(get_current_user)):
    _require_editor(user)
    return list(KNOWN_KEYS)


@router.get("")
async def list_prompts(
    key: str | None = None,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    stmt = select(Prompt).order_by(Prompt.created_at.desc())
    if key:
        stmt = stmt.where(Prompt.key == key)
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "key": r.key,
            "version": r.version,
            "active": r.active,
            "notes": r.notes,
            "template": r.template,
            "updated_by": str(r.updated_by) if r.updated_by else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


@router.get("/active")
async def list_active(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    result = await db.execute(select(Prompt).where(Prompt.active.is_(True)))
    rows = result.scalars().all()
    return [
        {
            "key": r.key,
            "version": r.version,
            "template": r.template,
            "id": str(r.id),
        }
        for r in rows
    ]


def _next_version(existing_versions: list[str]) -> str:
    """从 v1, v2, v3 ... 中取下一个；若旧版本不规则则按数量+1 命名为 v{n}。"""
    nums: list[int] = []
    for v in existing_versions:
        v = (v or "").strip().lstrip("v").lstrip("V")
        try:
            nums.append(int(v))
        except ValueError:
            continue
    next_num = max(nums) + 1 if nums else 1
    return f"v{next_num}"


@router.post("")
async def create_prompt(
    payload: PromptCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    if payload.key not in KNOWN_KEYS:
        raise HTTPException(status_code=400, detail=f"未知 prompt key: {payload.key}")

    existing = await db.execute(
        select(Prompt.version).where(Prompt.key == payload.key)
    )
    versions = [v for (v,) in existing.all()]
    new_version = _next_version(versions)

    if payload.activate:
        await db.execute(
            update(Prompt)
            .where(Prompt.key == payload.key, Prompt.active.is_(True))
            .values(active=False)
        )

    row = Prompt(
        key=payload.key,
        version=new_version,
        template=payload.template,
        notes=payload.notes,
        active=payload.activate,
        updated_by=user.id,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)

    if payload.activate:
        await PromptRegistry.reload_from_db(db)

    return {
        "id": str(row.id),
        "key": row.key,
        "version": row.version,
        "active": row.active,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/{prompt_id}/activate")
async def activate_prompt(
    prompt_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_editor(user)
    target = await db.get(Prompt, prompt_id)
    if not target:
        raise HTTPException(status_code=404, detail="Prompt 不存在")

    await db.execute(
        update(Prompt)
        .where(Prompt.key == target.key, Prompt.active.is_(True))
        .values(active=False)
    )
    target.active = True
    await db.commit()
    await PromptRegistry.reload_from_db(db)
    return {
        "id": str(target.id),
        "key": target.key,
        "version": target.version,
        "active": True,
    }


@router.post("/reload")
async def reload_cache(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """强制把 DB 中所有 active 行重新读入内存缓存。"""
    _require_editor(user)
    await PromptRegistry.reload_from_db(db)
    return {"ok": True, "versions": PromptRegistry.all_versions()}
