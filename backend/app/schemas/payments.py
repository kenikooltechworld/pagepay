"""Pydantic schemas for Paystack payments."""

from pydantic import BaseModel, Field

from app.core.config import settings


from app.core.config import settings


class PaystackDepositInitRequest(BaseModel):
    amount_kobo: int | None = Field(None, ge=1, description="Deposit amount in kobo (₦1=100 kobo). Server enforces minimum.")
    amount_naira: int | None = Field(None, ge=1, description="Deposit amount in Naira (converted to kobo). Prefer this for UI.")

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
