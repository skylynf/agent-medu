import ssl
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()


def _asyncpg_ssl_context(*, strict_verify: bool) -> bool | ssl.SSLContext:
    """strict_verify=False 时仍走 TLS，但不校验证书链（解决自签 CA / 链不完整导致的 CERTIFICATE_VERIFY_FAILED）。"""
    if strict_verify:
        return True
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _railway_managed_host(host: str) -> bool:
    h = host.lower()
    return h.endswith(".railway.internal") or h.endswith(".rlwy.net") or ".railway." in h


def _asyncpg_url_and_ssl(url: str, *, ssl_verify: bool) -> tuple[str, dict]:
    """
    asyncpg 不使用 libpq 的 sslmode 查询参数；Railway 常见 ?sslmode=require，需改为 connect_args。
    对 *.railway.app / *.rlwy.net 等入口默认开启 TLS；Railway 托管主机上默认不因证书链校验失败而断连。
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    pairs = parse_qsl(parsed.query, keep_blank_values=True)
    sslmodes = [v.lower() for k, v in pairs if k.lower() == "sslmode"]
    rest = [(k, v) for k, v in pairs if k.lower() != "sslmode"]
    connect_args: dict = {}
    use_ssl = False
    if any(m in ("require", "verify-ca", "verify-full", "prefer") for m in sslmodes):
        use_ssl = True
    elif "railway" in host or host.endswith(".rlwy.net"):
        use_ssl = True
    if use_ssl:
        # 仅 sslmode=verify-ca / verify-full 时严格校验证书链；sslmode=require 与 libpq 一致（加密、不校验服务端证书）。
        # 否则 require + 自签/不完整链会在 Python 侧触发 CERTIFICATE_VERIFY_FAILED。
        want_strict = ssl_verify and any(m in ("verify-ca", "verify-full") for m in sslmodes)
        connect_args["ssl"] = _asyncpg_ssl_context(strict_verify=want_strict)
    new_query = urlencode(rest)
    clean = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )
    return clean, connect_args


_db_url, _db_ssl = _asyncpg_url_and_ssl(settings.DATABASE_URL, ssl_verify=settings.DATABASE_SSL_VERIFY)
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
