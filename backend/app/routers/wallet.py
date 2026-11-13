"""Wallet HTTP routes (thin layer)."""

import logging

from fastapi import APIRouter, Depends, Query, Request

from app.controllers.payment_controller import PaymentController
from app.controllers.wallet_controller import WalletController
from app.core.database import get_db
from app.models.user import User
from app.schemas.payments import PaystackDepositInitRequest, PaystackDepositInitResponse
from app.schemas.wallet import (
    AdRewardClaimRequest,
    ConvertCbToSpRequest,
    GrantCbRequest,
    GrantSpPurchaseRequest,
    LedgerListResponse,
    WalletBalanceResponse,
)
from app.services.auth_service import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/wallet", tags=["wallet"])


def get_controller(db=Depends(get_db)) -> WalletController:
    return WalletController(db)


def get_payment_controller(db=Depends(get_db)) -> PaymentController:
    return PaymentController(db)


@router.get("/balance", response_model=WalletBalanceResponse)
async def get_balance(current_user: User = Depends(get_current_user), controller: WalletController = Depends(get_controller)):
    logger.info("endpoint.wallet.balance user=%s", current_user.id)
    res = await controller.balance(current_user.id)
    logger.info("endpoint.wallet.balance result user=%s sp=%s cb_kobo=%s", current_user.id, res.get("service_points_sp"), res.get("cashable_balance_cb_kobo"))
    return res


@router.get("/transactions", response_model=LedgerListResponse)
async def list_transactions(
    currency: str | None = Query(default=None, pattern="^(SP|CB|sp|cb)$"),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    logger.info("endpoint.wallet.transactions user=%s currency=%s limit=%s cursor=%s", current_user.id, currency, limit, cursor)
    res = await controller.transactions(current_user.id, currency, limit, cursor)
    logger.info("endpoint.wallet.transactions result user=%s count=%s next_cursor=%s", current_user.id, len(res.get("items", [])), res.get("next_cursor"))
    return res


@router.post("/deposit", response_model=PaystackDepositInitResponse)
async def initiate_wallet_deposit(
    payload: PaystackDepositInitRequest,
    current_user: User = Depends(get_current_user),
    controller: PaymentController = Depends(get_payment_controller),
):
    """Initialize Paystack CB (cashable) wallet deposit. Send `amount_naira` (preferred, user-facing) or `amount_kobo`."""
    amount_kobo = payload.resolved_amount_kobo()
    if amount_kobo <= 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Provide amount_naira or amount_kobo")
    logger.info("endpoint.wallet.deposit user=%s amount_naira=%s amount_kobo=%s callback_url=%s", current_user.id, payload.amount_naira, amount_kobo, bool(getattr(payload, "callback_url", None)))
    return await controller.init_wallet_deposit(current_user, amount_kobo, callback_url_override=getattr(payload, "callback_url", None))


@router.post("/deposit/webhook")
async def wallet_deposit_webhook_alias(request: Request, controller: PaymentController = Depends(get_payment_controller)):
    """Alias (convenience): /api/v1/wallet/deposit/webhook -> Paystack webhook handler."""
    logger.info("endpoint.wallet.deposit.webhook alias hit")
    return await controller.handle_webhook(request)


@router.post("/sp/ad-reward")
async def claim_ad_reward(
    payload: AdRewardClaimRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    logger.info("endpoint.wallet.ad_reward user=%s claim_id=%s amount_sp=%s", current_user.id, payload.claim_id, payload.amount_sp)
    res = await controller.claim_ad_reward(current_user.id, payload.claim_id, payload.amount_sp)
    logger.info("endpoint.wallet.ad_reward result user=%s applied=%s balance_sp=%s", current_user.id, res.get("applied"), res.get("balance_sp"))
    return res


@router.post("/cb/convert-to-sp")
async def convert_cb_to_sp(
    payload: ConvertCbToSpRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    logger.info("endpoint.wallet.convert_cb_to_sp user=%s amount_cb_kobo=%s", current_user.id, payload.amount_cb_kobo)
    res = await controller.convert_cb_to_sp(current_user.id, payload.amount_cb_kobo)
    logger.info("endpoint.wallet.convert_cb_to_sp result user=%s credited_sp=%s cb=%s sp=%s", current_user.id, res.get("credited_sp"), res.get("balance_cb_kobo"), res.get("balance_sp"))
    return res


@router.post("/cb/grant")
async def grant_cb(
    payload: GrantCbRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    """Pre-Paystack/dev CB grant (guarded by wallet_grant_secret)."""
    logger.info("endpoint.wallet.grant_cb user=%s amount_cb_kobo=%s ref=%s", current_user.id, payload.amount_cb_kobo, payload.reference)
    return await controller.grant_cb(current_user.id, payload.amount_cb_kobo, payload.reference, payload.grant_secret)


@router.post("/sp/grant-purchase")
async def grant_sp_purchase(
    payload: GrantSpPurchaseRequest,
    current_user: User = Depends(get_current_user),
    controller: WalletController = Depends(get_controller),
):
    """Pre-Paystack/dev SP purchase credit (guarded by wallet_grant_secret)."""
    logger.info("endpoint.wallet.grant_sp_purchase user=%s amount_sp=%s ref=%s", current_user.id, payload.amount_sp, payload.reference)
    return await controller.grant_sp_purchase(current_user.id, payload.amount_sp, payload.reference, payload.grant_secret)
