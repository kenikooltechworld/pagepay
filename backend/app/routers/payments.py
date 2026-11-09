"""Paystack HTTP routes (deposit init + webhook targets for paystack-router)."""

import logging

from fastapi import APIRouter, Depends, Request

from app.controllers.payment_controller import PaymentController
from app.core.database import get_db
from app.models.user import User
from app.schemas.payments import PaystackDepositInitRequest, PaystackDepositInitResponse, PaystackVerifyResponse
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
    """Initialize a Paystack transaction to fund cashable CB (kobo)."""
    logger.info("endpoint.payments.deposit user=%s amount_kobo=%s", current_user.id, payload.amount_kobo)
    return await controller.init_wallet_deposit(current_user, payload.amount_kobo)


@router.get("/paystack/verify/{reference}", response_model=PaystackVerifyResponse)
async def verify_paystack_deposit(
    reference: str,
    current_user: User = Depends(get_current_user),
    controller: PaymentController = Depends(get_controller),
):
    """Server-verify a Paystack reference and idempotently credit CB (webhook fallback)."""
    logger.info("endpoint.payments.verify user=%s ref=%s", current_user.id, reference)
    return await controller.verify_reference(current_user, reference)
