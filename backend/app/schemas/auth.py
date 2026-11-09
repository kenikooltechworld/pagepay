"""Pydantic schemas (request/response shapes) for auth endpoints.

Teaching notes:
- Schemas validate incoming JSON/form-derived data and shape outgoing responses.
- They are NOT the same as ORM models: models = DB tables; schemas = API contracts.
- FastAPI uses these for validation, docs (OpenAPI), and serialization.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegister(BaseModel):
    """POST /auth/register body."""

    email: EmailStr | None = None
    phone: str | None = None
    username: str | None = Field(default=None, max_length=12)
    password: str = Field(min_length=8)
    referral_code: str | None = Field(default=None, max_length=12)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip().lower()
        if len(v) > 12:
            raise ValueError("Username must be 12 characters or less")
        if not v:
            return None
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_")
        if not all(c in allowed for c in v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        reserved = {"admin", "support", "system", "help", "info", "null", "undefined", "pagepay"}
        if v in reserved:
            raise ValueError("Username is reserved")
        return v


class TokenResponse(BaseModel):
    """Returned on register/login/refresh: short-lived access + long-lived refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserMe(BaseModel):
    """Safe user profile returned by /auth/me (no password_hash)."""

    id: int
    email: str | None
    phone: str | None
    username: str | None
    tier: str
    role: str
    status: str
    created_at: datetime
    email_verified: bool = False
    avatar_url: str | None = None
    transaction_pin_set: bool = False
    referral_code: str | None = None
    referred_by: str | None = None

    model_config = ConfigDict(from_attributes=True)


class RefreshRequest(BaseModel):
    """POST /auth/refresh body."""

    refresh_token: str


class EmailVerificationRequest(BaseModel):
    """POST /auth/verify-email body (token-based)."""

    email: str
    token: str


class EmailVerificationCodeRequest(BaseModel):
    """POST /auth/verify-email-code body (6-digit code)."""

    email: str
    code: str


class ForgotPasswordRequest(BaseModel):
    """POST /auth/forgot-password body."""

    email: str | None = None
    phone: str | None = None
    username: str | None = None


class ForgotPasswordVerifyOtpRequest(BaseModel):
    """POST /auth/forgot-password/verify-otp body."""

    email: str | None = None
    phone: str | None = None
    username: str | None = None
    otp: str = Field(min_length=6, max_length=6)


class ForgotPasswordVerifyOtpResponse(BaseModel):
    """Response after OTP verification."""

    ok: bool
    reset_token: str | None = None


class ResetPasswordRequest(BaseModel):
    """POST /auth/reset-password body."""

    token: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v


class GoogleAuthRequest(BaseModel):
    """POST /auth/google body."""

    id_token: str = Field(min_length=10, max_length=4096)


class UserUpdate(BaseModel):
    """PATCH /me body."""

    username: str | None = None
    avatar_url: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str | None) -> str | None:
        if v is None or v == "":
            return None
        v = v.strip().lower()
        if len(v) > 12:
            raise ValueError("Username must be 12 characters or less")
        if not v:
            return None
        allowed = set("abcdefghijklmnopqrstuvwxyz0123456789_")
        if not all(c in allowed for c in v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        reserved = {"admin", "support", "system", "help", "info", "null", "undefined", "pagepay"}
        if v in reserved:
            raise ValueError("Username is reserved")
        return v


class ChangePasswordRequest(BaseModel):
    """POST /auth/change-password body."""

    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain at least one digit")
        if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`" for c in v):
            raise ValueError("Password must contain at least one special character")
        return v


class DeleteAccountRequest(BaseModel):
    """DELETE /auth/me body."""

    password: str = Field(min_length=6, description="Current account password for confirmation")
    confirmation: str = Field(pattern="^DELETE$", description="Must be exactly 'DELETE' to confirm")


class UserAuditLog(BaseModel):
    """Audit log entry returned by /auth/audit-logs."""

    id: int
    action: str
    ip_address: str | None = None
    user_agent: str | None = None
    device_fingerprint: str | None = None
    extra_data: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogsResponse(BaseModel):
    """Paginated audit logs response."""

    logs: list[UserAuditLog]
    total: int


class AvatarUploadRequest(BaseModel):
    """POST /auth/me/avatar body."""

    image: str = Field(description="Base64-encoded image (data:image/...;base64,...)")


class SetTransactionPinRequest(BaseModel):
    """POST /auth/me/pin body."""

    pin: str = Field(min_length=4, max_length=6, description="4-6 digit transaction PIN")
    current_password: str | None = Field(default=None, description="Current account password (required if PIN already set)")


class VerifyTransactionPinRequest(BaseModel):
    """POST /auth/me/pin/verify body."""

    pin: str = Field(min_length=4, max_length=6)
