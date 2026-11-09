"""Notification controller (OOP)."""

import json
from datetime import datetime, time as time_type

from fastapi import HTTPException

from app.models.user import Notification, User
from app.repositories.fcm_token_repository import FCMTokenRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_notification_preference_repository import UserNotificationPreferenceRepository


class NotificationController:
    """Orchestrates notification use-cases."""

    def __init__(self, db):
        self.db = db
        self.notifications = NotificationRepository(db)
        self.fcm_tokens = FCMTokenRepository(db)
        self.prefs = UserNotificationPreferenceRepository(db)

    async def get_preferences(self, current_user: User):
        prefs = await self.prefs.get_for_user(current_user.id)
        if not prefs:
            prefs = await self.prefs.create_default(current_user.id)
        return prefs

    async def update_preferences(self, current_user: User, data: dict):
        prefs = await self.prefs.get_for_user(current_user.id)
        if not prefs:
            prefs = await self.prefs.create_default(current_user.id)

        update_data = {}
        for k in ["push_enabled", "study_reminders", "task_alerts", "referral_bonuses", "wallet_updates", "ad_rewards"]:
            if k in data and data[k] is not None:
                update_data[k] = data[k]

        if "quiet_hours_start" in data:
            val = data["quiet_hours_start"]
            if val:
                h, m = map(int, val.split(":"))
                update_data["quiet_hours_start"] = time_type(h, m)
            else:
                update_data["quiet_hours_start"] = None
        if "quiet_hours_end" in data:
            val = data["quiet_hours_end"]
            if val:
                h, m = map(int, val.split(":"))
                update_data["quiet_hours_end"] = time_type(h, m)
            else:
                update_data["quiet_hours_end"] = None

        return await self.prefs.update(prefs, update_data)

    async def register_fcm_token(self, current_user: User, token: str, platform: str, device_id: str | None):
        existing = await self.fcm_tokens.get_by_token(token)
        if existing:
            return await self.fcm_tokens.update_existing(existing, current_user.id, platform, device_id)
        return await self.fcm_tokens.create(current_user.id, token, platform, device_id)

    async def deregister_fcm_token(self, current_user: User, token: str) -> bool:
        return await self.fcm_tokens.deactivate_by_token(token, current_user.id)

    async def list_fcm_tokens(self, current_user: User):
        return await self.fcm_tokens.list_active_for_user(current_user.id)

    async def list_notifications(self, current_user: User, limit: int = 50, offset: int = 0):
        notifs = await self.notifications.list_for_user(current_user.id, limit=limit, offset=offset)
        unread = await self.notifications.count_unread(current_user.id)
        return notifs, unread

    async def get_notification(self, current_user: User, notification_id: int):
        notif = await self.notifications.get_by_id(notification_id, current_user.id)
        if not notif:
            raise HTTPException(status_code=404, detail="Notification not found")
        return notif

    async def mark_read(self, current_user: User, notification_id: int):
        ok = await self.notifications.mark_read(notification_id, current_user.id)
        if not ok:
            raise HTTPException(status_code=404, detail="Notification not found")

    async def mark_all_read(self, current_user: User):
        await self.notifications.mark_all_read(current_user.id)
