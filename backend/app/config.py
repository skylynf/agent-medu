from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from functools import lru_cache


def _to_asyncpg_url(url: str) -> str:
    """Railway 等环境常提供 postgresql://，SQLAlchemy 异步引擎需 postgresql+asyncpg://。"""
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    return url


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/spagent"
    DATABASE_URL_SYNC: str = "postgresql://postgres:postgres@localhost:5432/spagent"
    DASHSCOPE_API_KEY: str = ""
    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    QWEN_MODEL: str = "qwen-max"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def normalize_async_database_url(cls, v: object) -> object:
        if isinstance(v, str):
            return _to_asyncpg_url(v)
        return v

    @model_validator(mode="after")
    def derive_sync_url_if_needed(self) -> "Settings":
        # 未单独配置 DATABASE_URL_SYNC 时，从异步 URL 推导 psycopg2 用的同步连接串
        default_sync = "postgresql://postgres:postgres@localhost:5432/spagent"
        if self.DATABASE_URL_SYNC == default_sync and self.DATABASE_URL.startswith(
            "postgresql+asyncpg://"
        ):
            self.DATABASE_URL_SYNC = "postgresql://" + self.DATABASE_URL.removeprefix(
                "postgresql+asyncpg://"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
