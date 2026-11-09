"""Data-access layer for the `point_credits` table (idempotent grants)."""

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import PointCredit, User
from app.models.wallet import WalletLedger


class PointCreditRepository:
    """Repository for `PointCredit` (idempotent point grants)."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def grant_welcome_bonus(self, user: User) -> bool:
        """Insert a welcome_bonus credit (idempotent). Returns True if newly inserted.

        Uses PostgreSQL ON CONFLICT DO NOTHING on the UNIQUE(user_id, source)
        constraint. If a row already existed, returns False and credits nothing.
        Also writes a `wallet_ledger` SP credit (idempotent key) so the unified ledger
        reflects the grant.
        """

        if settings.welcome_bonus_points <= 0:
            return False

        stmt = (
            pg_insert(PointCredit)
            .values(
                user_id=user.id,
                source="welcome_bonus",
                points=settings.welcome_bonus_points,
                metadata_json={"trigger": "email_verify"},
            )
            .on_conflict_do_nothing(index_elements=["user_id", "source"])
        )
        result = await self.db.execute(stmt)
        inserted = result.rowcount or 0
        await self.db.commit()

        if inserted == 0:
            return False

        # Credit the wallet (split-ledger aware).
        if settings.wallet_split_enabled:
            await self.db.execute(
                update(User)
                .where(User.id == user.id)
                .values(service_credit_balance=User.service_credit_balance + settings.welcome_bonus_points)
            )
        else:
            await self.db.execute(
                update(User)
                .where(User.id == user.id)
                .values(points_balance=User.points_balance + settings.welcome_bonus_points)
            )
        await self.db.commit()
        await self.db.refresh(user)

        # Unified wallet ledger entry (idempotent; best-effort if race).
        try:
            new_sp = int(getattr(user, "service_credit_balance", 0) or 0)
            self.db.add(WalletLedger(
                user_id=user.id, currency="SP", direction="credit", amount=settings.welcome_bonus_points,
                balance_after=new_sp, source="welcome_bonus", reference_type="point_credit",
                reference_id="welcome_bonus", idempotency_key=f"welcome_bonus_sp:{user.id}",
                metadata_json={"trigger": "email_verify"},
            ))
            await self.db.commit()
        except Exception:
            await self.db.rollback()
        return True
