"""Pydantic schemas for Paystack payments."""

from pydantic import BaseModel, Field


class PaystackDepositInitRequest(BaseModel):
    amount_kobo: int = Field(..., ge=100, description="Deposit amount in kobo (min 100)")


class PaystackDepositInitResponse(BaseModel):
    authorization_url: str
    access_code: str
    reference: str
    amount_kobo: int
    credit_amount_kobo: int
    currency: str = "NGN"


class PaystackVerifyResponse(BaseModel):
    received: bool = True
    handled: bool
    reference: str
    credited: bool | None = None
    reason: str | None = None
    status: str | None = None
    payment_status: str | None = None
    balance_cb_kobo: int | None = None
