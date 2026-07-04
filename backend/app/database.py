from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

DATABASE_URL = settings.database_url

# Convert postgresql:// to postgresql+asyncpg:// for async support
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_recycle=1800,
    # Disabled: SQLAlchemy 2.0.36 + aiomysql 0.2.0 have a known incompatibility
    # where pool_pre_ping calls connection.ping() with no args, but the
    # AsyncAdapt_aiomysql_connection.ping(reconnect) wrapper has no default.
    # Fixed upstream in SQLAlchemy >= 2.0.50. aiomysql's own reconnection +
    # pool_recycle still handle dead connections.
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
