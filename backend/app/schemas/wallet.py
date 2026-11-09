"""Pydantic schemas for wallet endpoints."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WalletBalanceResponse(BaseModel):
    service_points_sp: int = Field(..., description="Non-cashable service points (SP)")
    cashable_balance_cb_kobo: int = Field(..., description="Cashable balance (CB) in kobo")
    points_balance_legacy: int = Field(0, description="Legacy mirror (do not rely on)")
    sp_per_naira: int
    study_unlock_default_points: int


class LedgerEntry(BaseModel):
    id: int
    currency: str
    direction: str
    amount: int
    balance_after: int
    source: str
    reference_type: str | None = None
    reference_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LedgerListResponse(BaseModel):
    items: list[LedgerEntry]
    next_cursor: int | None = None


class AdRewardClaimRequest(BaseModel):
    claim_id: str = Field(..., min_length=3, max_length=120, description="Idempotency key for this ad reward")
    amount_sp: int = Field(..., ge=1, le=5000)


class ConvertCbToSpRequest(BaseModel):
    amount_cb_kobo: int = Field(..., ge=100, description="CB amount in kobo to convert")


class GrantCbRequest(BaseModel):
    """Pre-Paystack/dev grant: credits CB (kobo). Guarded by wallet_grant_secret."""

    amount_cb_kobo: int = Field(..., ge=1)
    reference: str = Field(..., min_length=3, max_length=120, description="Idempotency reference")
    grant_secret: str


class GrantSpPurchaseRequest(BaseModel):
    """Pre-Paystack/dev grant: credits SP as a purchase. Guarded by wallet_grant_secret."""

    amount_sp: int = Field(..., ge=1)
    reference: str = Field(..., min_length=3, max_length=120, description="Idempotency reference")
    grant_secret: str
