"""Transaction PIN controller (OOP)."""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import HTTPException, status

from app.models.user import User
from app.repositories.pin_reset_token_repository import PinResetTokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.email_service import send_pin_reset_otp_email
from app.services.sms_service import send_password_reset_sms

logger = logging.getLogger("uvicorn.error")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode(), bcrypt.gensalt(rounds=10)).decode()


def _verify_otp(otp: str, otp_hash: str) -> bool:
    try:
        return bcrypt.checkpw(otp.encode(), otp_hash.encode())
    except Exception:
        return False


class PinController:
    """Orchestrates transaction PIN use-cases."""

    def __init__(self, db):
        self.db = db
        self.users = UserRepository(db)
        self.auth = AuthService(db)
        self.pin_reset_tokens = PinResetTokenRepository(db)

    async def status(self, current_user: User) -> dict:
        has_pin = current_user.transaction_pin_hash is not None
        logger.info("pin.status user=%s has_pin=%s", current_user.id, has_pin)
        return {"has_pin": has_pin}

    async def setup(self, current_user: User, password: str, pin: str) -> dict:
        logger.info("pin.setup start user=%s", current_user.id)
        if current_user.transaction_pin_hash is not None:
            logger.warning("pin.setup conflict user=%s (already set)", current_user.id)
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="PIN already set. Use /pin/change to update it.")
        if not current_user.password_hash or not self.auth.verify_password(password, current_user.password_hash):
            logger.warning("pin.setup auth failed user=%s (incorrect password)", current_user.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password.")
        current_user.transaction_pin_hash = self.auth.hash_password(pin)
        await self.users.update(current_user)
        logger.info("pin.setup ok user=%s", current_user.id)
        return {"ok": True}

    async def verify(self, current_user: User, pin: str) -> dict:
        logger.info("pin.verify start user=%s", current_user.id)
        if current_user.transaction_pin_hash is None:
            logger.warning("pin.verify not set user=%s", current_user.id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No PIN set. Set one in Profile > Security.")
        if not self.auth.verify_password(pin, current_user.transaction_pin_hash):
            logger.warning("pin.verify failed user=%s (incorrect pin)", current_user.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect PIN.")
        logger.info("pin.verify ok user=%s", current_user.id)
        return {"valid": True}

    async def change(self, current_user: User, current_pin: str, new_pin: str) -> dict:
        logger.info("pin.change start user=%s", current_user.id)
        if current_user.transaction_pin_hash is None:
            logger.warning("pin.change not set user=%s", current_user.id)
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No PIN set. Set one in Profile > Security.")
        if not self.auth.verify_password(current_pin, current_user.transaction_pin_hash):
            logger.warning("pin.change failed user=%s (incorrect current pin)", current_user.id)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect current PIN.")
        current_user.transaction_pin_hash = self.auth.hash_password(new_pin)
        await self.users.update(current_user)
        logger.info("pin.change ok user=%s", current_user.id)
        return {"ok": True}

    async def forgot(self, current_user: User) -> dict:
        """Request OTP to reset transaction PIN (sent to user's email/phone)."""
        logger.info("pin.forgot start user=%s", current_user.id)
        if not current_user.email and not current_user.phone:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No email or phone on account to receive reset code.")

        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_token(raw_token)
        otp = f"{secrets.randbelow(1_000_000):06d}"
        otp_hash = _hash_otp(otp)
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=15)
        otp_expires_at = now + timedelta(minutes=10)

        await self.pin_reset_tokens.invalidate_active_for_user(current_user.id)
        await self.pin_reset_tokens.create(
            current_user.id,
            token_hash,
            expires_at,
            otp_hash=otp_hash,
            otp_expires_at=otp_expires_at,
        )
        try:
            if current_user.email:
                await send_pin_reset_otp_email(current_user.email, otp)
            if current_user.phone:
                await send_password_reset_sms(current_user.phone, otp)
        except Exception:
            logger.exception("pin.forgot send failed user=%s", current_user.id)

        logger.info("pin.forgot ok user=%s", current_user.id)
        return {"ok": True, "message": "If your account has email/phone, a PIN reset code has been sent."}

    async def forgot_verify_otp(self, current_user: User, otp: str) -> dict:
        logger.info("pin.forgot.verify start user=%s", current_user.id)
        row = await self.pin_reset_tokens.get_latest_unused_for_user(current_user.id)
        if not row or not row.otp_hash:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OTP request found. Request a new code.")
        if row.otp_expires_at and datetime.utcnow() > row.otp_expires_at:
            await self.pin_reset_tokens.mark_used(row)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired. Request a new code.")
        if not _verify_otp(otp, row.otp_hash):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

        row.otp_hash = None
        row.otp_expires_at = None
        raw_token = secrets.token_urlsafe(32)
        row.token_hash = _hash_token(raw_token)
        row.expires_at = datetime.utcnow() + timedelta(minutes=15)
        await self.pin_reset_tokens.save(row)
        logger.info("pin.forgot.verify ok user=%s", current_user.id)
        return {"ok": True, "reset_token": raw_token}

    async def reset(self, current_user: User, token: str, new_pin: str) -> dict:
        logger.info("pin.reset start user=%s", current_user.id)
        token_hash = _hash_token(token)
        reset_token = await self.pin_reset_tokens.get_valid_by_hash(token_hash)
        if not reset_token or reset_token.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token.")
        current_user.transaction_pin_hash = self.auth.hash_password(new_pin)
        await self.users.update(current_user)
        await self.pin_reset_tokens.mark_used(reset_token)
        logger.info("pin.reset ok user=%s", current_user.id)
        return {"ok": True}
