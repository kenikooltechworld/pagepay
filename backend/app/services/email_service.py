"""Email sending via Resend (best-effort helpers for auth flows)."""

import logging

import resend

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

resend.api_key = settings.resend_api_key or ""


async def send_email(to: str, subject: str, html: str) -> bool:
    """Send an email using Resend. Returns True on success, False otherwise."""

    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not configured; email not sent")
        return False

    try:
        result = resend.Emails.send(
            params={
                "from": settings.email_from,
                "to": to,
                "subject": subject,
                "html": html,
            }
        )
        logger.info("Email sent to %s: %s", to, result.get("id", "unknown"))
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to, exc)
        return False


async def send_verification_email(to: str, token: str, code: str) -> bool:
    """Send email verification with a 6-digit code and a fallback link."""

    verify_url = f"{settings.public_base_url}/verify-email?email={to}&token={token}"
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4F46E5;">Verify your email address</h2>
        <p>Thanks for signing up for PagePay! Enter this 6-digit code in the app to verify your email:</p>
        <div style="background-color: #F3F4F6; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #4F46E5;">{code}</span>
        </div>
        <p style="color: #666; font-size: 14px;">This code will expire in 24 hours.</p>
        <p style="color: #666; font-size: 14px;">If you didn't create an account, you can safely ignore this email.</p>
        <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;">
        <p style="color: #9CA3AF; font-size: 12px;">Or click the link below:</p>
        <a href="{verify_url}" style="color: #4F46E5; font-size: 14px;">{verify_url}</a>
    </body>
    </html>
    """
    return await send_email(to, "Verify your PagePay account", html)


async def send_password_reset_otp_email(to: str, otp: str) -> bool:
    """Send password reset OTP code via email."""

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4F46E5;">Reset your password</h2>
        <p>You requested to reset your password. Enter this 6-digit code in the app:</p>
        <div style="background-color: #F3F4F6; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #4F46E5;">{otp}</span>
        </div>
        <p style="color: #666; font-size: 14px;">This code will expire in 15 minutes.</p>
        <p style="color: #666; font-size: 14px;">If you didn't request a password reset, you can safely ignore this email.</p>
    </body>
    </html>
    """
    return await send_email(to, "Reset your PagePay password", html)
async def send_pin_reset_otp_email(to: str, otp: str) -> bool:
    """Send transaction PIN reset OTP code via email."""

    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #4F46E5;">Reset your transaction PIN</h2>
        <p>You requested to reset your PagePay transaction PIN. Enter this 6-digit code in the app:</p>
        <div style="background-color: #F3F4F6; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #4F46E5;">{otp}</span>
        </div>
        <p style="color: #666; font-size: 14px;">This code will expire in 10 minutes.</p>
        <p style="color: #666; font-size: 14px;">If you didn't request a PIN reset, you can safely ignore this email.</p>
    </body>
    </html>
    """
    return await send_email(to, "Reset your PagePay transaction PIN", html)
