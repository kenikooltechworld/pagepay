"""SMS sending (placeholder). Configure a real provider (Termii/Twilio) later."""

import logging

logger = logging.getLogger("uvicorn.error")


async def send_password_reset_sms(to: str, code: str) -> bool:
    """Send password reset OTP via SMS (placeholder)."""

    logger.info("[SMS placeholder] password reset code for %s: %s", to, code)
    return True
