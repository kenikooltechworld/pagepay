"""Payouts/webhook aliases so paystack-router `pp_` target (…/api/v1/payouts/webhook) resolves."""

import logging

from fastapi import APIRouter, Depends, Request

from app.controllers.payment_controller import PaymentController
from app.core.database import get_db

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/payouts", tags=["payouts"])


def get_controller(db=Depends(get_db)) -> PaymentController:
    return PaymentController(db)


@router.post("/webhook")
async def paystack_webhook_alias(request: Request, controller: PaymentController = Depends(get_controller)):
    """Alias for paystack-router (pp_ → /api/v1/payouts/webhook)."""
    logger.info("endpoint.payouts.webhook alias hit")
    return await controller.handle_webhook(request)
