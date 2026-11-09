"""Notification controller (OOP)."""

import json
import logging
from datetime import datetime, time as time_type

from fastapi import HTTPException

from app.models.user import Notification, User
from app.repositories.fcm_token_repository import FCMTokenRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_notification_preference_repository import UserNotificationPreferenceRepository

logger = logging.getLogger("uvicorn.error")


class NotificationController:
    """Orchestrates notification use-cases."""

    def __init__(self, db):
        self.db = db
        self.notifications = NotificationRepository(db)
        self.fcm_tokens = FCMTokenRepository(db)
        self.prefs = UserNotificationPreferenceRepository(db)

    async def get_preferences(self, current_user: User):
        logger.info("notifications.prefs.get user=%s", current_user.id)
        prefs = await self.prefs.get_for_user(current_user.id)
        if not prefs:
            prefs = await self.prefs.create_default(current_user.id)
        logger.info("notifications.prefs.get result user=%s push_enabled=%s", current_user.id, prefs.push_enabled)
        return prefs

    async def update_preferences(self, current_user: User, data: dict):
        logger.info("notifications.prefs.update user=%s keys=%s", current_user.id, list(data.keys()))
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

        res = await self.prefs.update(prefs, update_data)
        logger.info("notifications.prefs.update ok user=%s updated=%s", current_user.id, list(update_data.keys()))
        return res

    async def register_fcm_token(self, current_user: User, token: str, platform: str, device_id: str | None):
        logger.info("notifications.fcm.register user=%s platform=%s device_id=%s token_prefix=%s", current_user.id, platform, device_id, (token or "")[:12])
        existing = await self.fcm_tokens.get_by_token(token)
        if existing:
            res = await self.fcm_tokens.update_existing(existing, current_user.id, platform, device_id)
            logger.info("notifications.fcm.register updated user=%s token_id=%s", current_user.id, getattr(res, "id", None))
            return res
        res = await self.fcm_tokens.create(current_user.id, token, platform, device_id)
        logger.info("notifications.fcm.register created user=%s token_id=%s", current_user.id, getattr(res, "id", None))
        return res

    async def deregister_fcm_token(self, current_user: User, token: str) -> bool:
        logger.info("notifications.fcm.deregister user=%s token_prefix=%s", current_user.id, (token or "")[:12])
        ok = await self.fcm_tokens.deactivate_by_token(token, current_user.id)
        logger.info("notifications.fcm.deregister result user=%s ok=%s", current_user.id, ok)
        return ok

    async def list_fcm_tokens(self, current_user: User):
        logger.info("notifications.fcm.list user=%s", current_user.id)
        return await self.fcm_tokens.list_active_for_user(current_user.id)

    async def list_notifications(self, current_user: User, limit: int = 50, offset: int = 0):
        logger.info("notifications.list user=%s limit=%s offset=%s", current_user.id, limit, offset)
        notifs = await self.notifications.list_for_user(current_user.id, limit=limit, offset=offset)
        unread = await self.notifications.count_unread(current_user.id)
        logger.info("notifications.list result user=%s count=%s unread=%s", current_user.id, len(notifs), unread)
        return notifs, unread

    async def get_notification(self, current_user: User, notification_id: int):
        logger.info("notifications.get user=%s notification_id=%s", current_user.id, notification_id)
        notif = await self.notifications.get_by_id(notification_id, current_user.id)
        if not notif:
            logger.warning("notifications.get not found user=%s notification_id=%s", current_user.id, notification_id)
            raise HTTPException(status_code=404, detail="Notification not found")
        return notif

    async def mark_read(self, current_user: User, notification_id: int):
        logger.info("notifications.mark_read user=%s notification_id=%s", current_user.id, notification_id)
        ok = await self.notifications.mark_read(notification_id, current_user.id)
        if not ok:
            logger.warning("notifications.mark_read not found user=%s notification_id=%s", current_user.id, notification_id)
            raise HTTPException(status_code=404, detail="Notification not found")
        logger.info("notifications.mark_read ok user=%s notification_id=%s", current_user.id, notification_id)

    async def mark_all_read(self, current_user: User):
        logger.info("notifications.mark_all_read user=%s", current_user.id)
        await self.notifications.mark_all_read(current_user.id)
        logger.info("notifications.mark_all_read ok user=%s", current_user.id)
