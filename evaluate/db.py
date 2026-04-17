"""DB 引擎（同步 psycopg2，便于 pandas.read_sql）。"""
from __future__ import annotations

import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from evaluate.config import Settings, get_settings


def _strip_sslmode(url: str) -> tuple[str, dict]:
    """psycopg2 支持 sslmode 查询参数，留着即可；返回原 URL 与 connect_args。"""
    parsed = urlparse(url)
    return url, {}


def make_engine(settings: Settings | None = None) -> Engine:
    s = settings or get_settings()
    if not s.database_url:
        raise RuntimeError(
            "DATABASE_URL 未设置。请复制 evaluate/.env.example 为 evaluate/.env 并填入。"
        )
    url, connect_args = _strip_sslmode(s.database_url)
    return create_engine(url, future=True, pool_pre_ping=True, connect_args=connect_args)
