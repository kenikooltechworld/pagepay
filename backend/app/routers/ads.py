"""Ad reward credit endpoint.

POST /api/v1/ads/credit — the canonical entry point for every rewarded
ad impression that earns the user points. The client passes what the ad
SDK reported (USD revenue + a unique transaction_id); we apply the
revenue-share math and credit the wallet atomically.

Flow:
  1. Look up by transaction_id. If we've seen it, return the prior
     outcome — same callback fired twice never double-credits.
  2. Fetch the live USD→NGN rate from app.services.fx (cached 60s).
     On failure, reject the credit with 503 — we MUST NOT credit at
     a stale rate.
  3. Compute the user's share:
        ngn_revenue  = revenue_usd × fx_rate
        user_share   = ngn_revenue × 0.80     (platform keeps 20%)
        points       = int(user_share × 100)  (100 pts = ₦1)
     If points rounds to 0, we still record the impression as
     `rejected_low_value` — never fabricate a "1 point" floor.
  4. Insert an ad_events row with all the audit fields.
  5. Bump User.points_balance atomically. Return the new balance.

The router does NOT touch /session/end, /session/claim, or any read-
time reward math. Read time rewards are a separate code path; this
endpoint is purely "ad watched → points credited".
"""

from __future__ import annotations

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AdEvent, User
from app.routers.auth import get_current_user
from app.schemas import AdCreditRequest, AdCreditResponse
from app.services import fx as fx_module


logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/ads", tags=["ads"])


# Platform revenue share: 20% to us, 80% to the user. Keep this as a
# constant — flipping it requires a deploy, which is the right blast
# radius for a money-affecting change.
PLATFORM_SHARE = 0.20
USER_SHARE = 1.0 - PLATFORM_SHARE

# 100 points = ₦1 (NGN). All point math goes through this constant so
# the conversion rate lives in exactly one place.
POINTS_PER_NAIRA = 100


@router.post("/credit", response_model=AdCreditResponse)
async def credit_ad_reward(
    payload: AdCreditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdCreditResponse:
    """Credit the user's wallet based on the USD revenue this ad
    impression generated.

    Idempotent on `transaction_id`. Replay-safe — calling twice with the
    same id returns the original outcome and bumps nothing.
    """
    # ── 1. Idempotency check ────────────────────────────────────────
    # Look up the transaction_id before doing any work. If we've seen it,
    # return the prior outcome. The unique constraint on ad_events.
    # transaction_id would also catch a race, but the SELECT-then-INSERT
    # path keeps the response shape consistent with the credit case.
    existing = (
        await db.execute(
            select(AdEvent).where(AdEvent.transaction_id == payload.transaction_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        me = (
            await db.execute(select(User.points_balance).where(User.id == current_user.id))
        ).scalar_one()
        return AdCreditResponse(
            points_credited=existing.user_points_credited or 0,
            new_balance=me,
            fx_rate_used=existing.fx_rate_used or 0.0,
            user_share_ngn=(
                (existing.user_points_credited or 0) / POINTS_PER_NAIRA
            ),
            credit_status="duplicate",
        )

    # ── 2. Live FX ──────────────────────────────────────────────────
    # We MUST have a fresh rate. If the FX endpoint is down or returns
    # something we can't parse, we refuse the credit — crediting at a
    # zero or stale rate would silently lose (or over-credit) the user.
    try:
        # Module-level lookup so tests can monkeypatch
        # `app.services.fx.get_usd_to_ngn` and have the patched version
        # be what we actually call here.
        fx = await fx_module.get_usd_to_ngn()
    except Exception as exc:
        logger.error("FX lookup failed during ad credit: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="FX rate unavailable — credit rejected. Try again in a moment.",
        )

    # ── 3. Math ─────────────────────────────────────────────────────
    ngn_revenue = payload.revenue_usd * fx.rate
    user_share_ngn = ngn_revenue * USER_SHARE
    points = int(user_share_ngn * POINTS_PER_NAIRA)

    # ── 4. Persist impression + credit ──────────────────────────────
    # `rejected_low_value` covers the case where the per-impression
    # revenue is so small that 80% × NGN × 100 rounds to 0 pts. We still
    # record the impression for analytics; the wallet is not bumped.
    credit_status = "credited" if points > 0 else "rejected_low_value"

    event = AdEvent(
        user_id=current_user.id,
        session_id=None,
        ad_type="rewarded",
        ad_unit=payload.ad_unit,
        provider=payload.provider,
        # Legacy column from Phase 1 — keep populated for the existing
        # admin reporting queries. Micro-USD integer encoding (1 USD = 1e6).
        impression_revenue_usd=int(payload.revenue_usd * 1_000_000),
        watched_fully=True,
        reward_granted=(credit_status == "credited"),
        transaction_id=payload.transaction_id,
        revenue_usd=int(payload.revenue_usd * 1_000_000),     # micro-USD
        fx_rate_used=int(fx.rate * 1_000_000),                # micro-NGN/USD
        user_points_credited=points if credit_status == "credited" else 0,
        credit_status=credit_status,
    )
    db.add(event)

    if credit_status == "credited":
        await db.execute(
            update(User)
            .where(User.id == current_user.id)
            .values(points_balance=User.points_balance + points)
        )

    await db.commit()

    # Re-read the balance after the commit so the response reflects
    # whatever the DB just committed — no risk of a stale ORM value.
    me = (
        await db.execute(select(User.points_balance).where(User.id == current_user.id))
    ).scalar_one()

    logger.info(
        "Ad credit user=%s unit=%s provider=%s tx=%s usd=%.6f rate=%.4f "
        "ngn=%.4f share=%.4f pts=%d status=%s balance=%d",
        current_user.id, payload.ad_unit, payload.provider,
        payload.transaction_id, payload.revenue_usd, fx.rate,
        ngn_revenue, user_share_ngn, points, credit_status, me,
    )

    return AdCreditResponse(
        points_credited=points,
        new_balance=me,
        fx_rate_used=fx.rate,
        user_share_ngn=user_share_ngn,
        credit_status=credit_status,
    )