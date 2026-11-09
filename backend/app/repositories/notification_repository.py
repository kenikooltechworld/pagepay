"""Data-access layer for the `notifications` table."""

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Notification


class NotificationRepository:
    """Repository for `Notification` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        title: str,
        body: str,
        category: str | None = None,
        data: str | None = None,
    ) -> Notification:
        row = Notification(
            user_id=user_id,
            title=title,
            body=body,
            category=category,
            data=data,
        )
        self.db.add(row)
        await self.db.commit()
        return row

    async def mark_read(self, notification_id: int, user_id: int) -> None:
        await self.db.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(read=True)
        )
        await self.db.commit()


    async def list_for_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list[Notification]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_unread(self, user_id: int) -> int:
        from sqlalchemy import func, select
        result = await self.db.execute(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
                Notification.read == False,  # noqa: E712
            )
        )
        return result.scalar_one() or 0

    async def get_by_id(self, notification_id: int, user_id: int) -> Notification | None:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id,
                Notification.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def mark_read(self, notification_id: int, user_id: int) -> bool:
        from sqlalchemy import update
        result = await self.db.execute(
            update(Notification)
            .where(Notification.id == notification_id, Notification.user_id == user_id)
            .values(read=True)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def mark_all_read(self, user_id: int) -> None:
        from sqlalchemy import update
        await self.db.execute(
            update(Notification)
            .where(Notification.user_id == user_id, Notification.read == False)  # noqa: E712
            .values(read=True)
        )
        await self.db.commit()
