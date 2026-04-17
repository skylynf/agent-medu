import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import engine, Base, get_db, async_session
from app.api import auth, cases, sessions, analytics
from app.agents.orchestrator import SessionOrchestrator
from app.models.user import User
from app.models.session import TrainingSession

settings = get_settings()

logger = logging.getLogger(__name__)

# In-memory registry of active orchestrators (keyed by session_id)
active_sessions: dict[uuid.UUID, SessionOrchestrator] = {}


async def _create_db_schema() -> None:
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database schema ready")
    except Exception:
        # 不阻塞进程启动，便于 Railway /health 先通过；具体错误看部署日志
        logger.exception("database schema initialization failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_task = asyncio.create_task(_create_db_schema())
    try:
        yield
    finally:
        try:
            await init_task
        except Exception:
            pass
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
    return {"status": "ok", "service": "SPAgent"}


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
