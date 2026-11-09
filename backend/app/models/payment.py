"""Paystack payment DB model (CB wallet deposits; extensible)."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Payment(Base):
    """Payment/deposit record reconciled by Paystack webhook (provider_tx_ref = reference).

    Compatible with the pre-existing `payments` table shape (tier/amount_kobo/provider/provider_tx_ref/status/webhook_confirmed/metadata/created/confirmed)
    by adding optional `purpose`, `credit_amount_kobo`, and `currency` (nullable/defaulted) and exposing `tier`/metadata aliases.
    """

    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    purpose: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)  # wallet_deposit_cb | (future) sp_pack
    tier: Mapped[str | None] = mapped_column(String(50), nullable=True)  # legacy column retained
    amount_kobo: Mapped[int] = mapped_column(BigInteger)  # total charged
    credit_amount_kobo: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=0)  # CB to credit
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True, default="NGN")
    provider: Mapped[str] = mapped_column(String(50), default="paystack")
    provider_tx_ref: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending|success|failed
    webhook_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    payment_metadata: Mapped[dict | None] = mapped_column("payment_metadata", JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
