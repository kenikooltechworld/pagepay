import logging
import secrets
import string
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from app.database import get_db
from app.models import User, PasswordResetToken
from app.schemas import UserRegister, TokenResponse, UserMe, ChangePasswordRequest, ForgotPasswordRequest, ResetPasswordRequest, LegalPageResponse
from app.services.auth import hash_password, verify_password, create_access_token, get_current_user
from app.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("uvicorn.error")


def _generate_referral_code() -> str:
    """Generate a unique 6-char alphanumeric referral code."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(6))


def _hash_token(token: str) -> str:
    """Hash a reset token for storage."""
    import hashlib
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/register", response_model=TokenResponse, status_code=201)
async def register(payload: UserRegister, db: AsyncSession = Depends(get_db)):
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
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


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
            detail="No account found with that email or phone. Create an account instead.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form.password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password. Try again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(user.id)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserMe)
async def me(current_user: User = Depends(get_current_user)):
    return UserMe(
        id=current_user.id,
        email=current_user.email,
        phone=current_user.phone,
        points_balance=current_user.points_balance,
        tier=current_user.tier.value,
        created_at=current_user.created_at,
        is_worker=getattr(current_user, 'is_worker', True),  # default True for old users
        is_sponsor=getattr(current_user, 'is_sponsor', False),  # default False for old users
    )


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the user's password after re-verifying the current one.

    Re-using the current password proves the caller owns the account —
    without it, anyone with a leaked session token could lock the
    legitimate user out. We hash the new password via the same bcrypt
    path registration uses (truncates at 72 bytes per the bcrypt
    spec) so login continues to work.

    Idempotency: if the new and current passwords match, we still
    update the row (re-hash with a fresh salt). This isn't optimal
    but the cost is one bcrypt round and the UX is friendlier than
    silently no-op'ing.
    """
    if not verify_password(payload.current_password, current_user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )
    current_user.password_hash = hash_password(payload.new_password)
    await db.commit()
    logger.info("User %s changed their password.", current_user.id)
    return {"ok": True}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: User = Depends(get_current_user)):
    """Sign the user out.

    Stateless JWTs can't actually be invalidated server-side without
    a revocation list, so this endpoint is a no-op 204 in v1. We
    log the event so we can audit it, and the route exists so the
    client can call it cleanly. Phase 4 (Payments) will introduce a
    revoked-tokens table and this endpoint will start adding the
    current token's `jti` (or hash) to it.
    """
    logger.info("User %s signed out.", current_user.id)
    # Returning an explicit empty Response guarantees no body — fastapi
    # otherwise sometimes serializes `None` to "null" depending on the
    # response_class. The 204 contract forbids any body.
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset token.

    In production this would send an email/SMS. For now, return the
    raw token so the client can proceed straight to reset-password.
    """
    if not payload.email and not payload.phone:
        raise HTTPException(status_code=400, detail="Email or phone required")

    query = select(User).where(
        (User.email == payload.email) if payload.email else (User.phone == payload.phone)
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        # Don't reveal whether the account exists
        return {"ok": True, "message": "If that account exists, a reset link has been sent."}

    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.utcnow().replace(hour=23, minute=59, second=59)

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    await db.commit()

    logger.info("Password reset requested for user_id=%s", user.id)

    # In production: send email/SMS with the token. For dev, return it.
    return {
        "ok": True,
        "message": "If that account exists, a reset link has been sent.",
        "dev_token": raw_token,
    }


@router.post("/reset-password")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a one-time token."""
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

    logger.info("Password reset completed for user_id=%s", user.id)
    return {"ok": True}
