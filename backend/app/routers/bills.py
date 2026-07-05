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

_USER_SHARE = 0.70  # User gets 70%, platform keeps 30%

# Points conversion: 100 points = ₦1
_POINTS_PER_NAIRA = 100


def _compute_points(commission_kobo: int) -> int:
    """Compute user's point share from a commission amount in kobo.
    
    The commission comes from Peyflex's `discount` field in the API response,
    which reflects the real-time discount rate for your account tier:
    - Free API tier: 0.5-3% depending on service
    - Top Reseller tier: 1-6% (higher earnings for your users)
    
    Users receive 70% of the commission as points (100 pts = ₦1).
    Platform keeps 30% to cover infrastructure costs.
    """
    user_share_kobo = int(commission_kobo * _USER_SHARE)
    return user_share_kobo * _POINTS_PER_NAIRA // 100


def _generate_reference() -> str:
    return f"BILL-{uuid.uuid4().hex[:12].upper()}"


# ── Airtime ──────────────────────────────────────────────────────────


@router.get("/airtime/networks")
async def list_airtime_networks():
    """List airtime networks available on Peyflex."""
    nets = await get_public_client().get_airtime_networks()
    return [{"id": n.id, "name": n.name} for n in nets]


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
    nets = await get_public_client().get_data_networks()
    return [{"identifier": n.identifier, "name": n.name} for n in nets]


@router.get("/data/plans")
async def list_data_plans(network: str = "mtn_gifting_data"):
    """List data plans for a specific network."""
    plans = await get_public_client().get_data_plans(network)
    return [
        {"plan_code": p.plan_code, "amount": p.amount, "label": p.label}
        for p in plans
    ]


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
    return await get_public_client().get_electricity_plans()


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
    return await get_public_client().get_cable_providers()


@router.get("/tv/plans")
async def list_tv_plans(provider: str = "dstv"):
    """List cable TV plans for a provider."""
    return await get_public_client().get_cable_plans(provider)


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
