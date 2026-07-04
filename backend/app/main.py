from contextlib import asynccontextmanager
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.limiter import limiter
from app.models import Base
from app.routers import auth, content, sessions, health, wallet, progress, ads, study, legal
from app.routers.ai import router as ai_router
from app.routers.referral import router as referral_router
from app.routers.community import router as community_router
from app.routers.streak import router as streak_router
from app.routers.analytics import router as analytics_router
from app.routers.payouts import router as payouts_router
from app.routers.payments import router as payments_router
from app.routers.admin import router as admin_router
from app.routers.config import router as config_router
from app.routers.tasks import router as tasks_router
from app.routers.sponsor import router as sponsor_router
from app.seed import run_all_seeds
from app.services.task_processor import task_processor
from app.services.ai_verification import verification_service

logger = logging.getLogger("uvicorn.error")

# Background task processor
processor_task = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global processor_task
    
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        # Tables may already exist from a prior run with a different schema.
        # create_all is idempotent for matching tables, but stale schemas crash
        # the worker. Log and continue so the API still serves requests.
        logger.warning("Skipping create_all on startup: %s", exc)

    # Phase 2 ad-infrastructure seed. Runs in its own session so a
    # transactional error here doesn't poison the create_all pool.
    try:
        async with AsyncSessionLocal() as session:
            counts = await run_all_seeds(session)
            if any(counts.values()):
                logger.info("Phase 2 seed inserted: %s", counts)
    except Exception as exc:  # noqa: BLE001 — startup seed; best-effort
        logger.warning("Phase 2 seed failed: %s", exc)
    
    # Start Phase 7 background task processor
    logger.info("Starting Phase 7 task processor...")
    processor_task = asyncio.create_task(task_processor.start())

    yield
    
    # Shutdown: stop background processor
    logger.info("Stopping Phase 7 task processor...")
    task_processor.stop()
    if processor_task:
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
    
    # Close AI verification service HTTP client
    await verification_service.close()


app = FastAPI(title="PagePay API", lifespan=lifespan)
app.state.limiter = limiter
def _rate_limit_handler(request, exc):
    """Render a RateLimitExceeded as a JSON 429 instead of letting
    slowapi's default handler crash.

    Starlette's exception-handler contract is `(request, exc) -> Response`.
    The previous lambda returned `exc.detail` (a string), which Starlette
    then tried to call as a handler — hence `TypeError: 'str' object is
    not callable` whenever the 5/15min login limit actually fired.
    """
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limited", "message": str(exc.detail)}},
    )


app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(content.router, prefix=API_PREFIX)
app.include_router(sessions.router, prefix=API_PREFIX)
app.include_router(wallet.router, prefix=API_PREFIX)
app.include_router(health.router, prefix=API_PREFIX)
app.include_router(admin_router, prefix=API_PREFIX)
app.include_router(progress.router, prefix=API_PREFIX)
app.include_router(ads.router, prefix=API_PREFIX)
app.include_router(payouts_router, prefix=API_PREFIX)
app.include_router(payments_router, prefix=API_PREFIX)
app.include_router(config_router, prefix=API_PREFIX)
app.include_router(study.router, prefix=API_PREFIX)
app.include_router(ai_router, prefix=API_PREFIX)
app.include_router(referral_router, prefix=API_PREFIX)
app.include_router(community_router, prefix=API_PREFIX)
app.include_router(streak_router, prefix=API_PREFIX)
app.include_router(analytics_router, prefix=API_PREFIX)
app.include_router(legal.router, prefix=API_PREFIX)

# Phase 7: Social Tasks
app.include_router(tasks_router, prefix=API_PREFIX)
app.include_router(sponsor_router, prefix=API_PREFIX)
