"""配置：DB URL、组别定义、统计阈值。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

# 优先读取 evaluate/.env，再回退到工程根 .env（以便复用 backend 的连接串）
_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
load_dotenv(_HERE / ".env")
load_dotenv(_ROOT / ".env", override=False)
load_dotenv(_ROOT / "backend" / ".env", override=False)


# 学生在系统里实际选择的 method 字段值
LEARNING_METHODS: tuple[str, ...] = ("multi_agent", "single_agent", "control")
EXAM_METHOD: str = "exam"

# 论文呈现时的简称
GROUP_LABELS: Mapping[str, str] = {
    "multi_agent": "MA",
    "single_agent": "SA",
    "control": "CT",
    "exam": "Exam",
}

# OSCE 4 维度（与 final_evaluations.holistic_scores_json 的键对齐）
OSCE_DIMENSIONS: tuple[str, ...] = (
    "history_completeness",
    "communication",
    "clinical_reasoning",
    "diagnostic_accuracy",
)


def _normalize_db_url(url: str) -> str:
    """如果用户填了 asyncpg 串，自动改成 psycopg2（pandas/SQLAlchemy 同步连接需要）。"""
    if not url:
        return url
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://") and "+psycopg2" not in url:
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: _normalize_db_url(os.getenv("DATABASE_URL", "")))
    database_ssl_verify: bool = field(
        default_factory=lambda: os.getenv("DATABASE_SSL_VERIFY", "false").lower() in ("1", "true", "yes")
    )
    output_dir: Path = field(default_factory=lambda: Path(os.getenv("OUTPUT_DIR", "evaluate/output")))
    alpha: float = field(default_factory=lambda: float(os.getenv("ALPHA", "0.05")))

    def ensure_output(self) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir


def get_settings() -> Settings:
    return Settings()
