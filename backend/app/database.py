from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()


def _asyncpg_url_and_ssl(url: str) -> tuple[str, dict]:
    """
    asyncpg 不使用 libpq 的 sslmode 查询参数；Railway 常见 ?sslmode=require，需改为 connect_args。
    对 *.railway.app / *.rlwy.net 等公网入口默认开启 TLS。
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    sslmodes = [v.lower() for k, v in pairs if k.lower() == "sslmode"]
    rest = [(k, v) for k, v in pairs if k.lower() != "sslmode"]
    connect_args: dict = {}
    if any(m in ("require", "verify-ca", "verify-full", "prefer") for m in sslmodes):
        connect_args["ssl"] = True
    elif "railway" in host or host.endswith(".rlwy.net"):
        connect_args["ssl"] = True
    new_query = urlencode(rest)
    clean = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )
    return clean, connect_args


_db_url, _db_ssl = _asyncpg_url_and_ssl(settings.DATABASE_URL)
engine = create_async_engine(
    _db_url,
    echo=False,
    connect_args=_db_ssl,
)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
