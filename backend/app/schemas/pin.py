"""Pydantic schemas for transaction PIN endpoints."""

from pydantic import BaseModel, Field


class PinSetupRequest(BaseModel):
    """Set transaction PIN for the first time."""

    password: str = Field(min_length=8)
    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")


class PinVerifyRequest(BaseModel):
    """Verify transaction PIN."""

    pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")


class PinChangeRequest(BaseModel):
    """Change transaction PIN."""

    current_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")
    new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")


class PinStatusResponse(BaseModel):
    """PIN status response."""

    has_pin: bool


class PinForgotVerifyOtpRequest(BaseModel):
    """Verify OTP for PIN reset."""

    otp: str = Field(min_length=6, max_length=6, pattern=r"^\d+$")


class PinForgotVerifyOtpResponse(BaseModel):
    ok: bool
    reset_token: str | None = None


class PinResetRequest(BaseModel):
    """Reset PIN using verified reset token."""

    token: str = Field(min_length=10)
    new_pin: str = Field(min_length=4, max_length=6, pattern=r"^\d+$")
