"""Auth security service (OOP).

Teaching notes:
- `AuthService` encapsulates password hashing, JWT creation/verification, and
  token revocation. Business rules for auth live here, not in routers.
- Routers/controllers call this service; they never touch bcrypt/jose directly.
- Module-level helpers below exist for FastAPI dependency injection and for
  other modules (e.g. limiter) that need a simple function.
"""

import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.user import RevokedJWT, User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


class AuthService:
    """Service for authentication security operations."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)

    # --- Password hashing (static: no DB needed) ---

    @staticmethod
    def hash_password(password: str) -> str:
        pw = password.encode("utf-8")[:72]
        return bcrypt.hashpw(pw, bcrypt.gensalt(rounds=12)).decode("utf-8")

    @staticmethod
    def generate_referral_code() -> str:
        """Generate a unique 6-char alphanumeric referral code."""

        import random
        import string

        return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False

    # --- JWT access tokens ---

    @staticmethod
    def create_access_token(user_id: int, jti: str | None = None) -> str:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        payload = {
            "sub": str(user_id),
            "exp": expire,
            "type": "access",
            "jti": jti or secrets.token_hex(16),
        }
        return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)

    @staticmethod
    def decode_access_token(token: str) -> dict:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])

    @staticmethod
    def create_refresh_token() -> str:
        return secrets.token_urlsafe(64)

    # --- Revocation ---

    async def revoke_jwt(self, jti: str, user_id: int, reason: str | None = None, expires_at: datetime | None = None) -> None:
        # Align revocation TTL with the token's actual expiry (or fall back to
        # access token lifetime from settings) so revocations neither outlive
        # nor underlive the token.
        if expires_at is None:
            expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
        self.db.add(RevokedJWT(jti=jti, user_id=user_id, reason=reason, expires_at=expires_at))
        await self.db.commit()

    async def is_jwt_revoked(self, jti: str) -> bool:
        from sqlalchemy import select

        result = await self.db.execute(
            select(RevokedJWT).where(RevokedJWT.jti == jti, RevokedJWT.expires_at > datetime.utcnow())
        )
        return result.scalar_one_or_none() is not None

    # --- Current user resolution (FastAPI dependency) ---

    async def resolve_current_user(self, token: str) -> User:
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        try:
            payload = self.decode_access_token(token)
            user_id = payload.get("sub")
            jti = payload.get("jti")
            if user_id is None or jti is None:
                raise credentials_exception
        except JWTError:
            raise credentials_exception

        if await self.is_jwt_revoked(jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has been revoked",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user = await self.users.get_by_id(int(user_id))
        if user is None:
            raise credentials_exception
        if user.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active",
            )
        return user


# --- Module-level helpers for FastAPI DI and other modules ---

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    return await AuthService(db).resolve_current_user(token)


def hash_password(password: str) -> str:
    return AuthService.hash_password(password)


def verify_password(password: str, password_hash: str) -> bool:
    return AuthService.verify_password(password, password_hash)


def create_access_token(user_id: int, jti: str | None = None) -> str:
    return AuthService.create_access_token(user_id, jti)


def decode_access_token(token: str) -> dict:
    return AuthService.decode_access_token(token)


def create_refresh_token() -> str:
    return AuthService.create_refresh_token()


async def revoke_jwt(db: AsyncSession, jti: str, user_id: int, reason: str | None = None, expires_at: datetime | None = None) -> None:
    await AuthService(db).revoke_jwt(jti, user_id, reason, expires_at)


async def is_jwt_revoked(db: AsyncSession, jti: str) -> bool:
    return await AuthService(db).is_jwt_revoked(jti)
