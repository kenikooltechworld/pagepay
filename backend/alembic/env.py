"""Alembic environment configuration (async)."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.database import Base

# Import all models so their tables are registered on Base.metadata.
from app.models import user as _user_models  # noqa: F401

config = context.config

# Override sqlalchemy.url from settings (Neon DATABASE_URL).
# Transform postgresql:// -> postgresql+asyncpg:// (same as app/core/database.py).
db_url = settings.database_url
if db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    import ssl
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    url = config.get_main_option("sqlalchemy.url")
    # Strip unsupported query params (same as app/core/database.py).
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    unsupported = {"sslmode", "sslrootcert", "channel_binding", "sslcert", "sslkey"}
    qs = {k: v for k, v in qs.items() if k not in unsupported}
    url = urlunparse(parsed._replace(query=urlencode(qs, doseq=True)))

    ssl_context = ssl.create_default_context()
    if settings.environment == "production":
        ssl_context.check_hostname = True
        ssl_context.verify_mode = ssl.CERT_REQUIRED
    else:
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE

    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(
        url,
        connect_args={"ssl": ssl_context, "server_settings": {"application_name": "pagepay_alembic"}},
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
