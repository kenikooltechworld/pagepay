"""Forgot-password / reset business logic (OOP).

OTP + reset-token state is persisted in `password_reset_tokens` (hashed) so it works
across gunicorn workers and process restarts. The raw reset token is returned to the
client only after OTP verification.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt

from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.email_service import send_password_reset_otp_email
from app.services.sms_service import send_password_reset_sms


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt(rounds=10)).decode()


def _verify_otp(otp: str, otp_hash: str) -> bool:
    try:
        return bcrypt.checkpw(otp.encode(), otp_hash.encode())
    except Exception:
        return False


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
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = _hash_otp(otp)
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=15)
        otp_expires_at = now + timedelta(minutes=10)

        if user:
            # Invalidate previous active reset tokens for this user.
            await self.reset_tokens.invalidate_active_for_user(user.id)
            await self.reset_tokens.create(
                user.id,
                token_hash,
                expires_at,
                otp_hash=otp_hash,
                otp_expires_at=otp_expires_at,
            )
            try:
                if user.email:
                    await send_password_reset_otp_email(user.email, otp)
                if user.phone:
                    await send_password_reset_sms(user.phone, otp)
            except Exception:
                pass

        # Never return OTP in API responses.
        return {"ok": True, "message": "If that account exists, a reset code has been sent."}

    async def verify_otp(self, payload) -> str:
        if not payload.email and not payload.phone and not payload.username:
            raise ValueError("Email, phone, or username required")

        user = None
        if payload.email:
            user = await self.users.get_by_email(payload.email)
        elif payload.phone:
            user = await self.users.get_by_phone(payload.phone)
        elif payload.username:
            user = await self.users.get_by_username(payload.username)
        if not user:
            raise ValueError("No OTP request found. Request a new code.")

        row = await self.reset_tokens.get_latest_unused_for_user(user.id)
        if not row or not row.otp_hash:
            raise ValueError("No OTP request found. Request a new code.")
        if row.otp_expires_at and datetime.utcnow() > row.otp_expires_at:
            await self.reset_tokens.mark_used(row)
            raise ValueError("OTP expired. Request a new code.")
        if not _verify_otp(payload.otp, row.otp_hash):
            raise ValueError("Invalid OTP")

        # Consume OTP but keep reset token valid until password reset (single use via used_at on reset).
        row.otp_hash = None
        row.otp_expires_at = None
        await self.reset_tokens.save(row)

        # Return the raw token is not stored; we cannot recover it. Instead, issue a fresh reset token
        # bound to the same verified row and return that raw token.
        raw_token = secrets.token_urlsafe(32)
        row.token_hash = _hash_token(raw_token)
        row.expires_at = datetime.utcnow() + timedelta(minutes=15)
        await self.reset_tokens.save(row)
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
