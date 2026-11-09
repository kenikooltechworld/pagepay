import ssl
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

DATABASE_URL = settings.database_url

if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

parsed = urlparse(DATABASE_URL)
qs = parse_qs(parsed.query)
unsupported = {"sslmode", "sslrootcert", "channel_binding", "sslcert", "sslkey"}
qs = {k: v for k, v in qs.items() if k not in unsupported}
DATABASE_URL = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

connect_args: dict[str, object] = {
    "server_settings": {"application_name": "pagepay_backend"},
}

if DATABASE_URL.startswith("postgresql+asyncpg://"):
    ssl_context = ssl.create_default_context()
    if settings.environment == "production":
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    else:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
    connect_args["ssl"] = ssl_context

engine = create_async_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_recycle=1800,
    connect_args=connect_args,
    pool_pre_ping=True,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
