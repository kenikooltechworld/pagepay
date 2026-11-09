"""Paystack HTTP routes (deposit init + webhook targets for paystack-router)."""

import logging

from fastapi import APIRouter, Depends, Request

from app.controllers.payment_controller import PaymentController
from app.core.database import get_db
from app.models.user import User
from app.schemas.payments import (
    PaystackDepositInitRequest,
    PaystackDepositInitResponse,
    PaystackPaymentStatusResponse,
    PaystackRefundRequest,
    PaystackVerifyResponse,
)
from app.services.auth_service import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/payments", tags=["payments"])


def get_controller(db=Depends(get_db)) -> PaymentController:
    return PaymentController(db)


@router.post("/paystack/deposit", response_model=PaystackDepositInitResponse)
async def init_paystack_deposit(
    payload: PaystackDepositInitRequest,
    current_user: User = Depends(get_current_user),
    controller: PaymentController = Depends(get_controller),
):
    """Initialize a Paystack transaction to fund cashable CB. Send `amount_naira` (preferred) or `amount_kobo`."""
    amount_kobo = payload.resolved_amount_kobo()
    if amount_kobo <= 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Provide amount_naira or amount_kobo")
    logger.info("endpoint.payments.deposit user=%s amount_naira=%s amount_kobo=%s", current_user.id, payload.amount_naira, amount_kobo)
    return await controller.init_wallet_deposit(current_user, amount_kobo)


@router.get("/paystack/status/{reference}", response_model=PaystackPaymentStatusResponse)
async def get_paystack_payment_status(
    reference: str,
    current_user: User = Depends(get_current_user),
    controller: PaymentController = Depends(get_controller),
):
    """Get payment/deposit status for the current user (success/failed/pending/refunded)."""
    logger.info("endpoint.payments.status user=%s ref=%s", current_user.id, reference)
    return await controller.get_payment_status(current_user, reference)


@router.post("/paystack/refund")
async def refund_paystack_deposit(
    payload: PaystackRefundRequest,
    reference: str,
    current_user: User = Depends(get_current_user),
    controller: PaymentController = Depends(get_controller),
):
    """Initiate a guarded Paystack refund for a successful wallet deposit (idempotent; reverses CB on refund webhook)."""
    logger.info("endpoint.payments.refund user=%s ref=%s amount_kobo=%s", current_user.id, reference, payload.amount_kobo)
    return await controller.initiate_refund(actor_user=current_user, reference=reference, amount_kobo=payload.amount_kobo, reason=payload.reason, guard_secret=payload.guard_secret)
