"""Welcome bonus business logic (idempotent, best-effort).

Grants points after email verification, sends a welcome email, and creates
an in-app notification. All side effects are best-effort: failures are
logged but never break the verification flow.
"""

import logging

from app.repositories.notification_repository import NotificationRepository
from app.repositories.point_credit_repository import PointCreditRepository
from app.core.config import settings
from app.core.socketio import emit_notification
from app.repositories.user_repository import UserRepository
from app.services.fcm_service import send_push_background
from app.services.email_service import send_email

logger = logging.getLogger("uvicorn.error")


class WelcomeBonusService:
    """Grants the one-time welcome bonus after email verification."""

    def __init__(self, db, users: UserRepository, point_credits: PointCreditRepository):
        self.db = db
        self.users = users
        self.point_credits = point_credits
        self.notifications = NotificationRepository(db)

    async def grant(self, user) -> bool:
        try:
            granted = await self.point_credits.grant_welcome_bonus(user)
            if not granted:
                return False

            # Send welcome email (best-effort).
            if user.email:
                try:
                    html = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #4F46E5;">Welcome to PagePay!</h2>
                        <p>Hi {user.username or 'there'},</p>
                        <p>Your email has been verified and you've received <strong>{settings.welcome_bonus_points} welcome points</strong>!</p>
                        <p>Start reading, studying, and earning more points today.</p>
                        <p style="color: #666; font-size: 14px;">- The PagePay Team</p>
                    </body>
                    </html>
                    """
                    await send_email(user.email, "Welcome to PagePay!", html)
                except Exception as exc:
                    logger.warning("Welcome email failed for user_id=%s: %s", user.id, exc)

            # Create in-app notification (best-effort).
            try:
                notif = await self.notifications.create(
                    user_id=user.id,
                    title="Welcome to PagePay!",
                    body=f"You've received {settings.welcome_bonus_points} welcome points for verifying your email.",
                    category="welcome",
                )
                # Emit real-time Socket.IO notification.
                try:
                    await emit_notification(user.id, {
                        "id": notif.id,
                        "title": notif.title,
                        "body": notif.body,
                        "category": notif.category,
                        "created_at": notif.created_at.isoformat(),
                    })
                except Exception as exc:
                    logger.warning("Socket.IO emit failed for user_id=%s: %s", user.id, exc)

                # Send FCM push notification (background, best-effort).
                try:
                    await send_push_background(
                        user_id=user.id,
                        title="Welcome to PagePay!",
                        body=f"You've received {settings.welcome_bonus_points} welcome points for verifying your email.",
                        data={"type": "welcome_bonus", "points": str(settings.welcome_bonus_points)},
                    )
                except Exception as exc:
                    logger.warning("FCM push failed for user_id=%s: %s", user.id, exc)
            except Exception as exc:
                logger.warning("Welcome notification failed for user_id=%s: %s", user.id, exc)

            return True
        except Exception as exc:
            logger.error("Welcome bonus flow failed for user_id=%s: %s", user.id, exc)
            return False
