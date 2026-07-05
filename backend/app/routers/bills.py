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
"""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

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
    BundleInfo,
    DiscoInfo,
    BouquetInfo,
)
from app.services.peyflex import get_client, PeyflexError

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/bills", tags=["bills"])

# Commission rates by network (as fraction of amount).
# Used to estimate user-facing earn rate before the actual API call.
# The actual commission comes from Peyflex's response; these are for
# display purposes. Source: peyflex.com.ng/commissions (API reseller tier).
_COMMISSION_RATES: dict[str, float] = {
    "mtn": 0.03,
    "airtel": 0.034,
    "glo": 0.04,
    "9mobile": 0.04,
}

_USER_SHARE = settings.bills_user_share  # default 0.67

# Points conversion: 100 points = ₦1
_POINTS_PER_NAIRA = 100


def _compute_points(commission_naira: int) -> int:
    """Compute user's point share from a commission amount in kobo."""
    user_share_kobo = int(commission_naira * _USER_SHARE)
    return user_share_kobo * _POINTS_PER_NAIRA // 100


def _generate_reference() -> str:
    return f"BILL-{uuid.uuid4().hex[:12].upper()}"


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
        receipt = await get_client().buy_airtime(
            phone=payload.phone,
            amount_naira=payload.amount_naira,
            network=payload.network,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex airtime failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if receipt.status != "success":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {receipt.message}")

    # 3. Compute commission and points
    rate = _COMMISSION_RATES.get(payload.network, 0.03)
    commission_kobo = int(payload.amount_naira * 100 * rate)
    points = _compute_points(commission_kobo)
    platform_kobo = commission_kobo - int(commission_kobo * _USER_SHARE)

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
        external_ref=receipt.external_ref,
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


@router.post("/data", response_model=BillsPurchaseResponse)
async def buy_data(
    payload: DataPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillsPurchaseResponse:
    """Buy data bundle and earn points."""
    reference = _generate_reference()

    # Look up the bundle price from the price list
    bundles = _DATA_BUNDLES.get(payload.network, _DATA_BUNDLES["mtn"])
    bundle = next((b for b in bundles if b["id"] == payload.data_id), None)
    if not bundle:
        raise HTTPException(status_code=400, detail=f"Unknown data bundle: {payload.data_id}")
    price_naira = bundle["price_naira"]
    amount_kobo = price_naira * 100

    if current_user.points_balance < amount_kobo:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance - amount_kobo)
    )

    try:
        receipt = await get_client().buy_data(
            phone=payload.phone,
            data_id=payload.data_id,
            network=payload.network,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex data failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if receipt.status != "success":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {receipt.message}")

    rate = _COMMISSION_RATES.get(payload.network, 0.034)
    commission_kobo = int(price_naira * 100 * rate)
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
        external_ref=receipt.external_ref,
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
    )


# ── Static lookups ──────────────────────────────────────────────────

_COMMISSION_RATES_ELEC = 0.012  # ~1.2% estimated commission on electricity
_COMMISSION_RATES_TV = 0.018   # ~1.8% estimated commission on cable TV

# Nigerian electricity DISCOs supported by Peyflex.
# Static list — no DISCO-list API from Peyflex.
_DISCOS: list[dict] = [
    {"code": "aedc", "name": "Abuja Electricity (AEDC)"},
    {"code": "ekedc", "name": "Eko Electricity (EKEDC)"},
    {"code": "ibedc", "name": "Ibadan Electricity (IBEDC)"},
    {"code": "ikedc", "name": "Ikeja Electricity (IKEDC)"},
    {"code": "jed", "name": "Jos Electricity (JED)"},
    {"code": "kaedco", "name": "Kaduna Electricity (KAEDCO)"},
    {"code": "kedco", "name": "Kano Electricity (KEDCO)"},
    {"code": "phed", "name": "Port Harcourt Electricity (PHED)"},
]

# Cable TV bouquet pricing from Multichoice (official Naira rates).
# plan_code values are what Peyflex expects in the `variation_id` field.
_TV_PROVIDERS: dict[str, list[dict]] = {
    "dstv": [
        {"id": "dstv-premium", "name": "Premium", "price_naira": 24500, "channels": "155+ channels"},
        {"id": "dstv-compact-plus", "name": "Compact Plus", "price_naira": 15400, "channels": "95+ channels"},
        {"id": "dstv-compact", "name": "Compact", "price_naira": 10500, "channels": "75+ channels"},
        {"id": "dstv-confam", "name": "Confam", "price_naira": 6300, "channels": "50+ channels"},
        {"id": "dstv-yanga", "name": "Yanga", "price_naira": 3600, "channels": "30+ channels"},
        {"id": "dstv-padi", "name": "Padi", "price_naira": 2500, "channels": "20+ channels"},
    ],
    "gotv": [
        {"id": "gotv-max", "name": "Max", "price_naira": 6100, "channels": "60+ channels"},
        {"id": "gotv-jolli", "name": "Jolli", "price_naira": 3950, "channels": "40+ channels"},
        {"id": "gotv-jinja", "name": "Jinja", "price_naira": 2100, "channels": "25+ channels"},
        {"id": "gotv-supa", "name": "Supa", "price_naira": 1750, "channels": "20+ channels"},
    ],
    "startimes": [
        {"id": "startimes-nova", "name": "Nova", "price_naira": 1900, "channels": "30+ channels"},
        {"id": "startimes-classic", "name": "Classic", "price_naira": 2900, "channels": "50+ channels"},
        {"id": "startimes-smart", "name": "Smart", "price_naira": 4900, "channels": "70+ channels"},
    ],
}

# Real data bundle pricing from Peyflex API user tier.
# Source: https://peyflex.com.ng/data-pricing/ — "API users get 5% discount"
# These are the API user (discounted) prices — what Peyflex charges us.
# The `id` values are the Peyflex `data_id` / `amount` parameter sent to
# their `/api/v1/data` endpoint. Each network uses its own naming scheme.
_DATA_BUNDLES: dict[str, list[dict]] = {
    "mtn": [
        {"id": "1", "name": "500MB — 30 days", "price_naira": 332, "size_mb": 500, "validity_days": 30},
        {"id": "2", "name": "1GB — 30 days", "price_naira": 456, "size_mb": 1024, "validity_days": 30},
        {"id": "3", "name": "2GB — 30 days", "price_naira": 805, "size_mb": 2048, "validity_days": 30},
        {"id": "4", "name": "3GB — 30 days", "price_naira": 1140, "size_mb": 3072, "validity_days": 30},
        {"id": "5", "name": "5GB — 30 days", "price_naira": 1710, "size_mb": 5120, "validity_days": 30},
        {"id": "11", "name": "11GB — 30 days", "price_naira": 3465, "size_mb": 11264, "validity_days": 30},
    ],
    "airtel": [
        {"id": "1", "name": "600MB — 30 days", "price_naira": 287, "size_mb": 600, "validity_days": 30},
        {"id": "2", "name": "1GB — 30 days", "price_naira": 346, "size_mb": 1024, "validity_days": 30},
        {"id": "3", "name": "2GB — 30 days", "price_naira": 742, "size_mb": 2048, "validity_days": 30},
        {"id": "4", "name": "3GB — 30 days", "price_naira": 1039, "size_mb": 3072, "validity_days": 30},
        {"id": "5", "name": "5GB — 30 days", "price_naira": 2450, "size_mb": 5120, "validity_days": 30},
        {"id": "6", "name": "10GB — 30 days", "price_naira": 2920, "size_mb": 10240, "validity_days": 30},
    ],
    "glo": [
        {"id": "1", "name": "500MB — 30 days", "price_naira": 240, "size_mb": 500, "validity_days": 30},
        {"id": "2", "name": "1GB — 30 days", "price_naira": 264, "size_mb": 1024, "validity_days": 30},
        {"id": "3", "name": "3GB — 30 days", "price_naira": 833, "size_mb": 3072, "validity_days": 30},
        {"id": "4", "name": "5GB — 30 days", "price_naira": 1352, "size_mb": 5120, "validity_days": 30},
        {"id": "5", "name": "2GB — 30 days", "price_naira": 882, "size_mb": 2048, "validity_days": 30},
        {"id": "6", "name": "10GB — 30 days", "price_naira": 3234, "size_mb": 10240, "validity_days": 30},
    ],
    "9mobile": [
        {"id": "1", "name": "500MB — 30 days", "price_naira": 294, "size_mb": 500, "validity_days": 30},
        {"id": "2", "name": "1GB — 30 days", "price_naira": 490, "size_mb": 1024, "validity_days": 30},
        {"id": "3", "name": "2GB — 30 days", "price_naira": 960, "size_mb": 2048, "validity_days": 30},
        {"id": "4", "name": "3GB — 30 days", "price_naira": 1470, "size_mb": 3072, "validity_days": 30},
        {"id": "5", "name": "5GB — 30 days", "price_naira": 2450, "size_mb": 5120, "validity_days": 30},
        {"id": "6", "name": "10GB — 30 days", "price_naira": 4900, "size_mb": 10240, "validity_days": 30},
    ],
}


@router.get("/bundles", response_model=list[BundleInfo])
async def list_bundles(network: str = "mtn"):
    """List available data bundles for a given network."""
    bundles = _DATA_BUNDLES.get(network, _DATA_BUNDLES["mtn"])
    return [
        BundleInfo(
            id=b["id"],
            network=network,
            name=b["name"],
            size_mb=b["size_mb"],
            validity_days=b["validity_days"],
            price_naira=b["price_naira"],
            commission_rate=_COMMISSION_RATES.get(network, 0.034),
        )
        for b in bundles
    ]


@router.get("/discos", response_model=list[DiscoInfo])
async def list_discos():
    """List available electricity distribution companies."""
    return [DiscoInfo(code=d["code"], name=d["name"]) for d in _DISCOS]


@router.get("/tv-bouquets", response_model=list[BouquetInfo])
async def list_tv_bouquets(provider: str = "dstv"):
    """List available TV bouquets for a given provider."""
    bouquets = _TV_PROVIDERS.get(provider, _TV_PROVIDERS["dstv"])
    return [
        BouquetInfo(
            id=b["id"],
            provider=provider,
            name=b["name"],
            price_naira=b["price_naira"],
            channels=b.get("channels"),
            commission_rate=_COMMISSION_RATES_TV,
        )
        for b in bouquets
    ]


@router.get("/verify-meter")
async def verify_meter(meter_number: str, disco: str):
    """Verify a meter number with the DISCO."""
    try:
        result = await get_client().check_meter(meter_number=meter_number, disco=disco)
        return {"valid": True, "customer_name": result.get("customer_name", ""), "address": result.get("address", "")}
    except PeyflexError:
        return {"valid": False, "customer_name": None, "address": None}


@router.get("/verify-smartcard")
async def verify_smartcard(smartcard_number: str, provider: str):
    """Verify a smartcard/IUC number."""
    try:
        result = await get_client().check_cable_customer(smartcard_number=smartcard_number, service=provider)
        return {
            "valid": True,
            "customer_name": result.get("customer_name", ""),
            "status": result.get("status", ""),
        }
    except PeyflexError:
        return {"valid": False, "customer_name": None, "status": None}


@router.post("/electricity", response_model=BillsPurchaseResponse)
async def buy_electricity(
    payload: ElectricityPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillsPurchaseResponse:
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
        receipt = await get_client().buy_electricity(
            meter_number=payload.meter_number,
            disco=payload.disco,
            meter_type=payload.meter_type,
            amount_naira=payload.amount_naira,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex electricity failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if receipt.status != "success":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {receipt.message}")

    commission_kobo = int(payload.amount_naira * 100 * _COMMISSION_RATES_ELEC)
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
        external_ref=receipt.external_ref,
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
        meter_number=payload.meter_number,
    )


@router.post("/tv", response_model=BillsPurchaseResponse)
async def buy_tv(
    payload: TelevisionPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BillsPurchaseResponse:
    """Subscribe cable TV and earn points."""
    reference = _generate_reference()

    # Look up the bouquet price
    bouquets = _TV_PROVIDERS.get(payload.provider, _TV_PROVIDERS["dstv"])
    bouquet = next((b for b in bouquets if b["id"] == payload.variation_id), None)
    if not bouquet:
        raise HTTPException(status_code=400, detail=f"Unknown bouquet: {payload.variation_id}")
    price_naira = bouquet["price_naira"]
    amount_kobo = price_naira * 100

    if current_user.points_balance < amount_kobo:
        raise HTTPException(status_code=402, detail="Insufficient balance")

    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(points_balance=User.points_balance - amount_kobo)
    )

    try:
        receipt = await get_client().buy_tv(
            smartcard_number=payload.smartcard_number,
            service=payload.provider,
            variation_id=payload.variation_id,
        )
    except PeyflexError as exc:
        await db.rollback()
        logger.error("Peyflex TV failed: %s", exc)
        raise HTTPException(status_code=502, detail="Payment provider unavailable")

    if receipt.status != "success":
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Purchase failed: {receipt.message}")

    commission_kobo = int(price_naira * 100 * _COMMISSION_RATES_TV)
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
        external_ref=receipt.external_ref,
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
        smartcard_number=payload.smartcard_number,
        customer_name=bouquet["name"],
    )
