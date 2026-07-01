from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
import hmac
import logging
from app.config import settings
from app.database import get_db
from app.services.content.gutendex import import_gutendex
from app.services.content.gnews import import_gnews
from app.services.content.slicing import slice_all_books, slice_and_persist, force_reslice_all
from app.services.paystack import get_client as get_paystack_client, PaystackError
from app.models import ContentCatalog
from sqlalchemy import select

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/admin/content", tags=["admin"])


async def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    """Gate admin endpoints behind X-Admin-Token.

    Returns 401 if the header is missing or doesn't match settings.admin_token.
    We use a shared secret (not user JWTs) because admin callers are
    scripts and the cron container, not humans. Constant-time compare
    avoids a token-length side channel.
    """
    expected = settings.admin_token
    if not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Token",
            headers={"WWW-Authenticate": "X-Admin-Token"},
        )


@router.post("/import", dependencies=[Depends(require_admin_token)])
async def import_content(
    source: str = Query("gutenberg"),
    limit: int = Query(50, ge=1, le=500),
    start_page: int = Query(1, ge=1, description="1-indexed page; advance each cron run"),
    db: AsyncSession = Depends(get_db),
):
    if source == "gutenberg":
        count = await import_gutendex(db, limit=limit, start_page=start_page)
        return {"imported": count, "source": source, "start_page": start_page}
    if source == "gnews":
        count = await import_gnews(db, limit=limit, start_page=start_page)
        return {"imported": count, "source": source, "start_page": start_page}
    raise HTTPException(status_code=400, detail=f"Unknown source: {source}")


@router.post("/slice", dependencies=[Depends(require_admin_token)])
async def slice_existing(
    work_id: int | None = Query(None, description="Slice one work by id; omit to slice all"),
    db: AsyncSession = Depends(get_db),
):
    """Slice long content rows into 2-minute child reads.

    If `work_id` is given, slices only that parent (re-runs are idempotent).
    If omitted, slices every parent book in the catalog that doesn't already
    have children. Returns a summary of what was sliced and skipped.
    """
    if work_id is not None:
        row = await db.execute(select(ContentCatalog).where(ContentCatalog.id == work_id))
        parent = row.scalar_one_or_none()
        if not parent:
            raise HTTPException(status_code=404, detail=f"Work {work_id} not found")
        n = await slice_and_persist(db, parent)
        return {"sliced": 1, "children_added": n, "work_id": work_id}

    summary = await slice_all_books(db)
    return summary


@router.post("/reslice", dependencies=[Depends(require_admin_token)])
async def reslice_all(db: AsyncSession = Depends(get_db)):
    """Wipe every slice and re-slice every parent from scratch.

    Use this when the catalog has books that were imported before slicing
    was wired in (so they sit as 30-minute or 1-hour monoliths) or when
    the slicer config changes. Active `reading_session` rows are not
    touched; `reading_progress` rows have their `current_slice_id`
    cleared so the next resume points at slice 1 of the user's current
    work. Idempotent — safe to call repeatedly.

    Distinct from /slice which is non-destructive (skips parents that
    already have children). This one is destructive by design.
    """
    summary = await force_reslice_all(db)
    return summary


# ── Platform balance monitoring ──────────────────────────────────────

@router.get("/platform-balance", dependencies=[Depends(require_admin_token)])
async def get_platform_balance():
    """Return the current Paystack balance in kobo.

    Used by admin dashboard to monitor available balance and detect
    when auto-settlement has drained the account (which blocks
    user withdrawals). Returns 503 if Paystack is unconfigured or
    unreachable.
    """
    if not settings.paystack_secret_key:
        raise HTTPException(
            status_code=503,
            detail="PAYSTACK_SECRET_KEY is not configured",
        )
    try:
        balance_kobo = await get_paystack_client().get_balance()
    except PaystackError as exc:
        logger.error("Failed to fetch Paystack balance: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Unable to fetch Paystack balance",
        ) from exc
    return {
        "balance_kobo": balance_kobo,
        "balance_ngn": balance_kobo / 100,
        "currency": "NGN",
    }
