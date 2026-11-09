"""Data-access layer for the `password_reset_tokens` table."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import PasswordResetToken


class PasswordResetTokenRepository:
    """Repository for `PasswordResetToken` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, user_id: int, token_hash: str, expires_at: datetime) -> PasswordResetToken:
        row = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(row)
        await self.db.commit()
        return row

    async def get_valid_by_hash(self, token_hash: str) -> PasswordResetToken | None:
        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.expires_at > datetime.utcnow(),
            )
        )
        return result.scalar_one_or_none()

    async def mark_used(self, token: PasswordResetToken) -> None:
        token.used_at = datetime.utcnow()
        await self.db.commit()
