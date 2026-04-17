import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.database import engine, Base, get_db, async_session
from app.api import auth, cases, sessions, analytics
from app.agents.orchestrator import SessionOrchestrator
from app.models.user import User
from app.models.session import TrainingSession

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
active_sessions: dict[uuid.UUID, SessionOrchestrator] = {}


async def _create_db_schema() -> None:
    logger.info("DB schema init: connecting to %s", _safe_db_url(settings.DATABASE_URL))
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("DB schema init: success")
    except Exception as exc:
        # 不阻塞进程启动，具体错误会打印到 Railway deploy log
        logger.exception("DB schema init FAILED — type=%s msg=%s", type(exc).__name__, exc)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== SPAgent backend lifespan start ===")
    logger.info("DATABASE_URL : %s", _safe_db_url(settings.DATABASE_URL))
    logger.info("QWEN_MODEL   : %s", settings.QWEN_MODEL)
    logger.info("DASHSCOPE_KEY: %s", "SET" if settings.DASHSCOPE_API_KEY else "EMPTY — LLM calls will fail")
    logger.info("JWT_SECRET   : %s", "SET" if settings.JWT_SECRET not in ("change-me-in-production", "your-jwt-secret-change-me") else "DEFAULT (change in production)")

    # Fire-and-forget: schema init runs in the background so the app can
    # respond to healthchecks immediately without waiting for the DB.
    asyncio.create_task(_create_db_schema())
    try:
        logger.info("=== SPAgent backend ready, accepting requests ===")
        yield
    finally:
        logger.info("=== SPAgent backend shutting down ===")
        await engine.dispose()


app = FastAPI(
    title="SPAgent - 医学教育智能训练系统",
    description="基于三智能体协作架构的标准化病人训练平台",
    version="1.0.0",
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
app.include_router(sessions.router)
app.include_router(analytics.router)


@app.get("/health")
async def health_check():
    """轻量健康检查：只确认进程存活，不等 DB。"""
    return {"status": "ok", "service": "SPAgent"}


@app.get("/health/detailed")
async def health_check_detailed():
    """详细健康检查：同时测试数据库连通性，用于手动诊断。"""
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
        "service": "SPAgent",
        "database": db_status,
        "database_url": _safe_db_url(settings.DATABASE_URL),
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

    # Expect first message to be auth
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

    orchestrator: SessionOrchestrator | None = None

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "start_session":
                case_id = data.get("case_id", "")
                async with async_session() as db:
                    session = TrainingSession(
                        user_id=user.id,
                        case_id=case_id,
                    )
                    db.add(session)
                    await db.commit()
                    await db.refresh(session)
                    session_id = session.id

                orchestrator = SessionOrchestrator(
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
