"""Bills & Earn endpoints (Phase 8).

Users buy airtime, data, electricity, or cable TV subscriptions and earn
points back from the aggregator's commission — the platform never funds
rewards from its own pocket.

Flow for every purchase:
  1. User requests a purchase (phone/meter, amount, network)
  2. Backend debits the user's wallet for the amount
  3. Backend calls Peyflex to fulfill the purchase
  4. Peyflex pays a commission (varies by service)
  5. Backend splits the commission: user gets points, platform keeps the rest
  6. Backend records the BillTransaction row
  7. User receives the service + points

Real Peyflex API: https://client.peyflex.com.ng/api/
Reference: https://documenter.getpostman.com/view/17835214/2sB34imLMn
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update

from app.config import settings
from app.database import get_db
from app.models import BillTransaction, User
from app.routers.auth import get_current_user
from app.schemas import (
    AirtimePurchaseRequest,
    AirtimePurchaseResponse,
    DataPurchaseRequest,
    ElectricityPurchaseRequest,
    TelevisionPurchaseRequest,
    BillsPurchaseResponse,
)
from app.services.peyflex import get_client, get_public_client, PeyflexError

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/bills", tags=["bills"])

_USER_SHARE = settings.bills_user_share  # default 0.67

# Points conversion: 100 points = ₦1
_POINTS_PER_NAIRA = 100


def _compute_points(commission_kobo: int) -> int:
    """Compute user's point share from a commission amount in kobo.
    
    The commission comes from Peyflex's `discount` field in the API response,
    which reflects the real-time discount rate for your account tier:
    - Free API tier: 0.5-3% depending on service
    - Top Reseller tier: 1-6% (higher earnings for your users)
    
    Users receive 67% of the commission as points (100 pts = ₦1).
    Platform keeps 33% to cover infrastructure costs.
    """
    user_share_kobo = int(commission_kobo * _USER_SHARE)
    return user_share_kobo * _POINTS_PER_NAIRA // 100


def _generate_reference() -> str:
    return f"BILL-{uuid.uuid4().hex[:12].upper()}"


# ── Airtime ──────────────────────────────────────────────────────────


@router.get("/airtime/networks")
async def list_airtime_networks():
    """List airtime networks available on Peyflex."""
    try:
        nets = await get_public_client().get_airtime_networks()
        return [{"id": n.id, "name": n.name} for n in nets]
    except PeyflexError as exc:
        logger.error("Failed to fetch airtime networks: %s", exc)
        # Fallback to known networks
        return [
            {"id": "mtn", "name": "MTN"},
            {"id": "airtel", "name": "AIRTEL"},
            {"id": "glo", "name": "GLO"},
        ]


@router.post("/airtime", response_model=AirtimePurchaseResponse)
async def buy_airtime(
    payload: AirtimePurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AirtimePurchaseResponse:
    """Buy airtime and earn points from the commission."""
    reference = _generate_reference()
    amount_kobo = payload.amount_naira * 100

    # 1. Debit wallet
    if current_user.points_balance < amount_kobo:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance - amount_kobo)
    )

    # 2. Call Peyflex
    try:
        result = await get_client().buy_airtime(
            network=payload.network,
            mobile_number=payload.phone,
            amount=payload.amount_naira,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex airtime failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if result.status != "success":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {result.message}")

    # Extract real commission from Peyflex's discount field.
    # This reflects your actual account tier discount (Free API: 1%, Top Reseller: 2%).
    # If discount is missing or invalid, fall back to 0 commission.
    try:
        commission_kobo = int(float(result.discount) * 100)
    except (ValueError, TypeError):
        logger.warning("Peyflex airtime discount field missing or invalid: %s", result.discount)
        commission_kobo = 0

    points = _compute_points(commission_kobo)

    # 4. Record transaction and credit points
    tx = BillTransaction(
        user_id=current_user.id,
        service="airtime",
        provider="peyflex",
        phone=payload.phone,
        amount_naira=payload.amount_naira,
        commission_naira=commission_kobo,
        points_earned=points,
        reference=reference,
        status="success",
        external_ref=result.reference,
    )
    db.add(tx)

    new_balance = current_user.points_balance - amount_kobo + points
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance + points)
    )
    await db.commit()

    return AirtimePurchaseResponse(
        reference=reference,
        phone=payload.phone,
        amount_naira=payload.amount_naira,
        network=payload.network,
        commission_naira=commission_kobo,
        points_earned=points,
        new_balance=new_balance,
        status="success",
    )


# ── Data ──────────────────────────────────────────────────────────────

@router.get("/data/networks")
async def list_data_networks():
    """List data networks available on Peyflex."""
    try:
        nets = await get_public_client().get_data_networks()
        return [{"identifier": n.identifier, "name": n.name} for n in nets]
    except PeyflexError as exc:
        logger.error("Failed to fetch data networks: %s", exc)
        # Fallback
        return [
            {"identifier": "mtn_gifting_data", "name": "MTN (Gifting)"},
            {"identifier": "mtn_data_share", "name": "MTN (Data Share)"},
            {"identifier": "glo_data", "name": "GLO DATA"},
            {"identifier": "airtel_data", "name": "AIRTEL (GIFTING)"},
            {"identifier": "9mobile_data", "name": "9MOBILE"},
            {"identifier": "9mobile_gifting", "name": "9MOBILE (GIFTING)"},
        ]


# Fallback plans (from Peyflex API docs response samples) used when the
# live API is unreachable (e.g. Cloudflare block). These match the real
# plan_code values Peyflex expects.
_FALLBACK_PLANS: dict[str, list[dict]] = {
    "mtn_gifting_data": [
        {"plan_code": "M110MBS", "amount": 150, "label": "110MB = N150 (1DAY)"},
        {"plan_code": "M200MBS", "amount": 155, "label": "200MB = N155 (1DAY)"},
        {"plan_code": "M205GBS", "amount": 650, "label": "2.5GB = N650 (2DAYS)"},
        {"plan_code": "M2GBS", "amount": 800, "label": "2GB = N800 (2DAYS)"},
        {"plan_code": "M1GBS", "amount": 826, "label": "1GB = N826 (7DAYS)"},
        {"plan_code": "M2GBS", "amount": 1505, "label": "2GB = N1505 (1MONTH)"},
        {"plan_code": "M2m5GBS", "amount": 2500, "label": "2.5GB = N2500 (1MONTH)"},
        {"plan_code": "M6GBS", "amount": 2500, "label": "6GB = N2500 (WEEKLY)"},
        {"plan_code": "M11GBS", "amount": 3500, "label": "11GB = N3500 (WEEKLY)"},
        {"plan_code": "M10GBS", "amount": 4485, "label": "10GB = N4485 (1MONTH)"},
        {"plan_code": "M20GBS", "amount": 7500, "label": "20GB = N7500 (1MONTH)"},
        {"plan_code": "M25GBS", "amount": 8900, "label": "25GB = N8900 (1MONTH)"},
    ],
    "mtn_data_share": [
        {"plan_code": "M1GBS", "amount": 500, "label": "1GB = N500 (7 Days)"},
        {"plan_code": "M2GBS", "amount": 800, "label": "2GB = N800 (2 Days)"},
    ],
    "glo_data": [
        {"plan_code": "G500MBS", "amount": 240, "label": "500MB = N240 (1DAY)"},
        {"plan_code": "G1GBS", "amount": 264, "label": "1GB = N264 (1MONTH)"},
        {"plan_code": "G3GBS", "amount": 833, "label": "3GB = N833 (1MONTH)"},
        {"plan_code": "G5GBS", "amount": 1352, "label": "5GB = N1352 (1MONTH)"},
        {"plan_code": "G10GBS", "amount": 3234, "label": "10GB = N3234 (1MONTH)"},
    ],
    "airtel_data": [
        {"plan_code": "A600MBS", "amount": 287, "label": "600MB = N287 (1DAY)"},
        {"plan_code": "A1GBS", "amount": 346, "label": "1GB = N346 (1MONTH)"},
        {"plan_code": "A2GBS", "amount": 742, "label": "2GB = N742 (1MONTH)"},
        {"plan_code": "A3GBS", "amount": 1039, "label": "3GB = N1039 (1MONTH)"},
        {"plan_code": "A5GBS", "amount": 2450, "label": "5GB = N2450 (1MONTH)"},
        {"plan_code": "A10GBS", "amount": 2920, "label": "10GB = N2920 (1MONTH)"},
    ],
    "9mobile_data": [
        {"plan_code": "E500MBS", "amount": 294, "label": "500MB = N294 (1MONTH)"},
        {"plan_code": "E1GBS", "amount": 490, "label": "1GB = N490 (1MONTH)"},
        {"plan_code": "E2GBS", "amount": 960, "label": "2GB = N960 (1MONTH)"},
        {"plan_code": "E3GBS", "amount": 1470, "label": "3GB = N1470 (1MONTH)"},
        {"plan_code": "E5GBS", "amount": 2450, "label": "5GB = N2450 (1MONTH)"},
        {"plan_code": "E10GBS", "amount": 4900, "label": "10GB = N4900 (1MONTH)"},
    ],
    "9mobile_gifting": [
        {"plan_code": "EG500MBS", "amount": 294, "label": "500MB = N294 (1MONTH)"},
        {"plan_code": "EG1GBS", "amount": 490, "label": "1GB = N490 (1MONTH)"},
        {"plan_code": "EG5GBS", "amount": 2450, "label": "5GB = N2450 (1MONTH)"},
    ],
}


@router.get("/data/plans")
async def list_data_plans(network: str = "mtn_gifting_data"):
    """List data plans for a specific network."""
    try:
        plans = await get_public_client().get_data_plans(network)
        return [
            {"plan_code": p.plan_code, "amount": p.amount, "label": p.label}
            for p in plans
        ]
    except PeyflexError as exc:
        logger.error("Failed to fetch data plans for %s: %s", network, exc)
        fallback = _FALLBACK_PLANS.get(network, [])
        if fallback:
            return fallback
        raise HTTPException(status_code=502, detail="Failed to load data plans")


@router.post("/data", response_model=BillsPurchaseResponse)
async def buy_data(
    payload: DataPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillsPurchaseResponse:
    """Buy data bundle and earn points."""
    reference = _generate_reference()

    # Fetch plan price to know how much to charge
    try:
        plans = await get_client().get_data_plans(payload.network)
    except PeyflexError as exc:
        logger.error("Failed to fetch plans for pricing: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to get plan pricing")

    plan = next((p for p in plans if p.plan_code == payload.plan_code), None)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {payload.plan_code}")

    price_naira = plan.amount
    amount_kobo = price_naira * 100

    if current_user.points_balance < amount_kobo:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance - amount_kobo)
    )

    try:
        result = await get_client().buy_data(
            network=payload.network,
            mobile_number=payload.phone,
            plan_code=payload.plan_code,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex data failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if result.status != "success":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {result.message}")

    # Extract real commission from Peyflex's discount field.
    # This reflects your actual account tier discount (Free API: 0.5-3%, Top Reseller: 1-6%).
    try:
        commission_kobo = int(float(result.discount) * 100)
    except (ValueError, TypeError):
        logger.warning("Peyflex data discount field missing or invalid: %s", result.discount)
        commission_kobo = 0

    points = _compute_points(commission_kobo)

    tx = BillTransaction(
        user_id=current_user.id,
        service="data",
        provider="peyflex",
        phone=payload.phone,
        amount_naira=price_naira,
        commission_naira=commission_kobo,
        points_earned=points,
        reference=reference,
        status="success",
        external_ref=result.reference,
    )
    db.add(tx)

    new_balance = current_user.points_balance - amount_kobo + points
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance + points)
    )
    await db.commit()

    return BillsPurchaseResponse(
        reference=reference,
        commission_naira=commission_kobo,
        points_earned=points,
        new_balance=new_balance,
        status="success",
        phone=payload.phone,
        customer_name=result.plan,
    )


# ── Electricity ─────────────────────────────────────────────────────

@router.get("/electricity/plans")
async def list_electricity_plans():
    """List electricity DISCOs available on Peyflex."""
    try:
        return await get_public_client().get_electricity_plans()
    except PeyflexError as exc:
        logger.error("Failed to fetch electricity plans: %s", exc)
        return [
            {"plan_id": "ikeja-electric", "plan_code": "ikeja-electric", "plan_name": "Ikeja Electricity Distribution", "min_amount": 500, "max_amount": 1000000},
            {"plan_id": "abuja-electric", "plan_code": "abuja-electric", "plan_name": "Abuja Electricity Distribution", "min_amount": 900, "max_amount": 1000000},
            {"plan_id": "eko-electric", "plan_code": "eko-electric", "plan_name": "Eko Electricity Distribution", "min_amount": 1000, "max_amount": 100000},
            {"plan_id": "ibadan-electric", "plan_code": "ibadan-electric", "plan_name": "Ibadan Electricity Distribution", "min_amount": 2000, "max_amount": 500000},
            {"plan_id": "portharcourt-electric", "plan_code": "portharcourt-electric", "plan_name": "Portharcourt Electricity Distribution", "min_amount": 100, "max_amount": 10000000},
            {"plan_id": "kano-electric", "plan_code": "kano-electric", "plan_name": "Kano Electricity Distribution", "min_amount": 500, "max_amount": 500000},
            {"plan_id": "kaduna-electric", "plan_code": "kaduna-electric", "plan_name": "Kaduna Electricity Distribution", "min_amount": 1100, "max_amount": 100000},
            {"plan_id": "jos-electric", "plan_code": "jos-electric", "plan_name": "Jos Electricity Distribution", "min_amount": 1000, "max_amount": 500000},
            {"plan_id": "enugu-electric", "plan_code": "enugu-electric", "plan_name": "Enugu Electricity Distribution", "min_amount": 500, "max_amount": 500000},
            {"plan_id": "benin-electric", "plan_code": "benin-electric", "plan_name": "Benin Electricity Distribution", "min_amount": 500, "max_amount": 500000},
            {"plan_id": "yola-electric", "plan_code": "yola-electric", "plan_name": "Yola Electricity Distribution", "min_amount": 500, "max_amount": 500000},
            {"plan_id": "aba-electric", "plan_code": "aba-electric", "plan_name": "Aba Electricity Distribution", "min_amount": 100, "max_amount": 400000},
        ]


@router.post("/electricity")
async def buy_electricity(
    payload: ElectricityPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Buy electricity tokens and earn points."""
    reference = _generate_reference()
    amount_kobo = payload.amount_naira * 100

    if current_user.points_balance < amount_kobo:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance - amount_kobo)
    )

    try:
        result = await get_client().buy_electricity(
            plan=payload.plan_id,
            meter=payload.meter_number,
            amount=payload.amount_naira,
            meter_type=payload.meter_type,
            phone=payload.phone,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex electricity failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if result.get("status") != "SUCCESS":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {result.get('message', 'Unknown')}")

    # Extract real commission from Peyflex's response.
    # Electricity has very low commission (Free API: 0.1%, Top Reseller: 0.5%).
    # Peyflex may return this in 'discount', 'charged', or a computed field.
    commission_kobo = 0
    try:
        # Try to extract discount if available
        if "discount" in result and result["discount"]:
            commission_kobo = int(float(result["discount"]) * 100)
        elif "charged" in result and result["charged"]:
            # Some APIs return charged = amount - discount
            charged = float(result["charged"])
            commission_kobo = int((payload.amount_naira - charged) * 100)
    except (ValueError, TypeError, KeyError) as e:
        logger.warning("Could not extract electricity commission from response: %s. Error: %s", result, e)
        commission_kobo = 0

    points = _compute_points(commission_kobo)

    tx = BillTransaction(
        user_id=current_user.id,
        service="electricity",
        provider="peyflex",
        meter_number=payload.meter_number,
        amount_naira=payload.amount_naira,
        commission_naira=commission_kobo,
        points_earned=points,
        reference=reference,
        status="success",
        external_ref=result.get("reference", ""),
    )
    db.add(tx)

    new_balance = current_user.points_balance - amount_kobo + points
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance + points)
    )
    await db.commit()

    return {
        "reference": reference,
        "commission_naira": commission_kobo,
        "points_earned": points,
        "new_balance": new_balance,
        "status": "success",
        "meter_number": payload.meter_number,
        "token": result.get("token", ""),
    }


# ── Cable TV ────────────────────────────────────────────────────────

@router.get("/tv/providers")
async def list_tv_providers():
    """List cable TV providers available on Peyflex."""
    try:
        return await get_public_client().get_cable_providers()
    except PeyflexError:
        return [
            {"identifier": "dstv", "name": "DSTV"},
            {"identifier": "gotv", "name": "GOTV"},
            {"identifier": "startimes", "name": "Startimes"},
        ]


@router.get("/tv/plans")
async def list_tv_plans(provider: str = "dstv"):
    """List cable TV plans for a provider."""
    try:
        return await get_public_client().get_cable_plans(provider)
    except PeyflexError as exc:
        logger.error("Failed to fetch TV plans for %s: %s", provider, exc)
        raise HTTPException(status_code=502, detail="Failed to load TV plans")


@router.post("/tv")
async def buy_tv(
    payload: TelevisionPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Subscribe cable TV and earn points."""
    reference = _generate_reference()

    # Fetch plan price
    try:
        plans = await get_client().get_cable_plans(payload.provider)
    except PeyflexError as exc:
        logger.error("Failed to fetch TV plans for pricing: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to get plan pricing")

    plan = next((p for p in plans if p.get("plan_code") == payload.plan_code), None)
    if not plan:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {payload.plan_code}")

    price_naira = int(float(plan["amount"]))
    amount_kobo = price_naira * 100

    if current_user.points_balance < amount_kobo:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance - amount_kobo)
    )

    try:
        result = await get_client().buy_cable(
            identifier=payload.provider,
            plan=payload.plan_code,
            iuc=payload.smartcard_number,
            phone=payload.phone,
            amount=price_naira,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex TV failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if result.get("status") != "SUCCESS":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {result.get('message', 'Unknown')}")

    # Extract real commission from Peyflex's response.
    # Cable TV commission varies: DStv/GOtv 0.1%, Startimes 0.5% (Free API tier).
    # Top Reseller: 0.5% for all providers.
    commission_kobo = 0
    try:
        # Try to extract discount if available
        if "discount" in result and result["discount"]:
            commission_kobo = int(float(result["discount"]) * 100)
        elif "charged" in result and result["charged"]:
            # Some APIs return charged = amount - discount
            charged = float(result["charged"])
            commission_kobo = int((price_naira - charged) * 100)
    except (ValueError, TypeError, KeyError) as e:
        logger.warning("Could not extract TV commission from response: %s. Error: %s", result, e)
        commission_kobo = 0

    points = _compute_points(commission_kobo)

    tx = BillTransaction(
        user_id=current_user.id,
        service="tv",
        provider="peyflex",
        smartcard_number=payload.smartcard_number,
        amount_naira=price_naira,
        commission_naira=commission_kobo,
        points_earned=points,
        reference=reference,
        status="success",
        external_ref=result.get("reference", ""),
    )
    db.add(tx)

    new_balance = current_user.points_balance - amount_kobo + points
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance + points)
    )
    await db.commit()

    return {
        "reference": reference,
        "commission_naira": commission_kobo,
        "points_earned": points,
        "new_balance": new_balance,
        "status": "success",
        "smartcard_number": payload.smartcard_number,
        "customer_name": result.get("customer_name", ""),
    }
