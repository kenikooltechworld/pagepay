import logging
import secrets
import string
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models import User
from app.schemas import UserRegister, TokenResponse, UserMe, ChangePasswordRequest
from app.services.auth import hash_password, verify_password, create_access_token, get_current_user
from app.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("uvicorn.error")


def _generate_referral_code() -> str:
    """Generate a unique 6-char alphanumeric referral code."""
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(6))


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

    referred_by_code = payload.referral_code

    user = User(
        email=payload.email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        referred_by=referred_by_code,
    )
    db.add(user)
    await db.flush()

    if not user.referral_code:
        user.referral_code = _generate_referral_code()
        while True:
            exists = await db.execute(select(User).where(User.referral_code == user.referral_code))
            if not exists.scalar_one_or_none():
                break
            user.referral_code = _generate_referral_code()

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
    if not user or not verify_password(form.password, user.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email/phone or password",
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
