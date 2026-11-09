"""Firebase Cloud Messaging service for push notifications (simplified)."""

import json
import logging
import os
from typing import Optional

import firebase_admin
from firebase_admin import credentials, messaging
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import FCMToken

logger = logging.getLogger("uvicorn.error")

_firebase_app = None


def initialize_firebase():
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    info = None
    raw_json = settings.firebase_service_account_key
    if raw_json:
        info = json.loads(raw_json.strip())
    else:
        path = settings.firebase_service_account_file
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                info = json.load(f)

    if not info:
        logger.warning("Firebase service account not configured; push notifications disabled")
        return None

    try:
        cred = credentials.Certificate(info)
        _firebase_app = firebase_admin.initialize_app(cred)
        logger.info("Firebase Admin initialized (project_id=%s)", info.get("project_id"))
        return _firebase_app
    except Exception as exc:
        logger.error("Firebase init failed: %s", exc)
        return None


async def send_push_notification(
    db: AsyncSession,
    user_id: int,
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> bool:
    if _firebase_app is None:
        initialize_firebase()
    if _firebase_app is None:
        return False

    result = await db.execute(
        select(FCMToken).where(FCMToken.user_id == user_id, FCMToken.is_active == True)  # noqa: E712
    )
    tokens = result.scalars().all()
    if not tokens:
        logger.info("No active FCM tokens for user %d", user_id)
        return False

    success = False
    for fcm_token in tokens:
        try:
            message = messaging.Message(
                notification=messaging.Notification(title=title, body=body),
                data=data or {},
                token=fcm_token.token,
            )
            messaging.send(message)
            success = True
        except Exception as exc:
            logger.warning("FCM send failed for user %d: %s", user_id, exc)
            # Deactivate invalid tokens
            if "Unregistered" in str(exc) or "invalid" in str(exc).lower():
                await db.execute(
                    update(FCMToken).where(FCMToken.token == fcm_token.token).values(is_active=False)
                )
                await db.commit()
    return success


async def send_push_background(user_id: int, title: str, body: str, data: Optional[dict] = None):
    """Send push in a background task with its own DB session."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        try:
            await send_push_notification(db, user_id, title, body, data)
        except Exception as exc:
            logger.error("Background push failed: %s", exc)
