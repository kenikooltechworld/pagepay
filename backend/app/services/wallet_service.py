"""Wallet service (SP/CB ledger + atomic balance updates).

Design:
- `WalletLedger` is the auditable record; `users.service_credit_balance` (SP) and
  `users.cashable_balance` (CB, kobo) are denormalized running balances.
- Mutations lock the user row (`SELECT ... FOR UPDATE`), validate, write a ledger row, update
  the balance, and commit. Idempotent operations (e.g. ad reward claim) return the existing
  ledger row when the idempotency key already exists.
"""

import logging
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.wallet import WalletLedger
from app.repositories.wallet_repository import WalletRepository

logger = logging.getLogger("uvicorn.error")


class WalletService:
    """Business logic for SP/CB balances and ledger."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WalletRepository(db)

    # --- helpers ---

    async def _locked_user(self, user_id: int) -> User:
        result = await self.db.execute(select(User).where(User.id == user_id).with_for_update())
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    def _sp(self, user: User) -> int:
        return int(user.service_credit_balance or 0)

    def _cb(self, user: User) -> int:
        return int(user.cashable_balance or 0)

    @staticmethod
    def cb_kobo_to_sp(amount_cb_kobo: int) -> int:
        # SP = floor(cb_kobo * sp_per_naira / 100)
        return (int(amount_cb_kobo) * int(settings.sp_per_naira)) // 100

    # --- reads ---

    async def get_balance(self, user_id: int) -> dict:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return {
            "service_points_sp": self._sp(user),
            "cashable_balance_cb_kobo": self._cb(user),
            "points_balance_legacy": int(user.points_balance or 0),
            "sp_per_naira": settings.sp_per_naira,
            "study_unlock_default_points": settings.study_unlock_default_points,
        }

    async def list_transactions(self, user_id: int, currency: str | None, limit: int, cursor: int | None) -> dict:
        limit = max(1, min(int(limit or 50), 100))
        rows = await self.repo.list_ledger(user_id, currency=currency, limit=limit, cursor=cursor)
        items = [
            {
                "id": r.id,
                "currency": r.currency,
                "direction": r.direction,
                "amount": r.amount,
                "balance_after": r.balance_after,
                "source": r.source,
                "reference_type": r.reference_type,
                "reference_id": r.reference_id,
                "created_at": r.created_at,
            }
            for r in rows
        ]
        next_cursor = rows[-1].id if len(rows) == limit else None
        return {"items": items, "next_cursor": next_cursor}

    # --- mutations (atomic) ---

    async def _credit_sp(
        self, user_id: int, amount: int, source: str, *, reference_type: str | None = None,
        reference_id: str | None = None, idempotency_key: str | None = None, metadata: dict | None = None,
    ) -> tuple[User, WalletLedger, bool]:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        if idempotency_key:
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                u = await self._locked_user(user_id)  # refresh
                return u, existing, False
        user = await self._locked_user(user_id)
        if idempotency_key:  # recheck under lock
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                return user, existing, False
        new_bal = self._sp(user) + amount
        user.service_credit_balance = new_bal
        # keep legacy mirror in sync (non-authoritative)
        user.points_balance = int(user.points_balance or 0) + amount
        entry = WalletLedger(
            user_id=user_id, currency="SP", direction="credit", amount=amount,
            balance_after=new_bal, source=source, reference_type=reference_type,
            reference_id=reference_id, idempotency_key=idempotency_key, metadata_json=metadata,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(user)
        await self.db.refresh(entry)
        return user, entry, True

    async def _debit_sp(
        self, user_id: int, amount: int, source: str, *, reference_type: str | None = None,
        reference_id: str | None = None, idempotency_key: str | None = None, metadata: dict | None = None,
    ) -> tuple[User, WalletLedger, bool]:
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        if idempotency_key:
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                u = await self._locked_user(user_id)
                return u, existing, False
        user = await self._locked_user(user_id)
        if idempotency_key:
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                return user, existing, False
        if self._sp(user) < amount:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"message": "Insufficient service points (SP)", "required_sp": amount, "balance_sp": self._sp(user)},
            )
        new_bal = self._sp(user) - amount
        user.service_credit_balance = new_bal
        user.points_balance = max(0, int(user.points_balance or 0) - amount)
        entry = WalletLedger(
            user_id=user_id, currency="SP", direction="debit", amount=amount,
            balance_after=new_bal, source=source, reference_type=reference_type,
            reference_id=reference_id, idempotency_key=idempotency_key, metadata_json=metadata,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(user)
        await self.db.refresh(entry)
        return user, entry, True

    async def _credit_cb(
        self, user_id: int, amount_kobo: int, source: str, *, reference_type: str | None = None,
        reference_id: str | None = None, idempotency_key: str | None = None, metadata: dict | None = None,
    ) -> tuple[User, WalletLedger, bool]:
        if amount_kobo <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        if idempotency_key:
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                u = await self._locked_user(user_id)
                return u, existing, False
        user = await self._locked_user(user_id)
        if idempotency_key:
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                return user, existing, False
        new_bal = self._cb(user) + amount_kobo
        user.cashable_balance = new_bal
        entry = WalletLedger(
            user_id=user_id, currency="CB", direction="credit", amount=amount_kobo,
            balance_after=new_bal, source=source, reference_type=reference_type,
            reference_id=reference_id, idempotency_key=idempotency_key, metadata_json=metadata,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(user)
        await self.db.refresh(entry)
        return user, entry, True

    async def _debit_cb(
        self, user_id: int, amount_kobo: int, source: str, *, reference_type: str | None = None,
        reference_id: str | None = None, idempotency_key: str | None = None, metadata: dict | None = None,
    ) -> tuple[User, WalletLedger, bool]:
        if amount_kobo <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        if idempotency_key:
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                u = await self._locked_user(user_id)
                return u, existing, False
        user = await self._locked_user(user_id)
        if idempotency_key:
            existing = await self.repo.ledger_by_idempotency(idempotency_key)
            if existing:
                return user, existing, False
        if self._cb(user) < amount_kobo:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"message": "Insufficient cashable balance (CB)", "required_cb_kobo": amount_kobo, "balance_cb_kobo": self._cb(user)},
            )
        new_bal = self._cb(user) - amount_kobo
        user.cashable_balance = new_bal
        entry = WalletLedger(
            user_id=user_id, currency="CB", direction="debit", amount=amount_kobo,
            balance_after=new_bal, source=source, reference_type=reference_type,
            reference_id=reference_id, idempotency_key=idempotency_key, metadata_json=metadata,
        )
        self.db.add(entry)
        await self.db.commit()
        await self.db.refresh(user)
        await self.db.refresh(entry)
        return user, entry, True

    # --- public operations ---

    async def claim_ad_reward(self, user_id: int, claim_id: str, amount_sp: int) -> dict:
        idem = f"ad_reward:{user_id}:{claim_id}"
        user, entry, applied = await self._credit_sp(
            user_id, amount_sp, "ad_reward", reference_type="ad_claim", reference_id=claim_id, idempotency_key=idem,
        )
        return {"applied": applied, "balance_sp": self._sp(user), "ledger_id": entry.id}

    async def grant_cb(self, user_id: int, amount_cb_kobo: int, reference: str) -> dict:
        idem = f"grant_cb:{reference}"
        user, entry, applied = await self._credit_cb(
            user_id, amount_cb_kobo, "deposit_grant", reference_type="grant", reference_id=reference, idempotency_key=idem,
        )
        return {"applied": applied, "balance_cb_kobo": self._cb(user), "ledger_id": entry.id}

    async def grant_sp_purchase(self, user_id: int, amount_sp: int, reference: str) -> dict:
        idem = f"sp_purchase:{reference}"
        user, entry, applied = await self._credit_sp(
            user_id, amount_sp, "sp_purchase", reference_type="purchase", reference_id=reference, idempotency_key=idem,
        )
        return {"applied": applied, "balance_sp": self._sp(user), "ledger_id": entry.id}

    async def convert_cb_to_sp(self, user_id: int, amount_cb_kobo: int) -> dict:
        """Atomically debit CB (kobo) and credit SP at the configured rate."""
        sp_amount = self.cb_kobo_to_sp(amount_cb_kobo)
        if sp_amount <= 0:
            raise HTTPException(status_code=400, detail="Amount too small to convert at current rate")
        user = await self._locked_user(user_id)
        if self._cb(user) < amount_cb_kobo:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"message": "Insufficient cashable balance (CB)", "required_cb_kobo": amount_cb_kobo, "balance_cb_kobo": self._cb(user)},
            )
        new_cb = self._cb(user) - amount_cb_kobo
        new_sp = self._sp(user) + sp_amount
        user.cashable_balance = new_cb
        user.service_credit_balance = new_sp
        user.points_balance = int(user.points_balance or 0) + sp_amount
        ref = f"conv:{user_id}:{amount_cb_kobo}:{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
        self.db.add(WalletLedger(
            user_id=user_id, currency="CB", direction="debit", amount=amount_cb_kobo,
            balance_after=new_cb, source="cb_to_sp", reference_type="conversion", reference_id=ref,
        ))
        self.db.add(WalletLedger(
            user_id=user_id, currency="SP", direction="credit", amount=sp_amount,
            balance_after=new_sp, source="cb_to_sp", reference_type="conversion", reference_id=ref,
        ))
        await self.db.commit()
        await self.db.refresh(user)
        return {
            "converted_cb_kobo": amount_cb_kobo,
            "credited_sp": sp_amount,
            "balance_cb_kobo": self._cb(user),
            "balance_sp": self._sp(user),
        }
