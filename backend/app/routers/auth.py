"""Auth HTTP routes (thin layer)."""

from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from app.controllers.auth_controller import AuthController
from app.core.config import settings
from app.core.database import get_db
from app.limiter import limiter
from app.models.user import User
from app.schemas.auth import (
    AuditLogsResponse,
    AvatarUploadRequest,
    ChangePasswordRequest,
    UserUpdate,
    DeleteAccountRequest,
    EmailVerificationCodeRequest,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    ForgotPasswordVerifyOtpRequest,
    ForgotPasswordVerifyOtpResponse,
    GoogleAuthRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    UserMe,
    UserRegister,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


def get_controller(db=Depends(get_db)) -> AuthController:
    return AuthController(db)


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: UserRegister, controller: AuthController = Depends(get_controller)):
    return await controller.register(payload)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.auth_login_rate_limit)
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    controller: AuthController = Depends(get_controller),
):
    return await controller.login(request, form)


@router.get("/me", response_model=UserMe)
async def me(current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    return await controller.me(current_user)


@router.patch("/me", response_model=UserMe)
async def update_profile(request: Request, payload: UserUpdate, current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    return await controller.update_profile(request, current_user, payload)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, controller: AuthController = Depends(get_controller)):
    return await controller.refresh(payload)


@router.post("/change-password")
async def change_password(request: Request, payload: ChangePasswordRequest, current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    return await controller.change_password(request, current_user, payload)


@router.post("/logout", status_code=204)
async def logout(request: Request, current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    await controller.logout(request, current_user)
    return None


@router.post("/verify-email")
async def verify_email(payload: EmailVerificationRequest, controller: AuthController = Depends(get_controller)):
    return await controller.verify_email(payload)


@router.post("/verify-email-code")
async def verify_email_code(payload: EmailVerificationCodeRequest, controller: AuthController = Depends(get_controller)):
    return await controller.verify_email_code(payload)


@router.post("/resend-verification")
async def resend_verification(current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    return await controller.resend_verification(current_user)


@router.post("/forgot-password")
async def forgot_password(payload: ForgotPasswordRequest, controller: AuthController = Depends(get_controller)):
    return await controller.forgot_password(payload)


@router.post("/forgot-password/verify-otp", response_model=ForgotPasswordVerifyOtpResponse)
async def verify_forgot_otp(payload: ForgotPasswordVerifyOtpRequest, controller: AuthController = Depends(get_controller)):
    return await controller.verify_forgot_otp(payload)


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest, controller: AuthController = Depends(get_controller)):
    return await controller.reset_password(payload)


@router.post("/google", response_model=TokenResponse)
async def google_auth(payload: GoogleAuthRequest, controller: AuthController = Depends(get_controller)):
    return await controller.google_auth(payload)


@router.post("/me/avatar")
async def upload_avatar(payload: AvatarUploadRequest, current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    return await controller.upload_avatar(current_user, payload.image)


@router.delete("/me", status_code=204)
async def delete_account(request: Request, payload: DeleteAccountRequest, current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    await controller.delete_account(request, current_user, payload)
    return None


@router.get("/audit-logs", response_model=AuditLogsResponse)
async def audit_logs(limit: int = 50, offset: int = 0, current_user: User = Depends(get_current_user), controller: AuthController = Depends(get_controller)):
    return await controller.get_audit_logs(current_user, limit=limit, offset=offset)
