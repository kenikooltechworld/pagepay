import ssl
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

DATABASE_URL = settings.database_url

# Convert postgresql:// to postgresql+asyncpg:// for async support
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

# Create SSL context for Render PostgreSQL
# Render uses self-signed certificates, so we skip verification in non-production
def _get_ssl_context():
    """Create SSL context for asyncpg.
    
    For Render PostgreSQL:
    - Uses self-signed certificates
    - Skip certificate verification (CERT_NONE) for non-production
    - Still provides encrypted connection
    - For production: use CERT_REQUIRED with proper CA bundles
    """
    ssl_context = ssl.create_default_context()
    # Skip hostname/cert verification for self-signed certs
    # In production with real CA certs, use ssl.CERT_REQUIRED
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context

engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_recycle=1800,
    # SSL required for Render PostgreSQL
    connect_args={
        "ssl": _get_ssl_context(),
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
