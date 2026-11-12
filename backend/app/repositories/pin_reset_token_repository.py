"""Data-access layer for the `pin_reset_tokens` table."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import PinResetToken


class PinResetTokenRepository:
    """Repository for `PinResetToken` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        otp_hash: str | None = None,
        otp_expires_at: datetime | None = None,
    ) -> PinResetToken:
        row = PinResetToken(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
            otp_hash=otp_hash,
            otp_expires_at=otp_expires_at,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def invalidate_active_for_user(self, user_id: int) -> None:
        await self.db.execute(
            update(PinResetToken)
            .where(PinResetToken.user_id == user_id, PinResetToken.used_at.is_(None))
            .values(used_at=datetime.utcnow())
        )
        await self.db.commit()

    async def get_latest_unused_for_user(self, user_id: int) -> PinResetToken | None:
        result = await self.db.execute(
            select(PinResetToken)
            .where(
                PinResetToken.user_id == user_id,
                PinResetToken.used_at.is_(None),
                PinResetToken.expires_at > datetime.utcnow(),
            )
            .order_by(PinResetToken.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_valid_by_hash(self, token_hash: str) -> PinResetToken | None:
        result = await self.db.execute(
            select(PinResetToken).where(
                PinResetToken.token_hash == token_hash,
                PinResetToken.used_at.is_(None),
                PinResetToken.expires_at > datetime.utcnow(),
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: PinResetToken) -> None:
        token.used_at = datetime.utcnow()
        await self.db.commit()

    async def save(self, token: PinResetToken) -> None:
        await self.db.commit()
        await self.db.refresh(token)
