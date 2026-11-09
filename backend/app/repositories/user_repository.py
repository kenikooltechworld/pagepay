"""Data-access layer for the `users` table.

Teaching notes:
- Repositories encapsulate ALL SQL/ORM queries for one aggregate (User).
- Services/controllers never write queries directly; they call repositories.
- This keeps DB details in one place and makes services easy to unit-test
  (you can swap the repository with a fake).
"""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    """Repository for `User` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, user_id: int) -> User | None:
        return await self.db.get(User, user_id)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        result = await self.db.execute(select(User).where(User.phone == phone))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.username == username.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_referral_code(self, code: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.referral_code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_identity(self, identity: str) -> User | None:
        """Look up by email, phone, or username (case-insensitive username)."""

        result = await self.db.execute(
            select(User).where(
                (User.email == identity)
                | (User.phone == identity)
                | (User.username == identity.lower())
            )
        )
        return result.scalar_one_or_none()

    async def create(self, user: User) -> User:
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def update(self, user: User) -> User:
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def delete(self, user: User) -> None:
        await self.db.delete(user)
        await self.db.commit()
