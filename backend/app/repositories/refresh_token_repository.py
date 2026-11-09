"""Data-access layer for the `refresh_tokens` table."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import RefreshToken


class RefreshTokenRepository:
    """Repository for `RefreshToken` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> RefreshToken:
        row = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self.db.add(row)
        await self.db.commit()
        return row

    async def get_valid_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.expires_at > datetime.utcnow(),
                RefreshToken.revoked == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked = True
        await self.db.commit()

    async def revoke_all_for_user(self, user_id: int) -> None:
        await self.db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id)
            .values(revoked=True)
        )
        await self.db.commit()
