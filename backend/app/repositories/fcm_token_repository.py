"""Data-access layer for the `fcm_tokens` table."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import FCMToken


class FCMTokenRepository:
    """Repository for `FCMToken` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_token(self, token: str) -> FCMToken | None:
        result = await self.db.execute(select(FCMToken).where(FCMToken.token == token))
        return result.scalar_one_or_none()

    async def get_by_token_and_user(self, token: str, user_id: int) -> FCMToken | None:
        result = await self.db.execute(
            select(FCMToken).where(FCMToken.token == token, FCMToken.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def list_active_for_user(self, user_id: int) -> list[FCMToken]:
        result = await self.db.execute(
            select(FCMToken).where(FCMToken.user_id == user_id, FCMToken.is_active == True)  # noqa: E712
        )
        return list(result.scalars().all())

    async def create(self, user_id: int, token: str, platform: str, device_id: str | None) -> FCMToken:
        row = FCMToken(user_id=user_id, token=token, platform=platform, device_id=device_id, is_active=True)
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_existing(self, fcm: FCMToken, user_id: int, platform: str, device_id: str | None) -> FCMToken:
        fcm.is_active = True
        fcm.user_id = user_id
        fcm.platform = platform
        fcm.device_id = device_id
        fcm.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(fcm)
        return fcm

    async def deactivate(self, fcm: FCMToken) -> None:
        fcm.is_active = False
        fcm.updated_at = datetime.utcnow()
        await self.db.commit()

    async def deactivate_by_token(self, token: str, user_id: int) -> bool:
        fcm = await self.get_by_token_and_user(token, user_id)
        if not fcm:
            return False
        await self.deactivate(fcm)
        return True
