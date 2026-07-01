"""Payments router — Phase 4.

Premium subscription purchases via Paystack. Endpoints:

  POST /payments/initiate     — begin checkout (returns payment URL)
  POST /payments/webhook      — Paystack webhook (confirms payment, upgrades tier)
  GET  /payments/tiers        — list available tiers + prices (OTA-configurable)
  GET  /payments/tier-info    — user's current tier + expiry
"""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import User, Payment, UserTier
from app.routers.auth import get_current_user
from app.schemas import (
    PaymentInitiateRequest,
    PaymentInitiateResponse,
    PaymentWebhookResponse,
    TierInfo,
    UserTierInfo,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/payments", tags=["payments"])

# ── Pricing tiers (OTA-tuned via app_config, but with sensible defaults) ──

TIER_PRICING = {
    "premium_monthly": {
        "display_name": "Premium Monthly",
        "price_kobo": 50_000,  # ₦500
        "duration_days": 30,
        "benefits": [
            "Unlimited study materials",
            "AI tutor available 24/7",
            "Ad-free reading",
            "Export study notes",
        ],
    },
    "premium_yearly": {
        "display_name": "Premium Yearly",
        "price_kobo": 500_000,  # ₦5,000 (2 months free)
        "duration_days": 365,
        "benefits": [
            "All monthly features",
            "Early access to new AI features",
            "Priority support",
            "2x study points multiplier",
        ],
    },
}


# ── Helpers ────────────────────────────────────────────────────────────


async def _get_tier_pricing(db: AsyncSession, tier: str) -> dict:
    """Fetch tier pricing from app_config or fall back to default."""
    # In production, we'd query app_config[f"tier.{tier}.price_kobo"]
    # For now, use hardcoded TIER_PRICING
    return TIER_PRICING.get(tier, TIER_PRICING["premium_monthly"])


def _compute_subscription_expiry(tier: str) -> datetime:
    """Calculate subscription expiry date."""
    duration = TIER_PRICING[tier].get("duration_days", 30)
    return datetime.now(timezone.utc) + timedelta(days=duration)


# ── GET /payments/tiers ────────────────────────────────────────────────


@router.get("/tiers", response_model=list[TierInfo])
async def list_tiers():
    """List available premium tiers (public endpoint, no auth required)."""
    return [
        TierInfo(
            tier=tier_key,
            display_name=tier_info["display_name"],
            price_kobo=tier_info["price_kobo"],
            duration_days=tier_info["duration_days"],
            benefits=tier_info["benefits"],
        )
        for tier_key, tier_info in TIER_PRICING.items()
    ]


# ── GET /payments/tier-info ────────────────────────────────────────────


@router.get("/tier-info", response_model=UserTierInfo)
async def get_tier_info(
    current_user: User = Depends(get_current_user),
):
    """Get user's current tier + expiry."""
    is_premium = current_user.tier != UserTier.FREE
    days_remaining = None
    
    if is_premium and current_user.subscription_expires_at:
        now = datetime.now(timezone.utc)
        delta = current_user.subscription_expires_at - now
        days_remaining = max(0, delta.days)
        if days_remaining == 0:
            # Expired
            is_premium = False
    
    return UserTierInfo(
        current_tier=current_user.tier.value,
        subscription_expires_at=current_user.subscription_expires_at,
        is_premium=is_premium,
        days_remaining=days_remaining,
    )


# ── POST /payments/initiate ────────────────────────────────────────────


@router.post("/initiate", response_model=PaymentInitiateResponse)
async def initiate_payment(
    payload: PaymentInitiateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a premium subscription purchase.
    
    Creates a Payment record in pending state, calls Paystack's
    checkout endpoint, returns the payment URL.
    """
    if not settings.paystack_secret_key:
        raise HTTPException(status_code=503, detail="Payments not configured")
    
    tier_pricing = await _get_tier_pricing(db, payload.tier)
    amount_kobo = tier_pricing["price_kobo"]
    
    # Generate unique reference for this payment
    provider_tx_ref = f"pp_{current_user.id}_{uuid.uuid4().hex[:8]}"
    
    # Create Payment record (pending)
    payment = Payment(
        user_id=current_user.id,
        tier=payload.tier,
        amount_kobo=amount_kobo,
        provider=payload.provider,
        provider_tx_ref=provider_tx_ref,
        status="pending",
    )
    db.add(payment)
    await db.commit()
    await db.refresh(payment)
    
    try:
        # Build Paystack inline checkout URL
        # Documentation: https://paystack.com/docs/payments/accept-payments/#inline
        paystack_base = "https://checkout.paystack.com"
        
        metadata = json.dumps({"user_id": current_user.id, "tier": payload.tier})
        params = {
            "key": settings.paystack_public_key,
            "email": current_user.email or current_user.phone or "",
            "amount": amount_kobo,
            "reference": provider_tx_ref,
            "metadata": metadata,
        }
        
        payment_url = f"{paystack_base}?{urlencode(params)}"
        
        return PaymentInitiateResponse(
            payment_url=payment_url,
            provider_tx_ref=provider_tx_ref,
            provider=payload.provider,
            amount_kobo=amount_kobo,
            tier=payload.tier,
        )
    
    except Exception as exc:
        logger.error("Payment initiate failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment initiation failed") from exc


# ── POST /payments/webhook ────────────────────────────────────────────


@router.post("/webhook", response_model=PaymentWebhookResponse)
async def handle_payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Receive Paystack webhook for payment confirmations.
    
    Validates signature, finds Payment record, and on success:
    - Sets status='success'
    - Updates user.tier + subscription_expires_at
    - Marks webhook_confirmed=True
    """
    # Get raw body for signature verification
    raw_body = await request.body()
    
    # Verify signature
    if not settings.paystack_webhook_secret:
        logger.warning("Paystack webhook secret not configured")
        return PaymentWebhookResponse(status="skipped", message="Webhook secret not configured")
    
    signature = request.headers.get("X-Paystack-Signature", "")
    expected_sig = hmac.new(
        settings.paystack_webhook_secret.encode(),
        raw_body,
        hashlib.sha512,
    ).hexdigest()
    
    if not hmac.compare_digest(signature, expected_sig):
        logger.warning("Webhook signature mismatch")
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook body")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    event = body.get("event", "")
    data = body.get("data", {})
    
    # Only handle charge.success
    if event != "charge.success":
        logger.info("Ignoring webhook event: %s", event)
        return PaymentWebhookResponse(status="ignored", message=f"Event {event} not handled")
    
    provider_tx_ref = data.get("reference")
    if not provider_tx_ref:
        logger.error("No reference in webhook data")
        raise HTTPException(status_code=400, detail="Missing reference")
    
    # Find Payment record
    result = await db.execute(
        select(Payment).where(Payment.provider_tx_ref == provider_tx_ref)
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        logger.warning("Payment not found for reference: %s", provider_tx_ref)
        return PaymentWebhookResponse(status="ignored", message="Payment not found")
    
    if payment.status == "success":
        logger.info("Payment already confirmed: %s", provider_tx_ref)
        return PaymentWebhookResponse(status="already_confirmed", message="Payment already processed")
    
    # Verify payment status from Paystack
    paystack_status = data.get("status", "").lower()
    if paystack_status != "success":
        # Payment failed or pending on Paystack side
        await db.execute(
            update(Payment)
            .where(Payment.id == payment.id)
            .values(status="failed", confirmed_at=datetime.now(timezone.utc))
        )
        await db.commit()
        logger.warning("Payment failed in Paystack: %s", provider_tx_ref)
        return PaymentWebhookResponse(status="failed", message="Payment failed in Paystack")
    
    # ✅ Payment successful — upgrade user's tier
    expiry = _compute_subscription_expiry(payment.tier)
    tier_enum = UserTier[payment.tier.upper()]  # Convert string to enum
    
    await db.execute(
        update(User)
        .where(User.id == payment.user_id)
        .values(
            tier=tier_enum,
            subscription_expires_at=expiry,
        )
    )
    
    await db.execute(
        update(Payment)
        .where(Payment.id == payment.id)
        .values(
            status="success",
            webhook_confirmed=True,
            confirmed_at=datetime.now(timezone.utc),
        )
    )
    
    await db.commit()
    
    logger.info("Payment confirmed and tier upgraded: user_id=%s tier=%s", payment.user_id, payment.tier)
    
    return PaymentWebhookResponse(status="confirmed", message="Payment confirmed and tier upgraded")
