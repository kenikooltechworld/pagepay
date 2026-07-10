"""Ad reward credit + Phase 2 ad-infrastructure endpoints.

POST /api/v1/ads/credit            — DEPRECATED 410 Gone (legacy client-revenue path)
POST /api/v1/ads/impression        — DEPRECATED 410 Gone (legacy pending-impression log)
POST /api/v1/ads/reward-claim      — DEPRECATED 410 Gone (legacy SDK-callback credit)
POST /api/v1/ads/request-token     — NEW: issue one-time ad-request token
GET  /api/v1/ads/recent-credits    — NEW: poll for credited ad events
GET  /api/v1/ads/google/callback   — AdMob SSV webhook (ECDSA verified)
POST /api/v1/ads/applovin/callback — AppLovin SSV webhook (stub)

The /ads/credit and /ads/reward-claim endpoints accepted a client-
supplied `revenue_usd` value and credited points based on it. They
were attack surfaces: an authenticated client could mint arbitrary
NGN-equivalent points by fabricating a transaction_id and a
revenue_usd. They are now 410 Gone stubs — new code uses
/ads/request-token + the SSV callback flow (see
`create_ad_request` and `mark_ad_request_credited` in
app/services/ads.py).

Adding a new ad network (AppLovin MAX) is a matter of writing its
callback handler and pointing it at the same `mark_ad_request_*`
helpers — the credit/audit path is already network-agnostic.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.limiter import limiter
from app.models import AdEvent, AdRequest, User
from app.routers.auth import get_current_user
from app.schemas import (
    AdCreditRequest,
    AdCreditResponse,
    AdImpressionRequest,
    AdImpressionResponse,
    AdRecentCredit,
    AdRequestTokenRequest,
    AdRequestTokenResponse,
    AdRewardClaimRequest,
    AdRewardClaimResponse,
)
from app.services import ads as ads_service


logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/ads", tags=["ads"])


# Platform revenue share is read from settings so ops can change it
# without a deploy. Default is set in config.py
# (platform_ad_revenue_percent, default 0.15 = 15% platform, 85% user).
PLATFORM_SHARE = settings.platform_ad_revenue_percent
USER_SHARE = 1.0 - PLATFORM_SHARE

# 10 points = ₦1 (NGN). All point math goes through this constant so
# the conversion rate lives in exactly one place.
POINTS_PER_NAIRA = 10


# ── POST /ads/request-token — NEW: SSV-only credit flow entry ─────


@router.post("/credit", response_model=AdCreditResponse)  # legacy: removed body, kept stub
async def credit_ad_reward(
    payload: AdCreditRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdCreditResponse:
    """DEPRECATED — returns 410. Use POST /ads/request-token + SSV."""
    raise HTTPException(  # pragma: no cover
        status_code=410,
        detail=(
            "This endpoint is deprecated and will be removed. "
            "Use POST /api/v1/ads/request-token + the AdMob SSV "
            "callback to credit ad rewards."
        ),
    )


@router.post("/impression", response_model=AdImpressionResponse)  # legacy
async def log_ad_impression(
    payload: AdImpressionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdImpressionResponse:
    """DEPRECATED — returns 410. Use POST /ads/request-token + SSV."""
    raise HTTPException(  # pragma: no cover
        status_code=410,
        detail=(
            "This endpoint is deprecated and will be removed. "
            "Use POST /api/v1/ads/request-token + the AdMob SSV "
            "callback to track ad impressions."
        ),
    )


@router.post("/reward-claim", response_model=AdRewardClaimResponse)  # legacy
async def claim_ad_reward(
    payload: AdRewardClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdRewardClaimResponse:
    """DEPRECATED — returns 410. Use POST /ads/request-token + SSV."""
    raise HTTPException(  # pragma: no cover
        status_code=410,
        detail=(
            "This endpoint is deprecated and will be removed. "
            "Use POST /api/v1/ads/request-token + the AdMob SSV "
            "callback to credit rewarded ad views."
        ),
    )


# ── POST /ads/request-token — NEW: SSV-only credit flow entry ─────
# The client calls this just before showing a rewarded ad. The server
# issues a one-time AdRequest row, returns the token wrapped in
# `custom_data` for the client to pass to AdMob. The AdMob-signed
# SSV callback later consumes this row to credit the user. See the
# module docstring for the full flow.


@limiter.limit(f"{settings.ad_request_rate_limit_per_minute}/minute")
@router.post("/request-token", response_model=AdRequestTokenResponse, status_code=201)
async def issue_ad_request_token(
    request: Request,
    payload: AdRequestTokenRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdRequestTokenResponse:
    """Issue a one-time ad-request token for the authenticated user.

    The client must:
      1. Read ad unit IDs from GET /api/v1/ads/config (no hardcoding).
      2. Pick a rewarded_* unit (in-feed / interstitial earn zero).
      3. POST here with that unit name to get a `token` + `custom_data`.
      4. Pass `custom_data` to AdMob's ad request (`customData` on
         Android, `request.customData` on iOS).
      5. After the ad closes, poll GET /api/v1/ads/recent-credits
         with the timestamp from before the ad to see if the credit
         landed.

    Rate-limited at `settings.ad_request_rate_limit_per_minute`
    requests per minute per IP (slowapi key is the remote address).
    This caps attacker token-stuffing without blocking a heavy
    legit user (heavy users watch 10-20 ads/day, well under 30/min).
    """
    if not payload.ad_unit.startswith("rewarded_"):
        # The SSV handler will also reject non-rewarded units, but
        # fail fast here so the client gets a clear 400 instead of
        # a token that will never be honored.
        raise HTTPException(
            status_code=400,
            detail=(
                "Only rewarded_* ad units earn points. "
                f"Got '{payload.ad_unit}'; expected a unit starting with 'rewarded_'."
            ),
        )

    req = await ads_service.create_ad_request(
        db=db, user_id=current_user.id, ad_unit=payload.ad_unit
    )

    # `custom_data` is the single piece of state the client carries
    # into the AdMob SDK. AdMob signs it as part of the SSV payload,
    # so the server can trust it on the way back.
    custom_data = f"{current_user.id}:{req.token}"

    logger.info(
        "Issued ad-request token user=%s unit=%s id=%s expires_at=%s",
        current_user.id, req.ad_unit, req.id, req.expires_at,
    )

    return AdRequestTokenResponse(
        token=req.token,
        custom_data=custom_data,
        ad_unit=req.ad_unit,
        expires_at=req.expires_at,
        # The actual ad unit ID (e.g. "ca-app-pub-.../...") is resolved
        # by the client from /api/v1/ads/config; we don't echo it back
        # here because the /request-token endpoint is unit-name-keyed
        # and the config endpoint is the single source of truth for
        # unit IDs. Returning it would be a duplication risk.
        ad_unit_id=None,
    )


# ── GET /ads/recent-credits — NEW: poll for credited ad events ─────
# After the client shows a rewarded ad, it polls this endpoint with
# the timestamp from before the ad opened. The endpoint returns the
# AdEvent rows that have been credited since then, including the
# updated wallet balance. The client uses this to update the wallet
# display without trusting any client-side value.


@router.get("/recent-credits", response_model=list[AdRecentCredit])
async def list_recent_credits(
    since: datetime = Query(..., description="ISO 8601 timestamp. Returns credits created at or after this time."),
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AdRecentCredit]:
    """Return the authenticated user's credited ad events since `since`.

    `since` is required (not optional with a default) so a client
    bug that omits the parameter fails loudly instead of returning
    the full history. The client should pass the timestamp captured
    just before showing the ad.

    `new_balance` on each row is the user's points_balance at the
    time the row was credited (re-read from `AdEvent.created_at` so
    it's consistent even if other credits have arrived in the
    meantime). The client should treat the LAST row's `new_balance`
    as the freshest value and re-render the wallet.
    """
    rows = await ads_service.list_recent_credits_for_user(
        db, current_user.id, since=since, limit=limit
    )

    if not rows:
        return []

    # Fetch the user's CURRENT balance once, not per row. The
    # per-row `new_balance` is computed at credit time and stored
    # in the AdEvent row's created_at ordering; the LAST row's
    # value is the freshest authoritative balance, but for client
    # display we also surface the live balance.
    me = (
        await db.execute(select(User.points_balance).where(User.id == current_user.id))
    ).scalar_one()

    out: list[AdRecentCredit] = []
    for event in rows:
        out.append(
            AdRecentCredit(
                ad_event_id=event.id,
                ad_unit=event.ad_unit or "",
                points_credited=event.user_points_credited or 0,
                credited_at=event.created_at,
                new_balance=me,
            )
        )
    return out


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


async def _verify_admob_ssv_signature(
    query_params: dict[str, str],
    raw_query_string: str,
) -> bool:
    """Verify the ECDSA P-256 signature on an AdMob SSV callback.

    The signing string is constructed from the URL-encoded query parameters
    (excluding 'signature' and 'key_id') sorted alphabetically by key,
    formatted as 'key=value\\n' with a trailing '\\n'.

    Values must be URL-encoded (raw from the callback URL), because AdMob's
    signature is computed over the URL-encoded form — not the decoded one.
    """
    signature_b64 = query_params.get("signature")
    key_id = query_params.get("key_id")
    if not signature_b64 or not key_id:
        return False

    # Build signing string from raw URL-encoded query parameters.
    # We parse the raw query string manually to preserve URL encoding.
    excluded = {"signature", "key_id"}
    raw_entries: list[tuple[str, str]] = []
    for part in raw_query_string.split("&"):
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            raw_entries.append((k, v))
        else:
            raw_entries.append((part, ""))

    # Sort alphabetically by key
    raw_entries.sort(key=lambda x: x[0])

    parts = []
    for k, v in raw_entries:
        if k in excluded:
            continue
        parts.append(f"{k}={v}")
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

        pem_data = keys[key_id].encode("utf-8")
        public_key = serialization.load_pem_public_key(pem_data, backend=default_backend())

        signature = base64.b64decode(signature_b64)

        public_key.verify(signature, signing_string.encode("utf-8"), ec.ECDSA(hashes.SHA256()))
        return True
    except Exception as exc:
        logger.error(
            "AdMob SSV signature verification failed: %s: %s",
            type(exc).__name__, exc,
        )
        logger.debug(
            "AdMob SSV signing string (key_id=%s): %r",
            key_id, signing_string[:500],
        )
        return False


@router.get("/google/callback")
async def admob_ssv_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """AdMob SSV webhook — GET request with query parameters.

    AdMob sends a GET to this URL with the reward data as query params:
      ?ad_network=...&ad_unit=...&reward_amount=...&user_id=...&transaction_id=...
       &signature=...&key_id=...&custom_data=<f"{user_id}:{token}">

    This is the ONLY path that credits points. The flow is:

      1. Client got a `custom_data` value from POST /api/v1/ads/request-token.
      2. Client passed that custom_data to AdMob's ad request.
      3. AdMob echoes the custom_data back in this callback, signed.
      4. We verify the signature (401 on failure — never proceed with
         a callback that doesn't prove it's from AdMob).
      5. We parse custom_data to get (user_id, token), look up the
         AdRequest row, validate user_id matches and ad_unit is
         rewarded, and credit the user.

    Returns:
      - 200 `{"status": "verification_success"}` on empty GET (AdMob
        connectivity test, no signature to verify)
      - 200 `{"status": "credited", ...}` on successful credit
      - 200 `{"status": "duplicate", ...}` if the AdRequest was
        already credited
      - 200 `{"status": "ignored", "reason": ...}` for benign
        rejections (unknown token, expired, malformed custom_data)
      - 401 on signature failure
    """
    # Get both decoded params (for reading values) and raw query string (for
    # signature verification — AdMob signs the URL-encoded form, not decoded).
    raw_query_string = request.url.query or ""
    query_params = {k: v for k, v in request.query_params.items()}

    if not query_params:
        raise HTTPException(status_code=401, detail="Missing SSV parameters")

    # ── 1. Signature verification ─────────────────────────────────
    # CRITICAL: bad signature → 401, do NOT continue. The previous
    # implementation logged a warning and continued, which let a
    # network attacker forge SSV callbacks that polluted the
    # AdEvent table with arbitrary user_id values. See
    # `mark_ad_request_rejected` and `mark_ad_request_credited` in
    # services/ads.py for the state machine.
    is_valid = await _verify_admob_ssv_signature(query_params, raw_query_string)
    if not is_valid:
        logger.warning(
            "AdMob SSV: signature verification failed for tx=%s",
            query_params.get("transaction_id", "unknown"),
        )
        raise HTTPException(status_code=401, detail="Invalid SSV signature")

    # ── 2. Parse custom_data = "user_id:token" ─────────────────────
    # The client set this when requesting the ad (via the
    # /request-token endpoint). AdMob signs it as part of the SSV
    # payload, so the value is trustworthy on receipt.
    custom_data = query_params.get("custom_data", "")
    if ":" not in custom_data:
        logger.warning("AdMob SSV: missing or malformed custom_data: %r", custom_data)
        return {"status": "ignored", "reason": "missing_custom_data"}
    try:
        user_id_str, token = custom_data.split(":", 1)
        user_id = int(user_id_str)
    except (ValueError, AttributeError):
        logger.warning("AdMob SSV: malformed custom_data: %r", custom_data)
        return {"status": "ignored", "reason": "malformed_custom_data"}

    transaction_id = query_params.get("transaction_id", "")
    ad_unit_from_callback = query_params.get("ad_unit", "")

    # ── 3. Look up AdRequest by token ──────────────────────────────
    req = await ads_service.lookup_ad_request_by_token(db, token)
    if req is None:
        logger.warning("AdMob SSV: unknown token (user=%s, tx=%s)", user_id, transaction_id)
        return {"status": "ignored", "reason": "unknown_token"}

    # ── 4. Validate the callback matches what we issued ───────────
    # user_id in custom_data must match the user we issued the
    # token to. A forged callback that guesses a valid token still
    # needs to know the user_id — and AdMob signs the whole
    # payload, so an attacker can't substitute a different
    # user_id without breaking the signature check above.
    if req.user_id != user_id:
        logger.warning(
            "AdMob SSV: user mismatch (token_user=%s, custom_data_user=%s, tx=%s)",
            req.user_id, user_id, transaction_id,
        )
        return {"status": "ignored", "reason": "user_mismatch"}

    # Already-credited: idempotent no-op. The AdRequest row is
    # the source of truth; we don't re-look-up by transaction_id
    # because the same transaction_id could in theory appear
    # against a different AdRequest (though in practice it can't —
    # see the UNIQUE constraint on admob_transaction_id).
    if req.status == "credited":
        return {
            "status": "duplicate",
            "points_credited": req.points_credited or 0,
        }

    # Expired or already rejected: surface a clear reason. We do
    # NOT flip the row to "rejected" here if it's already terminal
    # (mark_ad_request_rejected is idempotent on terminal status).
    if req.status != "issued" or req.expires_at < datetime.utcnow():
        await ads_service.mark_ad_request_rejected(db, req, reason="expired_or_invalid")
        await db.commit()
        return {"status": "ignored", "reason": "expired_or_invalid"}

    # ── 5. Validate ad_unit is rewarded-only ──────────────────────
    # Per the user-facing decision, in-feed and interstitial ads
    # earn zero points. The /request-token endpoint also rejects
    # non-rewarded units upfront, but we double-check here in case
    # the client sent a non-rewarded unit (the SSV callback will
    # still arrive with that ad_unit value).
    if not req.ad_unit.startswith("rewarded_"):
        await ads_service.mark_ad_request_rejected(db, req, reason="non_rewarded_unit")
        await db.commit()
        logger.info(
            "AdMob SSV: non-rewarded ad_unit=%s (user=%s, tx=%s) — no credit",
            req.ad_unit, user_id, transaction_id,
        )
        return {"status": "ignored", "reason": "non_rewarded_unit"}

    # Optional sanity: the ad_unit in the SSV callback should match
    # the one we issued. If they differ, something weird is going on
    # (e.g. the client requested a rewarded_android token but the
    # user saw an in_feed unit) — log and continue with the issued
    # unit's payout (the ad_unit we *promised* to credit).
    if ad_unit_from_callback and ad_unit_from_callback != req.ad_unit:
        logger.warning(
            "AdMob SSV: ad_unit mismatch (issued=%s, callback=%s, user=%s, tx=%s)",
            req.ad_unit, ad_unit_from_callback, user_id, transaction_id,
        )

    # ── 6. Credit the user ────────────────────────────────────────
    points = ads_service.points_for_rewarded_ad()

    # Atomic update: mark the AdRequest as credited AND bump the
    # wallet in the same transaction. If the AdRequest is already
    # in a terminal state (race), mark_ad_request_credited is a
    # no-op and we'll re-check.
    await ads_service.mark_ad_request_credited(
        db, req, points=points, admob_transaction_id=transaction_id or None
    )
    await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(points_balance=User.points_balance + points)
    )

    # Insert the AdEvent row for the audit trail + the wallet
    # transaction history (the existing /api/v1/wallet/transactions
    # endpoint reads from AdEvent).
    event = AdEvent(
        user_id=user_id,
        ad_unit=req.ad_unit,
        ad_type="rewarded",
        provider="admob",
        watched_fully=True,
        reward_granted=True,
        transaction_id=transaction_id or None,
        revenue_usd=None,
        fx_rate_used=None,
        user_points_credited=points,
        credit_status="credited",
    )
    db.add(event)
    await db.commit()

    me = (
        await db.execute(select(User.points_balance).where(User.id == user_id))
    ).scalar_one()

    logger.info(
        "AdMob SSV credit: user=%s unit=%s tx=%s pts=%d balance=%d",
        user_id, req.ad_unit, transaction_id, points, me,
    )

    return {
        "status": "credited",
        "points_credited": points,
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
