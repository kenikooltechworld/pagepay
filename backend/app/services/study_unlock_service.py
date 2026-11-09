"""Study unlock service (SP debit + idempotent unlock record, atomic)."""

import json

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.study import StudyAsset, StudyMaterial
from app.models.user import User
from app.models.wallet import StudyUnlock, WalletLedger
from app.repositories.wallet_repository import WalletRepository
from app.services.wallet_service import WalletService


class StudyUnlockService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.wallet = WalletService(db)
        self.repo = WalletRepository(db)

    async def unlock_asset(self, user_id: int, asset_id: int) -> dict:
        # Load asset + material (ownership)
        asset = (await self.db.execute(select(StudyAsset).where(StudyAsset.id == asset_id))).scalar_one_or_none()
        if not asset:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")
        material = (await self.db.execute(select(StudyMaterial).where(StudyMaterial.id == asset.material_id))).scalar_one_or_none()
        if not material or material.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found")

        content = json.loads(asset.content_json) if asset.content_json else None

        # Fast path: already unlocked
        existing = await self.repo.get_unlock(user_id, asset_id)
        if existing:
            bal = await self.wallet.get_balance(user_id)
            return {
                "unlocked": True, "asset_id": asset.id, "material_id": asset.material_id,
                "points_spent": existing.points_spent, "new_sp_balance": bal["service_points_sp"],
                "content": content, "method": "already_unlocked",
            }

        cost = int(asset.points_to_unlock or 0)
        # Atomic: lock user, recheck unlock, debit SP, insert unlock, single commit
        user = (await self.db.execute(select(User).where(User.id == user_id).with_for_update())).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        existing = await self.repo.get_unlock(user_id, asset_id)
        if existing:
            await self.db.rollback()
            bal = await self.wallet.get_balance(user_id)
            return {
                "unlocked": True, "asset_id": asset.id, "material_id": asset.material_id,
                "points_spent": existing.points_spent, "new_sp_balance": bal["service_points_sp"],
                "content": content, "method": "already_unlocked",
            }

        sp = int(user.service_credit_balance or 0)
        if cost > 0 and sp < cost:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={"message": "Insufficient service points (SP)", "required_sp": cost, "balance_sp": sp},
            )
        new_sp = sp - cost if cost > 0 else sp
        if cost > 0:
            user.service_credit_balance = new_sp
            user.points_balance = max(0, int(user.points_balance or 0) - cost)
            self.db.add(WalletLedger(
                user_id=user_id, currency="SP", direction="debit", amount=cost,
                balance_after=new_sp, source="study_unlock", reference_type="study_asset",
                reference_id=str(asset_id), idempotency_key=f"study_unlock_sp:{user_id}:{asset_id}",
            ))
        self.db.add(StudyUnlock(user_id=user_id, asset_id=asset.id, material_id=asset.material_id, points_spent=cost))
        await self.db.commit()
        await self.db.refresh(user)
        return {
            "unlocked": True, "asset_id": asset.id, "material_id": asset.material_id,
            "points_spent": cost, "new_sp_balance": new_sp, "content": content, "method": "points",
        }

    async def is_unlocked(self, user_id: int, asset_id: int) -> bool:
        return await self.repo.get_unlock(user_id, asset_id) is not None
