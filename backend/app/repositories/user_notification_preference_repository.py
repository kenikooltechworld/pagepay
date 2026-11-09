"""Data-access layer for the `user_notification_preferences` table."""

from datetime import time as time_type, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserNotificationPreference


class UserNotificationPreferenceRepository:
    """Repository for `UserNotificationPreference` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_for_user(self, user_id: int) -> UserNotificationPreference | None:
        result = await self.db.execute(
            select(UserNotificationPreference).where(UserNotificationPreference.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_default(self, user_id: int) -> UserNotificationPreference:
        prefs = UserNotificationPreference(
            user_id=user_id,
            push_enabled=True,
            study_reminders=True,
            task_alerts=True,
            referral_bonuses=True,
            wallet_updates=True,
            ad_rewards=True,
        )
        self.db.add(prefs)
        await self.db.commit()
        await self.db.refresh(prefs)
        return prefs

    async def update(self, prefs: UserNotificationPreference, data: dict) -> UserNotificationPreference:
        for k, v in data.items():
            setattr(prefs, k, v)
        prefs.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(prefs)
        return prefs
