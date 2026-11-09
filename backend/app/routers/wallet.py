"""Wallet HTTP routes (thin layer)."""

from fastapi import APIRouter, Depends, Query

from app.controllers.wallet_controller import WalletController
from app.core.database import get_db
from app.models.user import User
from app.schemas.wallet import (
    AdRewardClaimRequest,
    ConvertCbToSpRequest,
    GrantCbRequest,
    GrantSpPurchaseRequest,
    LedgerListResponse,
    WalletBalanceResponse,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/wallet", tags=["wallet"])


def get_controller(db=Depends(get_db)) -> WalletController:
    return WalletController(db)


@router.get("/balance", response_model=WalletBalanceResponse)
async def get_balance(current_user: User = Depends(get_current_user), controller: WalletController = Depends(get_controller)):
    return await controller.balance(current_user.id)


@router.get("/transactions", response_model=LedgerListResponse)
async def list_transactions(
    currency: str | None = Query(default=None, pattern="^(SP|CB|sp|cb)$"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    return await controller.transactions(current_user.id, currency, limit, cursor)


@router.post("/sp/ad-reward")
async def claim_ad_reward(
    payload: AdRewardClaimRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    return await controller.claim_ad_reward(current_user.id, payload.claim_id, payload.amount_sp)


@router.post("/cb/convert-to-sp")
async def convert_cb_to_sp(
    payload: ConvertCbToSpRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    return await controller.convert_cb_to_sp(current_user.id, payload.amount_cb_kobo)


@router.post("/cb/grant")
async def grant_cb(
    payload: GrantCbRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    """Pre-Paystack/dev CB grant (guarded by wallet_grant_secret)."""
    return await controller.grant_cb(current_user.id, payload.amount_cb_kobo, payload.reference, payload.grant_secret)


@router.post("/sp/grant-purchase")
async def grant_sp_purchase(
    payload: GrantSpPurchaseRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    """Pre-Paystack/dev SP purchase credit (guarded by wallet_grant_secret)."""
    return await controller.grant_sp_purchase(current_user.id, payload.amount_sp, payload.reference, payload.grant_secret)
