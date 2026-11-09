"""Wallet and study-unlock database models.

Teaching notes:
- CB (cashable balance) is stored/ledgered in **kobo** (integer).
- SP (service points) is stored/ledgered in **points** (integer).
- `WalletLedger` is the auditable source of truth for balance changes. `users.service_credit_balance`
  and `users.cashable_balance` are denormalized running balances updated atomically with each ledger row.
- `StudyUnlock` makes asset unlocks idempotent: UNIQUE(user_id, asset_id).
"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WalletLedger(Base):
    """Auditable wallet transaction (SP or CB)."""

    __tablename__ = "wallet_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # SP | CB
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # credit | debit
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)  # always > 0
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reference_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(120), nullable=True, unique=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class StudyUnlock(Base):
    """Per-user unlock of a study asset (idempotent)."""

    __tablename__ = "study_unlocks"
    __table_args__ = (UniqueConstraint("user_id", "asset_id", name="uq_study_unlock_user_asset"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    asset_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    material_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    points_spent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
