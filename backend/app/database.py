from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

DATABASE_URL = settings.database_url

# Convert postgresql:// to postgresql+asyncpg:// for async support
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# For Render PostgreSQL:
# - Internal Database URL (inside Render): uses built-in Let's Encrypt certs, ssl=True
# - External Database URL (outside Render): append ?sslmode=require to connection string
# Per Render docs: publicly trusted certs are built into OS/runtime, no .pem file needed

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_recycle=1800,
    # Render PostgreSQL requires SSL, uses Let's Encrypt certs in runtime
    connect_args={
        "ssl": True,
        "server_settings": {
            "application_name": "pagepay_backend",
        },
    },
    pool_pre_ping=False,
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
