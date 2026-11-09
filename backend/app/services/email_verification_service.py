"""Email verification business logic (OOP)."""

import secrets
from datetime import datetime, timedelta

import bcrypt

from app.core.config import settings
from app.repositories.user_repository import UserRepository
from app.services.email_service import send_verification_email


class EmailVerificationService:
    """Handles issuing and verifying email verification tokens/codes."""

    def __init__(self, db, user_repo: UserRepository):
        self.db = db
        self.users = user_repo

    async def issue(self, user) -> tuple[str, str]:
        """Generate a verification token + 6-digit code, hash and store them.

        Returns the raw (token, code) for sending via email.
        """

        token_raw = secrets.token_urlsafe(32)
        code_raw = f"{secrets.randbelow(1_000_000):06d}"
        user.email_verification_token = bcrypt.hashpw(
            token_raw.encode(), bcrypt.gensalt(rounds=10)
        ).decode()
        user.email_verification_code = bcrypt.hashpw(
            code_raw.encode(), bcrypt.gensalt(rounds=10)
        ).decode()
        user.email_verification_expires_at = datetime.utcnow() + timedelta(hours=24)
        # Persist happens in UserRepository.create(); here we only mutate in-memory.
        return token_raw, code_raw

    async def verify_by_token(self, email: str, token: str) -> None:
        user = await self.users.get_by_email(email)
        if not user or user.email_verified:
            raise ValueError("Invalid verification token or email already verified")
        if not user.email_verification_token:
            raise ValueError("No pending verification for this email")
        if not user.email_verification_expires_at or user.email_verification_expires_at < datetime.utcnow():
            raise ValueError("Verification token expired. Request a new one.")
        try:
            ok = bcrypt.checkpw(token.encode(), user.email_verification_token.encode())
        except (ValueError, TypeError):
            ok = False
        if not ok:
            raise ValueError("Invalid verification token")

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_code = None
        user.email_verification_expires_at = None
        await self.users.update(user)

    async def verify_by_code(self, email: str, code: str) -> None:
        user = await self.users.get_by_email(email)
        if not user or user.email_verified:
            raise ValueError("Invalid code or email already verified")
        if not user.email_verification_code:
            raise ValueError("No pending verification for this email")
        if not user.email_verification_expires_at or user.email_verification_expires_at < datetime.utcnow():
            raise ValueError("Verification code expired. Request a new one.")
        try:
            ok = bcrypt.checkpw(code.encode(), user.email_verification_code.encode())
        except (ValueError, TypeError):
            ok = False
        if not ok:
            raise ValueError("Invalid verification code")

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_code = None
        user.email_verification_expires_at = None
        await self.users.update(user)

    async def resend(self, user) -> tuple[str, str]:
        return await self.issue(user)
