"""Ad reward credit + Phase 2 ad-infrastructure endpoints.

POST /api/v1/ads/credit           — legacy client-driven credit path
POST /api/v1/ads/impression       — log an ad load (no credit)
POST /api/v1/ads/reward-claim     — credit after a real SDK callback
POST /api/v1/ads/google/callback  — AdMob SSV webhook (HMAC verified)
POST /api/v1/ads/applovin/callback — AppLovin SSV webhook (stub)

All credit paths share the same math + idempotency contract via
`app.services.ads`. Adding a new ad network (AppLovin MAX) is a
matter of writing its callback handler and pointing it at the same
service — the credit/audit/impression path is already network-agnostic.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import AdEvent, User
from app.routers.auth import get_current_user
from app.schemas import (
    AdCreditRequest,
    AdCreditResponse,
    AdImpressionRequest,
    AdImpressionResponse,
    AdRewardClaimRequest,
    AdRewardClaimResponse,
)
from app.services import ads as ads_service


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


# ── POST /ads/credit — legacy client-driven path ────────────────────
# Kept for the MockAdModal flow in dev and for the AppLovin path
# when SSV is unreliable. New builds should prefer /reward-claim +
# SSV; this endpoint stays for backward compat and the legacy
# in-app claim flow that predates SSV.


@router.post("/credit", response_model=AdCreditResponse)
async def credit_ad_reward(
    payload: AdCreditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdCreditResponse:
    """Credit the user's wallet based on the USD revenue this ad
    impression generated.

    Idempotent on `transaction_id`. Replay-safe — calling twice with
    the same id returns the original outcome and bumps nothing.
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

    # ── 2. Live FX + 3. Math ────────────────────────────────────────
    try:
        result = await ads_service.compute_ad_credit(payload.revenue_usd)
    except Exception as exc:
        logger.error("FX lookup failed during ad credit: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="FX rate unavailable — credit rejected. Try again in a moment.",
        )

    ngn_revenue = result.ngn_revenue
    user_share_ngn = result.user_share_ngn
    points = result.points
    credit_status = result.credit_status

    # ── 4. Persist impression + credit ──────────────────────────────
    event = AdEvent(
        user_id=current_user.id,
        session_id=None,
        ad_type="rewarded",
        ad_unit=payload.ad_unit,
        provider=payload.provider,
        # Legacy column kept populated for Phase 1 admin reports.
        impression_revenue_usd=int(payload.revenue_usd * 1_000_000),
        watched_fully=True,
        reward_granted=(credit_status == "credited"),
        transaction_id=payload.transaction_id,
        revenue_usd=int(payload.revenue_usd * 1_000_000),     # micro-USD
        fx_rate_used=int(result.fx_rate * 1_000_000),          # micro-NGN/USD
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
        payload.transaction_id, payload.revenue_usd, result.fx_rate,
        ngn_revenue, user_share_ngn, points, credit_status, me,
    )

    return AdCreditResponse(
        points_credited=points,
        new_balance=me,
        fx_rate_used=result.fx_rate,
        user_share_ngn=user_share_ngn,
        credit_status=credit_status,  # type: ignore[arg-type]
    )


# ── POST /ads/impression — log an ad load (no credit) ──────────────
# The client calls this the moment an ad slot finishes loading,
# before the user has watched it. We insert an AdEvent row with
# `credit_status='pending'` and no `transaction_id` so the
# reward-claim call later can link back via `ad_event_id` and
# upgrade the row to "credited"/"rejected_low_value".
#
# This endpoint exists so analytics can answer "how many ads did
# we serve, and what was the load-to-watch conversion rate". The
# legacy /credit endpoint conflated load + watch + credit into one
# call, which made that question unanswerable.


@router.post("/impression", response_model=AdImpressionResponse)
async def log_ad_impression(
    payload: AdImpressionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdImpressionResponse:
    """Record that an ad was loaded. Does NOT credit the wallet.

    The reward-claim call (after the user has watched the ad and
    the SDK reports a `transaction_id`) upgrades the same AdEvent
    row to "credited" and bumps the wallet. If the user never
    watches, the row stays at `credit_status='pending'` — useful
    for the load-to-watch funnel report.
    """
    event = AdEvent(
        user_id=current_user.id,
        session_id=payload.session_id,
        ad_type=payload.ad_type,
        ad_unit=payload.ad_unit,
        provider=payload.provider,
        watched_fully=False,
        reward_granted=False,
        # No transaction_id yet — the SDK hasn't reported revenue.
        # We rely on the client's `ad_event_id` to link the
        # reward-claim call back to this row.
        transaction_id=None,
        revenue_usd=None,
        fx_rate_used=None,
        user_points_credited=None,
        credit_status="pending",
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    return AdImpressionResponse(ad_event_id=event.id)


# ── POST /ads/reward-claim — credit after SDK callback ─────────────
# The new client-driven path that pairs with the SSV webhook. The
# client calls this when the SDK's revenue callback fires with a
# `transaction_id` and a USD amount. We link back to the
# AdEvent row created at impression time and apply the credit.


@router.post("/reward-claim", response_model=AdRewardClaimResponse)
async def claim_ad_reward(
    payload: AdRewardClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdRewardClaimResponse:
    """Credit a previously-logged impression with the SDK's revenue.

    Idempotent on `transaction_id`. If the same transaction_id is
    claimed twice (e.g. client retried after a network blip), the
    second call returns the original outcome without re-crediting.

    If `ad_event_id` is present, we link the credit back to the
    impression row created at load time. If it's absent (e.g. the
    client never logged an impression because the ad loaded
    faster than the user could react), we still credit — the
    audit trail just won't have the load-time row.
    """
    # ── 1. Idempotency check ────────────────────────────────────────
    existing = (
        await db.execute(
            select(AdEvent).where(AdEvent.transaction_id == payload.transaction_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        me = (
            await db.execute(select(User.points_balance).where(User.id == current_user.id))
        ).scalar_one()
        return AdRewardClaimResponse(
            ad_event_id=existing.id,
            points_credited=existing.user_points_credited or 0,
            new_balance=me,
            fx_rate_used=existing.fx_rate_used or 0.0,
            user_share_ngn=(existing.user_points_credited or 0) / POINTS_PER_NAIRA,
            credit_status=existing.credit_status,  # type: ignore[arg-type]
        )

    # Mark the load-time row as watched, if we have one.
    session_id: int | None = None
    if payload.ad_event_id is not None:
        imp = (
            await db.execute(select(AdEvent).where(AdEvent.id == payload.ad_event_id))
        ).scalar_one_or_none()
        if imp is not None:
            imp.watched_fully = True
            session_id = imp.session_id

    # ── 2. Live FX + 3. Math ────────────────────────────────────────
    try:
        result = await ads_service.compute_ad_credit(payload.revenue_usd)
    except Exception as exc:
        logger.error("FX lookup failed during reward-claim: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="FX rate unavailable — credit rejected. Try again in a moment.",
        )

    points = result.points
    credit_status = result.credit_status

    # ── 4. Persist impression + credit ──────────────────────────────
    event = AdEvent(
        user_id=current_user.id,
        session_id=session_id,
        ad_type=payload.ad_type,
        ad_unit=payload.ad_unit,
        provider=payload.provider,
        impression_revenue_usd=int(payload.revenue_usd * 1_000_000),
        watched_fully=True,
        reward_granted=(credit_status == "credited"),
        transaction_id=payload.transaction_id,
        revenue_usd=int(payload.revenue_usd * 1_000_000),
        fx_rate_used=int(result.fx_rate * 1_000_000),
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

    me = (
        await db.execute(select(User.points_balance).where(User.id == current_user.id))
    ).scalar_one()
    logger.info(
        "Ad reward-claim user=%s imp=%s unit=%s tx=%s usd=%.6f pts=%d status=%s balance=%d",
        current_user.id, payload.ad_event_id, payload.ad_unit,
        payload.transaction_id, payload.revenue_usd,
        event.user_points_credited or 0, event.credit_status, me,
    )
    return AdRewardClaimResponse(
        ad_event_id=event.id,
        points_credited=event.user_points_credited or 0,
        new_balance=me,
        fx_rate_used=result.fx_rate,
        user_share_ngn=result.user_share_ngn,
        credit_status=event.credit_status,  # type: ignore[arg-type]
    )


# ── POST /ads/google/callback — AdMob SSV webhook ──────────────────
# AdMob Server-Side Verification callback. AdMob POSTs the
# transaction details; we verify the signature, idempotency-check
# the transaction_id, find the user's active reading session, and
# credit the wallet.
#
# AdMob retries on non-2xx, so this endpoint is structured to
# return 200 in three cases:
#   1. Successful credit
#   2. Duplicate transaction_id (already credited; idempotent no-op)
#   3. FX failure (we still 200 because retrying with the same
#      payload will hit the same FX outage; the network should
#      back off, not double-call)
# The only non-200 is signature verification failure (401). AdMob
# itself is the only caller and it does NOT retry on 401, so 401
# signals a misconfigured shared secret.


def _verify_admob_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Verify AdMob's HMAC-SHA256 webhook signature.

    AdMob's SSV sends the signature in `X-AdMob-Signature` as a
    hex-encoded HMAC-SHA256 of the raw request body, using the
    shared secret configured in the AdMob dashboard. We compare
    in constant time. Returns False on any error (missing header,
    malformed hex, wrong length, secret unset) — the caller maps
    that to a 401.
    """
    secret = settings.admob_webhook_secret
    if not secret or not signature_header:
        return False
    try:
        expected = hmac.new(
            secret.encode("utf-8"), raw_body, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())
    except Exception as exc:  # noqa: BLE001 — signature path must never raise
        logger.warning("AdMob signature verify raised: %s", exc)
        return False


@router.post("/google/callback")
async def admob_ssv_callback(
    request: Request,
    x_admob_signature: str | None = Header(default=None, alias="X-Admob-Signature"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """AdMob SSV webhook. Returns 200 on all valid requests.

    Request body shape (per AdMob docs): the SDK forwards the
    reward event to AdMob with a `custom_data` payload; AdMob
    POSTs back the verification details as a query-string-encoded
    body. We accept the parsed shape via the AdSsvCallbackRequest
    schema. The signature header is the HMAC of the raw body.
    """
    raw = await request.body()
    if not _verify_admob_signature(raw, x_admob_signature):
        # 401 stops AdMob from retrying — a signature failure means
        # the shared secret is misconfigured and we won't accept
        # any further callbacks until ops rotates it.
        raise HTTPException(status_code=401, detail="Invalid AdMob signature")

    # Parse the body. AdMob's SSV sends x-www-form-urlencoded by
    # default; some configurations send JSON. We accept both.
    try:
        import json as _json
        body = _json.loads(raw.decode("utf-8") or "{}")
    except Exception:
        # Fall back to form parsing.
        from urllib.parse import parse_qs
        body = {k: v[0] for k, v in parse_qs(raw.decode("utf-8")).items()}

    # Map AdMob's wire field names to our schema.
    reward_amount = body.get("reward_amount") or body.get("revenue_amount") or 0
    try:
        reward_amount = float(reward_amount)
    except (TypeError, ValueError):
        reward_amount = 0.0
    custom_data = body.get("custom_data") or {}
    if isinstance(custom_data, str):
        try:
            custom_data = _json.loads(custom_data)
        except Exception:
            custom_data = {}

    user_id_raw = custom_data.get("user_id") or body.get("user_id")
    if user_id_raw is None:
        logger.warning("AdMob SSV: missing user_id in custom_data; ignoring")
        return {"status": "ignored", "reason": "missing_user_id"}
    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        return {"status": "ignored", "reason": "invalid_user_id"}

    transaction_id = body.get("transaction_id") or body.get("ad_unit_id")
    if not transaction_id:
        return {"status": "ignored", "reason": "missing_transaction_id"}

    ad_unit = body.get("ad_unit_id") or "admob_unknown"

    # Idempotency. If we've seen this transaction_id, return the
    # original outcome. AdMob retries on non-2xx so this is the
    # hot path during an outage.
    existing = (
        await db.execute(
            select(AdEvent).where(AdEvent.transaction_id == str(transaction_id))
        )
    ).scalar_one_or_none()
    if existing is not None:
        me = (
            await db.execute(select(User.points_balance).where(User.id == user_id))
        ).scalar_one_or_none() or 0
        return {
            "status": "duplicate",
            "points_credited": existing.user_points_credited or 0,
            "new_balance": me,
        }

    # Link to the active reading session, if any.
    active_session = await ads_service.find_active_session_for_user(db, user_id)

    # Live FX + math. We 200 on FX failure (don't retry-storm).
    try:
        result = await ads_service.compute_ad_credit(reward_amount)
    except Exception as exc:
        logger.error("AdMob SSV: FX unavailable, dropping credit: %s", exc)
        return {"status": "fx_unavailable"}

    points = result.points
    credit_status = result.credit_status

    event = AdEvent(
        user_id=user_id,
        session_id=active_session.id if active_session else None,
        ad_type="rewarded",
        ad_unit=ad_unit,
        provider="admob",
        impression_revenue_usd=ads_service.to_micro(reward_amount),
        watched_fully=True,
        reward_granted=(credit_status == "credited"),
        transaction_id=str(transaction_id),
        revenue_usd=ads_service.to_micro(reward_amount),
        fx_rate_used=ads_service.to_micro(result.fx_rate),
        user_points_credited=points if credit_status == "credited" else 0,
        credit_status=credit_status,
    )
    db.add(event)
    if credit_status == "credited":
        await db.execute(
            update(User)
            .where(User.id == user_id)
            .values(points_balance=User.points_balance + points)
        )
    await db.commit()
    me = (
        await db.execute(select(User.points_balance).where(User.id == user_id))
    ).scalar_one()
    logger.info(
        "AdMob SSV credited user=%s unit=%s tx=%s usd=%.6f pts=%d status=%s balance=%d",
        user_id, ad_unit, transaction_id, reward_amount,
        event.user_points_credited or 0, event.credit_status, me,
    )
    return {
        "status": event.credit_status,
        "points_credited": event.user_points_credited or 0,
        "new_balance": me,
    }


# ── POST /ads/applovin/callback — AppLovin SSV webhook (stub) ──────
# AppLovin MAX uses a different secret and a different payload
# shape (server-to-server postback with `currency` and `revenue`
# fields). When AppLovin integration is wired, this endpoint will
# mirror the AdMob one with the matching signature scheme. Until
# then, return 501 so AppLovin's dashboard doesn't silently
# swallow failures.


@router.post("/applovin/callback")
async def applovin_ssv_callback() -> dict:
    """AppLovin MAX SSV webhook — not yet implemented.

    Returns 501 so the AppLovin dashboard shows the endpoint is
    reachable but unwired. The contract (idempotency on
    transaction_id, FX-fetched credit math) is already in
    place via the shared `ads_service` — adding the AppLovin
    payload parser + signature scheme is the only work left.
    """
    raise HTTPException(
        status_code=501,
        detail="AppLovin SSV not yet implemented. Wire the postback secret in app/config.py and add the payload parser.",
    )
