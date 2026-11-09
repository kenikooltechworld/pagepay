"""Forgot-password / reset business logic (OOP)."""

import secrets
from datetime import datetime, timedelta

from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import send_password_reset_otp_email
from app.services.sms_service import send_password_reset_sms


# In-memory OTP store (process-local, dev convenience). Keyed by identity.
_dev_otps: dict[str, tuple[str, str, datetime]] = {}


def _cleanup_expired_otps() -> None:
    now = datetime.utcnow()
    expired = [k for k, (_, _, exp) in _dev_otps.items() if exp < now]
    for k in expired:
        del _dev_otps[k]


class PasswordResetService:
    """Handles forgot-password OTP flow and token-based reset."""

    def __init__(self, db, users: UserRepository, reset_tokens: PasswordResetTokenRepository):
        self.db = db
        self.users = users
        self.reset_tokens = reset_tokens

    async def request_reset(self, payload) -> dict:
        if not payload.email and not payload.phone and not payload.username:
            raise ValueError("Email, phone, or username required")

        user = None
        if payload.email:
            user = await self.users.get_by_email(payload.email)
        elif payload.phone:
            user = await self.users.get_by_phone(payload.phone)
        elif payload.username:
            user = await self.users.get_by_username(payload.username)

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        expires_at = datetime.utcnow() + timedelta(minutes=15)

        if user:
            await self.reset_tokens.create(user.id, token_hash, expires_at)

        otp = f"{secrets.randbelow(1_000_000):06d}"
        _cleanup_expired_otps()
        key = payload.email or payload.phone or payload.username or ""
        _dev_otps[key] = (otp, raw_token, datetime.utcnow() + timedelta(minutes=15))

        if user:
            try:
                if user.email:
                    await send_password_reset_otp_email(user.email, otp)
                if user.phone:
                    await send_password_reset_sms(user.phone, otp)
            except Exception:
                pass

        return {"ok": True, "dev_otp": otp, "message": "If that account exists, a reset code has been sent."}

    @staticmethod
    def verify_otp(payload) -> str:
        key = payload.email or payload.phone or payload.username or ""
        stored = _dev_otps.get(key)
        if not stored:
            raise ValueError("No OTP request found. Request a new code.")
        otp, raw_token, expires_at = stored
        if datetime.utcnow() > expires_at:
            del _dev_otps[key]
            raise ValueError("OTP expired. Request a new code.")
        if payload.otp != otp:
            raise ValueError("Invalid OTP")
        del _dev_otps[key]
        return raw_token

    async def reset(self, token: str, new_password: str) -> None:
        from app.services.auth_service import hash_password

        token_hash = _hash_token(token)
        reset_token = await self.reset_tokens.get_valid_by_hash(token_hash)
        if not reset_token:
            raise ValueError("Invalid or expired reset token")

        user = await self.users.get_by_id(reset_token.user_id)
        if not user:
            raise ValueError("User not found")

        user.password_hash = hash_password(new_password)
        await self.users.update(user)
        await self.reset_tokens.mark_used(reset_token)


def _hash_token(token: str) -> str:
    import hashlib

    return hashlib.sha256(token.encode()).hexdigest()
