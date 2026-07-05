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

from fastapi import APIRouter, Depends, HTTPException, Request
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
PLATFORM_SHARE = 0.05
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
# AdMob Server-Side Verification callback. AdMob sends a GET request
# with query parameters containing the reward data and an ECDSA P-256
# signature. We verify the signature against Google's published public
# keys, then credit the user's wallet.
#
# Reference: https://developers.google.com/admob/ios/rewarded-video-ssv
#            https://developers.google.com/admob/android/rewarded-video-ssv
#
# AdMob retries on non-2xx, so we return 200 in all cases except
# signature failure (401). Idempotent on transaction_id.


import json as _json
from urllib.parse import parse_qs

import httpx


# Cache Google's SSV public keys so we don't fetch them on every callback.
# Keys are rotated rarely — a 24-hour cache is safe.
_GOOGLE_VERIFIER_KEYS: dict[str, str] | None = None
_VERIFIER_KEYS_URL = "https://www.gstatic.com/admob/reward/verifier-keys.json"
_VERIFIER_KEYS_TTL_SECONDS = 86400
_last_keys_fetch: float = 0


async def _fetch_verifier_keys() -> dict[str, str]:
    """Fetch and cache Google's ECDSA P-256 public keys for AdMob SSV.

    Returns a dict mapping key_id → PEM-encoded public key string.
    Cached in memory for 24 hours. Falls back to stale cache on failure.
    """
    global _GOOGLE_VERIFIER_KEYS, _last_keys_fetch
    now = __import__('time').time()
    if _GOOGLE_VERIFIER_KEYS is not None and (now - _last_keys_fetch) < _VERIFIER_KEYS_TTL_SECONDS:
        return _GOOGLE_VERIFIER_KEYS

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_VERIFIER_KEYS_URL)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("Failed to fetch AdMob verifier keys: %s", exc)
        if _GOOGLE_VERIFIER_KEYS is not None:
            return _GOOGLE_VERIFIER_KEYS
        raise

    keys: dict[str, str] = {}
    try:
        # Response shape: {"keys": [{"keyId": 3335741209, "pem": "...", "base64": "..."}, ...]}
        # keyId is an integer from Google but AdMob sends it as a string — store as string.
        for entry in data.get("keys", []):
            kid = str(entry.get("keyId", ""))
            pem = entry.get("pem")
            if kid and pem:
                keys[kid] = pem
    except Exception as exc:
        logger.error("Failed to parse AdMob verifier keys: %s", exc)
        raise

    if not keys:
        logger.error("No valid AdMob verifier keys found in response")
        raise ValueError("No valid keys")

    _GOOGLE_VERIFIER_KEYS = keys
    _last_keys_fetch = now
    return keys


async def _verify_admob_ssv_signature(query_params: dict[str, str]) -> bool:
    """Verify the ECDSA P-256 signature on an AdMob SSV callback.

    The signing string is: all query params (excluding 'signature' and 'key_id')
    sorted alphabetically, formatted as 'key=value\\n', with final \\n.

    Returns True if the signature is valid.
    """
    signature_b64 = query_params.get("signature")
    key_id = query_params.get("key_id")
    if not signature_b64 or not key_id:
        return False

    # Reconstruct the signing string
    excluded = {"signature", "key_id"}
    parts = []
    for k in sorted(query_params):
        if k not in excluded:
            parts.append(f"{k}={query_params[k]}")
    signing_string = "\n".join(parts) + "\n"

    try:
        import base64
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import serialization, hashes
        from cryptography.hazmat.backends import default_backend

        keys = await _fetch_verifier_keys()
        if key_id not in keys:
            logger.warning("AdMob SSV: unknown key_id=%s", key_id)
            return False

        # Load PEM public key
        pem_data = keys[key_id].encode("utf-8")
        public_key = serialization.load_pem_public_key(pem_data, backend=default_backend())

        # Decode the base64 signature
        signature = base64.b64decode(signature_b64)

        # Verify ECDSA
        public_key.verify(signature, signing_string.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except Exception as exc:
        logger.error("AdMob SSV signature verification failed: %s", exc)
        return False


@router.get("/google/callback")
async def admob_ssv_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """AdMob SSV webhook — GET request with query parameters.

    AdMob sends a GET to this URL with the reward data as query params:
      ?ad_network=...&ad_unit=...&reward_amount=...&user_id=...&transaction_id=...&signature=...&key_id=...

    Returns 200 on success/idempotent, 401 on bad signature.
    """
    query_params = {k: v for k, v in request.query_params.items()}

    if not query_params:
        # Empty GET = AdMob's connectivity test
        return {"status": "verification_success", "message": "SSV endpoint reachable"}

    # Verify ECDSA signature
    is_valid = await _verify_admob_ssv_signature(query_params)
    if not is_valid:
        logger.warning("AdMob SSV: invalid signature for transaction %s",
                       query_params.get("transaction_id", "unknown"))
        raise HTTPException(status_code=401, detail="Invalid SSV signature")

    # Parse fields. Note: reward_amount from SSV is the custom reward value
    # set in the AdMob dashboard (e.g. "1") — it is NOT ad revenue. The
    # actual revenue comes exclusively from the client-side PAID event.
    # SSV is verification that the user completed the ad; we log it but
    # do NOT credit points here to avoid double-crediting.
    reward_amount = float(query_params.get("reward_amount", 0))
    user_id_raw = query_params.get("user_id", "")
    transaction_id = query_params.get("transaction_id", "")
    ad_unit = query_params.get("ad_unit", "admob_unknown")

    try:
        user_id = int(user_id_raw)
    except (TypeError, ValueError):
        logger.warning("AdMob SSV: invalid user_id=%s", user_id_raw)
        return {"status": "ignored", "reason": "invalid_user_id"}

    if not transaction_id:
        return {"status": "ignored", "reason": "missing_transaction_id"}

    # Idempotency check — if the client-side PAID event already credited
    # this transaction, return the existing outcome.
    existing = (
        await db.execute(
            select(AdEvent).where(AdEvent.transaction_id == transaction_id)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return {
            "status": "duplicate",
            "points_credited": existing.user_points_credited or 0,
            "new_balance": 0,
        }

    # Log the SSV verification event but do NOT credit points.
    # Points are credited by the client-side PAID event handler.
    logger.info(
        "AdMob SSV verified: user=%s unit=%s tx=%s reward_amount=%.6f",
        user_id, ad_unit, transaction_id, reward_amount,
    )

    event = AdEvent(
        user_id=user_id,
        session_id=None,
        ad_type="rewarded",
        ad_unit=ad_unit,
        provider="admob",
        watched_fully=True,
        reward_granted=True,
        transaction_id=transaction_id,
        revenue_usd=None,
        fx_rate_used=None,
        user_points_credited=None,
        credit_status="pending",
    )
    db.add(event)
    await db.commit()

    return {
        "status": "verified",
        "message": "SSV callback verified. Points credited via client-side PAID event.",
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
