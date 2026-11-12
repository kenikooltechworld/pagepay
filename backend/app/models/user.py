"""Auth-related database models (minimal set for register/login/logout/refresh).

Teaching notes:
- Each class maps to a DB table via SQLAlchemy's declarative ORM.
- `Mapped[...]` + `mapped_column(...)` declare typed columns (SQLAlchemy 2.0 style).
- Passwords/tokens are NEVER stored in plain text here: we store hashes.
- We keep this file focused on auth; other domains (wallet, study, etc.) can live
  in their own model modules and be imported into `app.models` later.
"""

import enum
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, Integer, JSON, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class UserTier(enum.Enum):
    """Subscription tier. Stored as an enum in the DB (matches reference app)."""

    FREE = "free"
    STUDY_PLUS_MONTHLY = "study_plus_monthly"
    STUDY_PLUS_YEARLY = "study_plus_yearly"
    COMPLETE_PLUS_MONTHLY = "complete_plus_monthly"
    COMPLETE_PLUS_YEARLY = "complete_plus_yearly"


class User(Base):
    __tablename__ = "users"

    # Primary key. `autoincrement=True` lets the DB assign ids.
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)

    # Identity: at least one of email/phone is required at the API layer.
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(12), unique=True, index=True, nullable=True)

    # Bcrypt hash of the password (or NULL for future OAuth-only users).
    password_hash: Mapped[str | None] = mapped_column(String(255))

    # Account state / profile basics needed by auth responses.
    points_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    service_credit_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    cashable_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    tier: Mapped[UserTier] = mapped_column(Enum(UserTier), default=UserTier.FREE)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)  # active|banned|suspended
    referrals_today_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # --- Auth security / lockout ---
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Email verification
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    # Bcrypt-hashed verification token (sent via link) and 6-digit code (sent via email).
    email_verification_token: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verification_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verification_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

# Minimal login metadata (useful for audit/security). Filled on login.
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_login_ip: Mapped[str | None] = mapped_column(String(45), nullable=True)
    last_login_user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Avatar URL (Cloudflare R2 public URL). Set by the avatar upload flow.
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Referral system.
    referral_code: Mapped[str | None] = mapped_column(String(12), unique=True, index=True, nullable=True)
    referred_by: Mapped[str | None] = mapped_column(String(12), nullable=True)

    # Transaction PIN (bcrypt-hashed). Used for wallet withdrawals.
    transaction_pin_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Device fingerprint (for fraud detection).
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Legacy/feature flags present in existing Neon schema (NOT NULL, no defaults in DB).
    # We set safe defaults so inserts from this minimal auth slice succeed. When we
    # port the full feature set, move these to their proper domain modules.
    is_worker: Mapped[bool] = mapped_column(Boolean, default=True)
    is_sponsor: Mapped[bool] = mapped_column(Boolean, default=False)
    sponsor_wallet_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    sponsor_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    sponsor_kyc_status: Mapped[str] = mapped_column(String(20), default="none")
    sponsor_auto_approve_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    country: Mapped[str] = mapped_column(String(50), default="Nigeria")


class RefreshToken(Base):
    """Opaque refresh token record. We store only a SHA-256 hash, not the token."""

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True)
    # SHA-256 hex digest of the raw refresh token sent to the client.
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    # Set True when rotated/revoked so it can't be reused.
    revoked: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RevokedJWT(Base):
    """Revoked access-token JTIs (logout/password change). Checked on each authed request."""

    __tablename__ = "revoked_jwts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)  # logout | password_change
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base):
    """Single-use token for the forgot-password flow.

    OTP is stored hashed (for verify-otp) so it works across gunicorn workers and restarts.
    The raw reset token is returned to the client only after OTP verification.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # Bcrypt hash of the 6-digit OTP (verified before releasing reset token).
    otp_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PinResetToken(Base):
    """Single-use token for the forgot-PIN flow (transaction PIN reset)."""

    __tablename__ = "pin_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    otp_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    otp_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PointCredit(Base):
    """Audit row for points credited. UNIQUE(user_id, source) makes grants idempotent."""

    __tablename__ = "point_credits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    points: Mapped[int] = mapped_column(BigInteger, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class UserAuditLog(Base):
    """Audit trail of user actions (login, verify, password reset, etc.)."""

    __tablename__ = "user_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(50), index=True, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    extra_data: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Notification(Base):
    """In-app notification for a user."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class FCMToken(Base):
    """Firebase Cloud Messaging token for a user's device."""

    __tablename__ = "fcm_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    token: Mapped[str] = mapped_column(String(512), nullable=False)
    platform: Mapped[str | None] = mapped_column(String(20), nullable=True)
    device_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UserNotificationPreference(Base):
    """Per-user notification preferences."""

    __tablename__ = "user_notification_preferences"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    study_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    task_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    referral_bonuses: Mapped[bool] = mapped_column(Boolean, default=True)
    wallet_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    ad_rewards: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_start: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    quiet_hours_end: Mapped[datetime | None] = mapped_column(Time, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
