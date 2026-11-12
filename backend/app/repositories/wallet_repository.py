"""Data-access layer for wallet ledger and study unlocks."""

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.wallet import StudyUnlock, WalletLedger


class WalletRepository:
    """Repository for `WalletLedger` and `StudyUnlock`."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def ledger_by_idempotency(self, key: str) -> WalletLedger | None:
        result = await self.db.execute(select(WalletLedger).where(WalletLedger.idempotency_key == key))
        return result.scalar_one_or_none()

    async def list_ledger(
        self, user_id: int, currency: str | None = None, limit: int = 50, cursor: int | None = None
    ) -> list[WalletLedger]:
        q = select(WalletLedger).where(WalletLedger.user_id == user_id)
        if currency:
            q = q.where(WalletLedger.currency == currency.upper())
        if cursor is not None:
            q = q.where(WalletLedger.id < cursor)
        q = q.order_by(WalletLedger.id.desc()).limit(limit)
        result = await self.db.execute(q)
        return list(result.scalars().all())

    async def get_unlock(self, user_id: int, asset_id: int) -> StudyUnlock | None:
        result = await self.db.execute(
            select(StudyUnlock).where(StudyUnlock.user_id == user_id, StudyUnlock.asset_id == asset_id)
        )
        return result.scalar_one_or_none()

    async def list_unlocks_for_material(self, user_id: int, material_id: int) -> list[StudyUnlock]:
        result = await self.db.execute(
            select(StudyUnlock).where(StudyUnlock.user_id == user_id, StudyUnlock.material_id == material_id)
        )
        return list(result.scalars().all())

    async def delete_unlocks_for_asset(self, asset_id: int) -> None:
        await self.db.execute(delete(StudyUnlock).where(StudyUnlock.asset_id == asset_id))

    async def delete_unlocks_for_material(self, material_id: int) -> None:
        await self.db.execute(delete(StudyUnlock).where(StudyUnlock.material_id == material_id))
