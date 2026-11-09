"""FastAPI application entrypoint."""

import logging

from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app.core.database import Base, engine
from app.core.logging_middleware import RequestLogMiddleware
from app.core.socketio import sio
from app.limiter import limiter

# Basic logging config so INFO/ERROR show in Docker/Render logs.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

# Import models so their tables are registered on `Base.metadata` before create_all.
from app.models import payment as _payment_models  # noqa: F401
from app.models import user as _user_models  # noqa: F401
from app.models import wallet as _wallet_models  # noqa: F401
from app.routers import auth, notifications, payments, payouts, pin, study, wallet
from app.services.fcm_service import initialize_firebase

app = FastAPI(title="PagePay API")
logger = logging.getLogger("uvicorn.error")

# Request/response logging (redacts secrets/tokens/pins/passwords).
app.add_middleware(RequestLogMiddleware)

# --- Rate limiting (slowapi) ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- Routers ---
app.include_router(auth.router, prefix="/api/v1")
app.include_router(pin.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(study.router, prefix="/api/v1")
app.include_router(wallet.router, prefix="/api/v1")
app.include_router(payments.router, prefix="/api/v1")
app.include_router(payouts.router, prefix="/api/v1")


@app.on_event("startup")
async def on_startup():
    """Create tables if missing (dev convenience). Use Alembic migrations in prod.

    Multiple gunicorn workers can race on `create_all`; catch benign duplicate-type/table errors.
    """

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        logger.warning("create_all skipped/failed (likely raced): %s", exc)

    # Initialize Firebase for push notifications (best-effort).
    try:
        initialize_firebase()
    except Exception as exc:
        logger.warning("Firebase init failed: %s", exc)
    logger.info("startup complete")


@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"status": "ok", "service": "pagepay-api"}


@app.get("/api/v1/health")
async def health():
    return {"status": "ok"}


@app.get("/api/v1/health/db")
async def health_db():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


# Wrap with Socket.IO for real-time updates.
import socketio as _socketio

socket_app = _socketio.ASGIApp(sio, app)
