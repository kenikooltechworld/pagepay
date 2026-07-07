import hashlib
import logging
import secrets
import string
import bcrypt
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from jose import JWTError, jwt
from app.database import get_db
from app.models import User, PasswordResetToken, RefreshToken
from app.schemas import UserRegister, TokenResponse, UserMe, ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest, LegalPageResponse, EmailVerificationRequest
from app.services.auth import hash_password, verify_password, create_access_token, create_refresh_token, get_current_user, revoke_jwt
from app.services.email import send_verification_email, send_password_reset_email
from app.services.user_audit import log_user_action, get_user_audit_logs
from app.config import settings
from app.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("uvicorn.error")

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _get_jti_from_request(request: Request) -> str | None:
    """Extract jti from the Authorization header token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload.get("jti")
    except JWTError:
        return None


def _generate_referral_code() -> str:
    """Generate a unique 6-char alphanumeric referral code."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(6))


def _hash_token(token: str) -> str:
    """Hash a reset token for storage using bcrypt."""
    return bcrypt.hashpw(token.encode(), bcrypt.gensalt(rounds=10)).decode()


def _hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: UserRegister, request: Request, db: AsyncSession = Depends(get_db)):
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=400, detail="Email or phone required")

    query = select(User).where(
        (User.email == payload.email) if payload.email else (User.phone == payload.phone)
    )
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User already exists")

    # Validate referral code if provided
    referred_by_code = payload.referral_code
    if referred_by_code:
        referrer = await db.execute(
            select(User).where(User.referral_code == referred_by_code)
        )
        if not referrer.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Invalid referral code. Check the code and try again."
            )

    # Generate unique referral code BEFORE creating user to avoid flush/autoflush deadlock
    unique_referral_code = _generate_referral_code()
    while True:
        exists = await db.execute(select(User).where(User.referral_code == unique_referral_code))
        if not exists.scalar_one_or_none():
            break
        unique_referral_code = _generate_referral_code()

    user = User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        referred_by=referred_by_code,
        referral_code=unique_referral_code,
        email_verified=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Generate email verification token
    verification_token = secrets.token_urlsafe(32)
    user.email_verification_token = bcrypt.hashpw(verification_token.encode(), bcrypt.gensalt(rounds=10)).decode()
    user.email_verification_expires_at = datetime.utcnow() + timedelta(hours=24)
    await db.commit()

    # Send verification email (non-blocking)
    try:
        if user.email:
            await send_verification_email(user.email, verification_token)
    except Exception as exc:
        logger.error("Failed to send verification email to %s: %s", user.email, exc)

    # Issue tokens
    access_token = create_access_token(user.id)
    refresh_token_str = create_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=_hash_refresh_token(refresh_token_str),
        expires_at=datetime.utcnow() + timedelta(days=30),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint"),
    )
    db.add(refresh_token)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)


@router.get("/me", response_model=UserMe)
async def me(current_user: User = Depends(get_current_user)):
    return UserMe(
        id=current_user.id,
        email=current_user.email,
        phone=current_user.phone,
        points_balance=current_user.points_balance,
        tier=current_user.tier.value,
        created_at=current_user.created_at,
        is_worker=current_user.is_worker,
        is_sponsor=current_user.is_sponsor,
        email_verified=current_user.email_verified,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit("5/15minutes")
async def login(
    request: Request,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    query = select(User).where(
        (User.email == form.username) | (User.phone == form.username)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account lockout
    if user.locked_until and user.locked_until > datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account locked. Try again in {int((user.locked_until - datetime.utcnow()).total_seconds() / 60)} minutes.",
        )

    if not verify_password(form.password, user.password_hash or ""):
        user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
        if user.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = datetime.utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_login_attempts = 0
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.",
            )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed attempts on successful login
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.client.host if request.client else None
    user.last_login_user_agent = request.headers.get("user-agent")
    await db.commit()

    # Log successful login
    await log_user_action(
        db,
        user.id,
        "login",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint"),
    )

    access_token = create_access_token(user.id)
    refresh_token_str = create_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=_hash_refresh_token(refresh_token_str),
        expires_at=datetime.utcnow() + timedelta(days=30),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint"),
    )
    db.add(refresh_token)
    await db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)


@router.post("/change-password")
async def change_password(
    request: Request,
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()
    
    # Revoke current JWT (password change invalidates all existing sessions)
    jti = _get_jti_from_request(request)
    if jti:
        await revoke_jwt(db, jti, current_user.id, reason="password_change")
    
    # Log password change
    await log_user_action(
        db,
        current_user.id,
        "password_change",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint"),
    )
    
    logger.info("User %s changed their password.", current_user.id)
    return {"ok": True}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    logger.info("User %s signed out.", current_user.id)
    
    # Revoke current JWT
    jti = _get_jti_from_request(request)
    if jti:
        await revoke_jwt(db, jti, current_user.id, reason="logout")
    
    # Revoke all refresh tokens for this user
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == current_user.id, RefreshToken.revoked == False)  # noqa: E712
    )
    for token in result.scalars().all():
        token.revoked = True
    await db.commit()
    
    # Log logout
    await log_user_action(
        db,
        current_user.id,
        "logout",
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint"),
    )
    
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    body = await request.json()
    refresh_token_str = body.get("refresh_token")
    if not refresh_token_str:
        raise HTTPException(status_code=400, detail="refresh_token required")

    token_hash = _hash_refresh_token(refresh_token_str)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.expires_at > datetime.utcnow(),
            RefreshToken.revoked == False,  # noqa: E712
        )
    )
    token = result.scalar_one_or_none()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = await db.get(User, token.user_id)
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token(user.id)
    return TokenResponse(access_token=access_token)


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=400, detail="Email or phone required")

    query = select(User).where(
        (User.email == payload.email) if payload.email else (User.phone == payload.phone)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        return {"ok": True, "message": "If that account exists, a reset link has been sent."}

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    await db.commit()

    # Send password reset email (non-blocking)
    try:
        if user.email:
            await send_password_reset_email(user.email, raw_token)
    except Exception as exc:
        logger.error("Failed to send password reset email to %s: %s", user.email, exc)

    logger.info("Password reset requested for user_id=%s", user.id)
    return {
        "ok": True,
        "message": "If that account exists, a reset link has been sent.",
    }


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    token_hash = _hash_token(payload.token)

    result = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > datetime.utcnow(),
        )
    )
    reset_token = result.scalar_one_or_none()
    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    user = await db.get(User, reset_token.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password_hash = hash_password(payload.new_password)
    reset_token.used_at = datetime.utcnow()
    await db.commit()

    # Log password reset
    await log_user_action(
        db,
        user.id,
        "password_reset",
        metadata={"method": "token"},
    )

    logger.info("Password reset completed for user_id=%s", user.id)
    return {"ok": True}


@router.post("/verify-email")
async def verify_email(payload: EmailVerificationRequest, db: AsyncSession = Depends(get_db)):
    """Verify email address using the token sent via email."""
    query = select(User).where(User.email == payload.email, User.email_verified == False)  # noqa: E712
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification token or email already verified")

    if not user.email_verification_token:
        raise HTTPException(status_code=400, detail="No pending verification for this email")

    if user.email_verification_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification token expired. Request a new one.")

    if not bcrypt.checkpw(payload.token.encode(), user.email_verification_token.encode()):
        raise HTTPException(status_code=400, detail="Invalid verification token")

    user.email_verified = True
    user.email_verification_token = None
    user.email_verification_expires_at = None
    await db.commit()

    # Log email verification
    await log_user_action(
        db,
        user.id,
        "email_verify",
        metadata={"method": "token"},
    )

    logger.info("Email verified for user_id=%s", user.id)
    return {"ok": True, "message": "Email verified successfully"}


@router.post("/resend-verification")
async def resend_verification(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Resend verification email to the current user."""
    if not current_user.email:
        raise HTTPException(status_code=400, detail="No email address on file")

    if current_user.email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    verification_token = secrets.token_urlsafe(32)
    current_user.email_verification_token = bcrypt.hashpw(verification_token.encode(), bcrypt.gensalt(rounds=10)).decode()
    current_user.email_verification_expires_at = datetime.utcnow() + timedelta(hours=24)
    await db.commit()

    try:
        await send_verification_email(current_user.email, verification_token)
    except Exception as exc:
        logger.error("Failed to resend verification email to %s: %s", current_user.email, exc)
        raise HTTPException(status_code=500, detail="Failed to send verification email")

    return {"ok": True, "message": "Verification email sent"}


@router.post("/google", response_model=TokenResponse)
async def google_auth(
    request: Request,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with Google ID token.

    Frontend sends: { "id_token": "..." }
    Backend verifies with Google and creates/logs in user.
    """
    id_token = payload.get("id_token")
    if not id_token:
        raise HTTPException(status_code=400, detail="id_token required")

    if not settings.google_client_id:
        raise HTTPException(status_code=501, detail="Google OAuth2 is not configured")

    # Verify ID token with Google
    try:
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        # Verify the token
        idinfo = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            settings.google_client_id,
        )
    except Exception as exc:
        logger.error("Google token verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = idinfo.get("email")
    if not email or not idinfo.get("email_verified"):
        raise HTTPException(status_code=400, detail="Google account email not verified")

    # Find or create user
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        # Create new user from Google
        user = User(
            email=email,
            password_hash=None,  # OAuth users don't have password
            email_verified=True,
            is_worker=True,
            is_sponsor=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        # Update email_verified if not already
        if not user.email_verified:
            user.email_verified = True
            await db.commit()

    # Issue tokens
    access_token = create_access_token(user.id)
    refresh_token_str = create_refresh_token()
    refresh_token = RefreshToken(
        user_id=user.id,
        token_hash=_hash_refresh_token(refresh_token_str),
        expires_at=datetime.utcnow() + timedelta(days=30),
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        device_fingerprint=request.headers.get("x-device-fingerprint"),
    )
    db.add(refresh_token)
    await db.commit()

    logger.info("Google OAuth login for user_id=%s email=%s", user.id, email)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token_str)


@router.get("/audit-logs")
async def get_audit_logs(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
):
    """Get current user's audit logs."""
    logs = await get_user_audit_logs(db, current_user.id, limit=limit, offset=offset)
    return {
        "logs": [
            {
                "id": log.id,
                "action": log.action,
                "ip_address": log.ip_address,
                "user_agent": log.user_agent,
                "device_fingerprint": log.device_fingerprint,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
    }
