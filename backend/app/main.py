import asyncio
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from sqlalchemy import text

# 尽早配置日志，确保 Railway deploy log 能看到所有启动信息
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
    force=True,
)

logger = logging.getLogger(__name__)

# 在导入业务模块之前先打印 Python/环境信息，方便定位 ImportError
logger.info("Python %s | PID %s | cwd=%s", sys.version, os.getpid(), os.getcwd())
logger.info("PORT env: %s", os.environ.get("PORT", "(not set, default 8000)"))

from app.config import get_settings
from app.database import engine, Base, async_session
from app.api import (
    auth,
    cases,
    sessions,
    analytics,
    methods,
    control,
    surveys,
    prompts,
    final_evaluations,
)
from app.models.user import User
from app.models.session import TrainingSession
from app.prompts import PromptRegistry
from app.sessions import (
    SessionStrategy,
    MultiAgentSession,
    ExamSession,
)

settings = get_settings()


def _safe_db_url(url: str) -> str:
    """把 URL 里的密码替换成 *** 用于日志输出。"""
    try:
        parsed = urlparse(url)
        if parsed.password:
            return url.replace(parsed.password, "***")
    except Exception:
        pass
    return url


# In-memory registry of active orchestrators (keyed by session_id)
active_sessions: dict[uuid.UUID, SessionStrategy] = {}


def _build_strategy(method: str, *, session_id, case_id, user_id) -> SessionStrategy:
    method = (method or "multi_agent").lower()
    if method == "exam":
        return ExamSession(session_id=session_id, case_id=case_id, user_id=user_id)
    return MultiAgentSession(session_id=session_id, case_id=case_id, user_id=user_id)


LIGHTWEIGHT_MIGRATIONS: list[tuple[str, str]] = [
    # (description, SQL)。所有语句都使用 IF NOT EXISTS / IF EXISTS，保证幂等。
    (
        "training_sessions.method",
        "ALTER TABLE training_sessions "
        "ADD COLUMN IF NOT EXISTS method VARCHAR(20) NOT NULL DEFAULT 'multi_agent'",
    ),
    (
        "training_sessions.method index",
        "CREATE INDEX IF NOT EXISTS ix_training_sessions_method "
        "ON training_sessions (method)",
    ),
    (
        "training_sessions.prompt_versions_json",
        "ALTER TABLE training_sessions "
        "ADD COLUMN IF NOT EXISTS prompt_versions_json JSONB",
    ),
]


async def _apply_lightweight_migrations() -> None:
    """对老库做最小幅度的列扩展。create_all 不会修改已有表结构，
    所以这里手动跑 ALTER TABLE，避免 'column does not exist' 报错。"""
    try:
        async with engine.begin() as conn:
            for desc, sql in LIGHTWEIGHT_MIGRATIONS:
                try:
                    await conn.execute(text(sql))
                    logger.info("Migration applied: %s", desc)
                except Exception as inner_exc:
                    # 单条失败不阻塞剩余迁移；只记日志
                    logger.warning(
                        "Migration step %s failed (continuing): %s", desc, inner_exc
                    )
    except Exception as exc:
        logger.exception("Lightweight migrations FAILED — %s: %s", type(exc).__name__, exc)


async def _create_db_schema() -> None:
    logger.info("DB schema init: connecting to %s", _safe_db_url(settings.DATABASE_URL))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB schema init: success")
    except Exception as exc:
        logger.exception("DB schema init FAILED — type=%s msg=%s", type(exc).__name__, exc)
        return

    # 给老库补齐新列；新库这些列已经在 create_all 里建好，ALTER 是 no-op
    await _apply_lightweight_migrations()

    # 装载 prompt 默认值并 seed 到 DB（仅当 DB 中尚无 active 行时）
    try:
        PromptRegistry.load_yaml_defaults()
        async with async_session() as db:
            await PromptRegistry.seed_db_from_yaml(db)
            await PromptRegistry.reload_from_db(db)
        logger.info("Prompt registry: seeded & reloaded (versions=%s)", PromptRegistry.all_versions())
    except Exception as exc:
        logger.exception("Prompt registry init FAILED — type=%s msg=%s", type(exc).__name__, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== SPAgent backend lifespan start ===")
    logger.info("DATABASE_URL : %s", _safe_db_url(settings.DATABASE_URL))
    logger.info("QWEN_MODEL   : %s", settings.QWEN_MODEL)
    logger.info("DASHSCOPE_KEY: %s", "SET" if settings.DASHSCOPE_API_KEY else "EMPTY — LLM calls will fail")
    logger.info("JWT_SECRET   : %s", "SET" if settings.JWT_SECRET not in ("change-me-in-production", "your-jwt-secret-change-me") else "DEFAULT (change in production)")

    # 提前装载 YAML（即使 DB seed 还没跑完，agent 也能用 YAML 默认值响应）
    try:
        PromptRegistry.load_yaml_defaults()
        logger.info("Prompt YAML defaults loaded: %s", list(PromptRegistry.all_versions()))
    except Exception:
        logger.exception("Prompt YAML defaults load failed at startup")

    # Fire-and-forget: schema init runs in the background so the app can
    # respond to healthchecks immediately without waiting for the DB.
    asyncio.create_task(_create_db_schema())
    try:
        logger.info("=== Medu-SPAgent backend ready, accepting requests ===")
        yield
    finally:
        logger.info("=== Medu-SPAgent backend shutting down ===")
        await engine.dispose()


app = FastAPI(
    title="Medu-SPAgent — Medical Education SP Agent",
    description="AI 标准化病人多智能体训练 / 对照学习 / 考试 / 后测 一体化研究平台",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(cases.router)
app.include_router(methods.router)
app.include_router(surveys.router)
app.include_router(prompts.router)
# 注意：control + final_evaluations 必须在 sessions.router 之前注册，否则
# `/api/sessions/{session_id}` 会先匹配 `control` 字符串导致 422。
app.include_router(control.router)
app.include_router(final_evaluations.router)
app.include_router(sessions.router)
app.include_router(analytics.router)


@app.get("/health")
async def health_check():
    """轻量健康检查：只确认进程存活，不等 DB。"""
    return {"status": "ok", "service": "Medu-SPAgent"}


@app.get("/health/detailed")
async def health_check_detailed():
    db_status = "unknown"
    db_error: str | None = None
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        db_status = "error"
        db_error = f"{type(exc).__name__}: {exc}"
        logger.warning("Detailed health check — DB ping failed: %s", exc)

    return {
        "status": "ok",
        "service": "Medu-SPAgent",
        "database": db_status,
        "database_url": _safe_db_url(settings.DATABASE_URL),
        "prompt_versions": PromptRegistry.all_versions(),
        **({"database_error": db_error} if db_error else {}),
    }


async def _authenticate_ws(token: str) -> User | None:
    """Authenticate a WebSocket connection via JWT token."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            return None
        async with async_session() as db:
            user = await db.get(User, uuid.UUID(user_id))
            return user
    except (JWTError, Exception):
        return None


@app.websocket("/ws/consultation")
async def websocket_consultation(websocket: WebSocket):
    await websocket.accept()

    try:
        auth_msg = await websocket.receive_json()
        token = auth_msg.get("token", "")
        user = await _authenticate_ws(token)
        if not user:
            await websocket.send_json({"type": "error", "content": "认证失败"})
            await websocket.close()
            return
        await websocket.send_json({"type": "authenticated", "content": f"欢迎，{user.full_name}"})
    except WebSocketDisconnect:
        return
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass
        return

    orchestrator: SessionStrategy | None = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start_session":
                case_id = data.get("case_id", "")
                method = (data.get("method") or "multi_agent").lower()
                if method == "control":
                    await websocket.send_json({
                        "type": "error",
                        "content": "对照学习模式不通过 WebSocket 启动，请改用 /api/sessions/control/start REST 接口",
                    })
                    continue

                async with async_session() as db:
                    session = TrainingSession(
                        user_id=user.id,
                        case_id=case_id,
                        method=method,
                    )
                    db.add(session)
                    await db.commit()
                    await db.refresh(session)
                    session_id = session.id

                orchestrator = _build_strategy(
                    method,
                    session_id=session_id,
                    case_id=case_id,
                    user_id=user.id,
                )
                active_sessions[session_id] = orchestrator

                opening = await orchestrator.get_opening()
                await websocket.send_json({
                    "type": "session_started",
                    "session_id": str(session_id),
                    "case_id": case_id,
                    "method": method,
                })
                await websocket.send_json(opening)

            elif msg_type == "student_message":
                if not orchestrator:
                    await websocket.send_json({"type": "error", "content": "请先开始一个会话"})
                    continue

                content = data.get("content", "").strip()
                if not content:
                    continue

                async def stream_send(msg: dict):
                    await websocket.send_json(msg)

                async with async_session() as db:
                    await orchestrator.process_student_message(
                        content, db, send_fn=stream_send,
                    )
                    await db.commit()

            elif msg_type == "end_session":
                if orchestrator:
                    async with async_session() as db:
                        summary = await orchestrator.end_session(db)
                        await db.commit()
                    await websocket.send_json(summary)
                    active_sessions.pop(orchestrator.session_id, None)
                    orchestrator = None

    except WebSocketDisconnect:
        if orchestrator:
            async with async_session() as db:
                try:
                    await orchestrator.end_session(db)
                    await db.commit()
                except Exception:
                    pass
            active_sessions.pop(orchestrator.session_id, None)
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
        except Exception:
            pass
