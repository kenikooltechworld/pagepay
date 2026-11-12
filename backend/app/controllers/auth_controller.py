"""Auth controller (OOP): orchestrates use-cases by combining services/repos."""

import hashlib
import secrets
from datetime import datetime, timedelta

import bcrypt
from fastapi import HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import RefreshToken, User
from app.repositories.password_reset_token_repository import PasswordResetTokenRepository
from app.repositories.point_credit_repository import PointCreditRepository
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.user_audit_repository import UserAuditLogRepository
from app.repositories.user_repository import UserRepository
from app.schemas.auth import (
    AuditLogsResponse,
    DeleteAccountRequest,
    EmailVerificationCodeRequest,
    EmailVerificationRequest,
    ForgotPasswordRequest,
    ForgotPasswordVerifyOtpRequest,
    GoogleAuthRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenResponse,
    ChangePasswordRequest,
    UserMe,
    UserRegister,
    UserUpdate,
)
from app.services.auth_service import (
    AuthService,
    create_access_token,
    create_refresh_token,
    decode_access_token,
)
from app.services.email_verification_service import EmailVerificationService
from app.services.password_reset_service import PasswordResetService
from app.services.welcome_bonus_service import WelcomeBonusService
from app.services.cloudflare_r2 import CloudflareR2Service


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _get_jti_from_request(request: Request) -> str | None:
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    try:
        payload = decode_access_token(auth_header[7:])
        jti = payload.get("jti")
        return jti if isinstance(jti, str) else None
    except Exception:
        return None


class AuthController:
    """Orchestrates all auth use-cases."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.users = UserRepository(db)
        self.refresh_tokens = RefreshTokenRepository(db)
        self.reset_tokens = PasswordResetTokenRepository(db)
        self.point_credits = PointCreditRepository(db)
        self.audit_logs = UserAuditLogRepository(db)
        self.auth = AuthService(db)
        self.email_verification = EmailVerificationService(db, self.users)
        self.password_reset = PasswordResetService(db, self.users, self.reset_tokens)
        self.welcome_bonus = WelcomeBonusService(db, self.users, self.point_credits)
        self.r2 = CloudflareR2Service()

    async def _ensure_referral_code(self, user: User) -> str:
        """Guarantee the user has a unique referral code (self-heal for legacy users)."""
        if user.referral_code:
            return user.referral_code
        code = self.auth.generate_referral_code()
        while await self.users.get_by_referral_code(code):
            code = self.auth.generate_referral_code()
        user.referral_code = code
        await self.users.update(user)
        return code

    # --- register ---
    async def register(self, payload: UserRegister) -> TokenResponse:
        if not payload.email and not payload.phone:
            raise HTTPException(status_code=400, detail="Email or phone required")

        if payload.email:
            existing = await self.users.get_by_email(payload.email)
            if existing:
                raise HTTPException(status_code=400, detail="User already exists")
        if payload.phone:
            existing = await self.users.get_by_phone(payload.phone)
            if existing:
                raise HTTPException(status_code=400, detail="User already exists")
        if payload.username:
            existing = await self.users.get_by_username(payload.username)
            if existing:
                raise HTTPException(status_code=400, detail="Username already taken")

        # Validate referral code if provided.
        if payload.referral_code:
            referrer = await self.users.get_by_referral_code(payload.referral_code)
            if not referrer:
                raise HTTPException(status_code=400, detail="Invalid referral code. Check the code and try again.")

        # Generate unique referral code.
        unique_referral_code = self.auth.generate_referral_code()
        while True:
            dup = await self.users.get_by_referral_code(unique_referral_code)
            if not dup:
                break
            unique_referral_code = self.auth.generate_referral_code()

        user = User(
            email=payload.email,
            phone=payload.phone,
            username=payload.username.lower() if payload.username else None,
            password_hash=self.auth.hash_password(payload.password),
            referred_by=payload.referral_code,
            referral_code=unique_referral_code,
            email_verified=False,
        )

        verification_token_raw = None
        verification_code_raw = None
        if user.email:
            verification_token_raw, verification_code_raw = await self.email_verification.issue(user)
            try:
                from app.services.email_service import send_verification_email
                await send_verification_email(user.email, verification_token_raw, verification_code_raw)
            except Exception:
                pass

        await self.users.create(user)

        access_token = create_access_token(user.id)
        refresh_token_str = create_refresh_token()
        await self.refresh_tokens.create(
            user.id, _hash_refresh_token(refresh_token_str), datetime.utcnow() + timedelta(days=30)
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)

    # --- login ---
    async def login(self, request: Request, form: OAuth2PasswordRequestForm) -> TokenResponse:
        identity = form.username.strip()
        user = await self.users.get_by_identity(identity)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if user.locked_until and user.locked_until > datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account locked. Try again later.")

        if not self.auth.verify_password(form.password, user.password_hash or ""):
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= settings.auth_max_failed_attempts:
                user.locked_until = datetime.utcnow() + timedelta(minutes=settings.auth_lockout_minutes)
                user.failed_login_attempts = 0
                await self.users.update(user)
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Too many failed attempts. Account locked for {settings.auth_lockout_minutes} minutes.",
                )
            await self.users.update(user)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = request.client.host if request.client else None
        user.last_login_user_agent = request.headers.get("user-agent")
        user.device_fingerprint = request.headers.get("x-device-fingerprint")
        await self.users.update(user)

        await self.audit_logs.create(
            user_id=user.id,
            action="login",
            ip_address=user.last_login_ip,
            user_agent=user.last_login_user_agent,
        )

        access_token = create_access_token(user.id)
        refresh_token_str = create_refresh_token()
        await self.refresh_tokens.create(
            user.id, _hash_refresh_token(refresh_token_str), datetime.utcnow() + timedelta(days=30)
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)

    # --- me ---
    async def me(self, current_user: User) -> UserMe:
        # Self-heal: ensure every user has a referral code (e.g. legacy rows).
        if not current_user.referral_code:
            await self._ensure_referral_code(current_user)
        return UserMe(
            id=current_user.id,
            email=current_user.email,
            phone=current_user.phone,
            username=current_user.username,
            tier=current_user.tier.value,
            role=current_user.role,
            status=current_user.status,
            created_at=current_user.created_at,
            email_verified=current_user.email_verified,
            avatar_url=current_user.avatar_url,
            transaction_pin_set=current_user.transaction_pin_hash is not None,
            referral_code=current_user.referral_code,
            referred_by=current_user.referred_by,
        )

    # --- refresh ---
    async def refresh(self, payload: RefreshRequest) -> TokenResponse:
        token_hash = _hash_refresh_token(payload.refresh_token)
        token_row = await self.refresh_tokens.get_valid_by_hash(token_hash)

        # Reuse detection: if a revoked/expired refresh token is presented,
        # revoke ALL refresh tokens for that user (token theft mitigation).
        if not token_row:
            # Try to find the token even if revoked/expired to detect reuse.
            from sqlalchemy import select
            from app.models.user import RefreshToken as RT
            result = await self.db.execute(
                select(RT).where(RT.token_hash == token_hash)
            )
            reused = result.scalar_one_or_none()
            if reused:
                await self.refresh_tokens.revoke_all_for_user(reused.user_id)
                await self.audit_logs.create(
                    user_id=reused.user_id,
                    action="refresh_token_reuse_detected",
                )
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        user = await self.users.get_by_id(token_row.user_id)
        if not user or user.status != "active":
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        await self.refresh_tokens.revoke(token_row)
        access_token = create_access_token(user.id)
        new_refresh_str = create_refresh_token()
        await self.refresh_tokens.create(
            user.id, _hash_refresh_token(new_refresh_str), datetime.utcnow() + timedelta(days=30)
        )
        return TokenResponse(access_token=access_token, refresh_token=new_refresh_str)

    # --- update profile ---
    async def update_profile(self, request: Request, current_user: User, payload) -> UserMe:
        if payload.username is not None:
            if payload.username == "":
                current_user.username = None
            else:
                existing = await self.users.get_by_username(payload.username)
                if existing and existing.id != current_user.id:
                    raise HTTPException(status_code=400, detail="Username already taken")
                current_user.username = payload.username.lower() if payload.username else None

        if payload.avatar_url is not None:
            current_user.avatar_url = payload.avatar_url

        await self.users.update(current_user)
        await self.audit_logs.create(
            user_id=current_user.id,
            action="profile_update",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            device_fingerprint=request.headers.get("x-device-fingerprint"),
        )
        return await self.me(current_user)

    # --- change password ---
    async def change_password(self, request: Request, current_user: User, payload) -> dict:
        if not current_user.password_hash:
            raise HTTPException(status_code=400, detail="Account has no password set")
        if not self.auth.verify_password(payload.current_password, current_user.password_hash):
            raise HTTPException(status_code=401, detail="Current password is incorrect.")

        current_user.password_hash = self.auth.hash_password(payload.new_password)
        await self.users.update(current_user)

        # Revoke current JWT.
        auth_header = request.headers.get("authorization", "")
        jti = None
        expires_at = None
        if auth_header.startswith("Bearer "):
            try:
                p = decode_access_token(auth_header[7:])
                jti = p.get("jti")
                exp = p.get("exp")
                if exp:
                    expires_at = datetime.utcfromtimestamp(exp)
            except Exception:
                pass
        if jti:
            await self.auth.revoke_jwt(jti, current_user.id, reason="password_change", expires_at=expires_at)

        await self.audit_logs.create(
            user_id=current_user.id,
            action="password_change",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            device_fingerprint=request.headers.get("x-device-fingerprint"),
        )
        return {"ok": True}

    # --- logout ---
    async def logout(self, request: Request, current_user: User) -> None:
        auth_header = request.headers.get("authorization", "")
        jti = None
        expires_at = None
        if auth_header.startswith("Bearer "):
            try:
                payload = decode_access_token(auth_header[7:])
                jti = payload.get("jti")
                exp = payload.get("exp")
                if exp:
                    expires_at = datetime.utcfromtimestamp(exp)
            except Exception:
                pass
        if jti:
            await self.auth.revoke_jwt(jti, current_user.id, reason="logout", expires_at=expires_at)
        await self.audit_logs.create(
            user_id=current_user.id,
            action="logout",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

    # --- email verification ---
    async def verify_email(self, payload: EmailVerificationRequest) -> dict:
        try:
            await self.email_verification.verify_by_token(payload.email, payload.token)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        user = await self.users.get_by_email(payload.email)
        if user:
            await self.welcome_bonus.grant(user)
            try:
                from app.services.referral_service import grant_referral_bonuses
                await grant_referral_bonuses(self.db, user)
            except Exception:
                pass
            await self.audit_logs.create(user_id=user.id, action="email_verify", extra_data="method=token")
        return {"ok": True, "message": "Email verified successfully"}

    async def verify_email_code(self, payload: EmailVerificationCodeRequest) -> dict:
        try:
            await self.email_verification.verify_by_code(payload.email, payload.code)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        user = await self.users.get_by_email(payload.email)
        if user:
            await self.welcome_bonus.grant(user)
            try:
                from app.services.referral_service import grant_referral_bonuses
                await grant_referral_bonuses(self.db, user)
            except Exception:
                pass
            await self.audit_logs.create(user_id=user.id, action="email_verify", extra_data="method=code")
        return {"ok": True, "message": "Email verified successfully"}

    async def resend_verification(self, current_user: User) -> dict:
        if not current_user.email:
            raise HTTPException(status_code=400, detail="No email address on file")
        if current_user.email_verified:
            raise HTTPException(status_code=400, detail="Email already verified")

        token_raw, code_raw = await self.email_verification.resend(current_user)
        await self.users.update(current_user)
        try:
            from app.services.email_service import send_verification_email
            await send_verification_email(current_user.email, token_raw, code_raw)
        except Exception:
            raise HTTPException(status_code=500, detail="Failed to send verification email")
        return {"ok": True, "message": "Verification email sent"}

    # --- forgot password ---
    async def forgot_password(self, payload: ForgotPasswordRequest) -> dict:
        try:
            return await self.password_reset.request_reset(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    async def verify_forgot_otp(self, payload: ForgotPasswordVerifyOtpRequest) -> dict:
        try:
            raw_token = await self.password_reset.verify_otp(payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        from app.schemas.auth import ForgotPasswordVerifyOtpResponse
        return ForgotPasswordVerifyOtpResponse(ok=True, reset_token=raw_token)

    async def reset_password(self, payload: ResetPasswordRequest) -> dict:
        try:
            await self.password_reset.reset(payload.token, payload.new_password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        # Audit log (best-effort; user_id unknown from token, skip for now)
        return {"ok": True, "message": "Password reset successfully"}

    # --- google oauth ---
    async def google_auth(self, payload: GoogleAuthRequest) -> TokenResponse:
        from app.services.google_auth_service import GoogleAuthService

        google = GoogleAuthService()
        try:
            info = google.verify_id_token(payload.id_token)
        except ValueError as exc:
            raise HTTPException(status_code=501, detail=str(exc))

        email = info["email"]
        created = False

        user = await self.users.get_by_email(email)
        if not user:
            base_username = email.split("@")[0].lower().replace(".", "_").replace("-", "_")
            base_username = "".join(c for c in base_username if c.isalnum() or c == "_")[:12]
            username = base_username or "user"
            counter = 1
            while True:
                candidate = f"{username}{counter}" if counter > 1 else username
                if len(candidate) > 12:
                    candidate = candidate[:12]
                dup = await self.users.get_by_username(candidate)
                if not dup:
                    username = candidate
                    break
                counter += 1

            unique_referral_code = self.auth.generate_referral_code()
            while await self.users.get_by_referral_code(unique_referral_code):
                unique_referral_code = self.auth.generate_referral_code()

            user = User(
                email=email,
                password_hash=None,
                username=username,
                referral_code=unique_referral_code,
                email_verified=True,
            )
            await self.users.create(user)
            created = True
        else:
            await self._ensure_referral_code(user)
            if not user.email_verified:
                user.email_verified = True
                await self.users.update(user)

        await self.audit_logs.create(user_id=user.id, action="google_login")

        # Welcome bonus (idempotent) on Google accounts (email is verified).
        try:
            await self.welcome_bonus.grant(user)
            from app.services.referral_service import grant_referral_bonuses
            await grant_referral_bonuses(self.db, user)
        except Exception:
            pass

        access_token = create_access_token(user.id)
        refresh_token_str = create_refresh_token()
        await self.refresh_tokens.create(
            user.id, _hash_refresh_token(refresh_token_str), datetime.utcnow() + timedelta(days=30)
        )
        return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)

    # --- avatar upload (Cloudflare R2) ---
    async def upload_avatar(self, current_user: User, data_url: str) -> dict:
        if not data_url or not data_url.startswith("data:image"):
            raise HTTPException(status_code=400, detail="Invalid image data")

        # Delete old avatar from R2 (best-effort).
        if current_user.avatar_url:
            try:
                self.r2.delete(current_user.avatar_url)
            except Exception:
                pass

        try:
            url = self.r2.upload_base64(data_url, folder="pagepay/avatars")
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {exc}")

        current_user.avatar_url = url
        await self.users.update(current_user)
        await self.audit_logs.create(user_id=current_user.id, action="avatar_upload")
        return {"ok": True, "avatar_url": url}

    # --- account deletion ---
    async def delete_account(self, request: Request, current_user: User, payload) -> None:
        # Password check (if user has a password set).
        if current_user.password_hash:
            if not self.auth.verify_password(payload.password, current_user.password_hash):
                raise HTTPException(status_code=400, detail="Incorrect password")

        # confirmation check
        if payload.confirmation != "DELETE":
            raise HTTPException(status_code=400, detail="Must type 'DELETE' exactly to confirm")

        await self.audit_logs.create(
            user_id=current_user.id,
            action="account_deletion_start",
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        # Delete avatar from R2 (best-effort).
        if current_user.avatar_url:
            try:
                self.r2.delete(current_user.avatar_url)
            except Exception:
                pass

        # Revoke current JWT.
        auth_header = request.headers.get("authorization", "")
        jti = None
        expires_at = None
        if auth_header.startswith("Bearer "):
            try:
                payload = decode_access_token(auth_header[7:])
                jti = payload.get("jti")
                exp = payload.get("exp")
                if exp:
                    expires_at = datetime.utcfromtimestamp(exp)
            except Exception:
                pass
        if jti:
            await self.auth.revoke_jwt(jti, current_user.id, reason="account_deletion", expires_at=expires_at)

        # Delete all refresh tokens.
        await self.refresh_tokens.revoke_all_for_user(current_user.id)

        # Delete user (cascades to related tables via FK constraints).
        await self.users.delete(current_user)

    # --- transaction PIN ---
    async def set_transaction_pin(self, current_user: User, pin: str, current_password: str | None) -> dict:
        if current_user.transaction_pin_hash:
            if not current_password or not current_user.password_hash:
                raise HTTPException(status_code=400, detail="Current password required to change PIN")
            if not self.auth.verify_password(current_password, current_user.password_hash):
                raise HTTPException(status_code=400, detail="Incorrect password")
        current_user.transaction_pin_hash = self.auth.hash_password(pin)
        await self.users.update(current_user)
        await self.audit_logs.create(user_id=current_user.id, action="pin_set")
        return {"ok": True, "message": "Transaction PIN set successfully"}

    async def verify_transaction_pin(self, current_user: User, pin: str) -> dict:
        if not current_user.transaction_pin_hash:
            raise HTTPException(status_code=400, detail="No transaction PIN set")
        if not self.auth.verify_password(pin, current_user.transaction_pin_hash):
            raise HTTPException(status_code=400, detail="Incorrect PIN")
        return {"ok": True, "message": "PIN verified"}

    # --- device fingerprint tracking ---
    # (handled in login/refresh via header; stored on user)

    # --- audit logs ---
    async def get_audit_logs(self, current_user: User, limit: int = 50, offset: int = 0) -> dict:
        limit = min(limit, 100)
        logs = await self.audit_logs.list_for_user(current_user.id, limit=limit, offset=offset)
        from app.schemas.auth import UserAuditLog
        return {
            "logs": [UserAuditLog.model_validate(l) for l in logs],
            "total": len(logs),
        }
