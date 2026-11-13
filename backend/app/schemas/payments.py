"""Pydantic schemas for Paystack payments."""

from pydantic import BaseModel, Field

from app.core.config import settings


from app.core.config import settings


class PaystackDepositInitRequest(BaseModel):
    amount_kobo: int | None = Field(None, ge=1, description="Deposit amount in kobo (?1=100 kobo). Server enforces minimum.")
    amount_naira: int | None = Field(None, ge=1, description="Deposit amount in Naira (converted to kobo). Prefer this for UI.")
    callback_url: str | None = Field(None, description="Optional return/callback URL after checkout (e.g. mobile deep link). Falls back to server default.")

    def resolved_amount_kobo(self) -> int:
        if self.amount_kobo is not None:
            return int(self.amount_kobo)
        if self.amount_naira is not None:
            return int(self.amount_naira) * 100
        return 0


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


class PaystackRefundRequest(BaseModel):
    amount_kobo: int | None = Field(None, ge=1, description="Optional partial refund in kobo; defaults to full amount")
    reason: str | None = Field(None, max_length=200)
    guard_secret: str | None = Field(None, description="Required unless caller is admin (uses wallet_grant_secret)")


class PaystackPaymentStatusResponse(BaseModel):
    reference: str
    status: str
    purpose: str | None = None
    amount_kobo: int
    credit_amount_kobo: int | None = None
    currency: str | None = None
    webhook_confirmed: bool
    created_at: str | None = None
    confirmed_at: str | None = None
