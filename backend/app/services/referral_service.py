"""Referral rewards (SP) — idempotent, credited via the unified wallet ledger.

Policy (current): credit BOTH users with 100 SP when the referee verifies their email.
Idempotency: `point_credits` UNIQUE(user_id, source) + wallet ledger idempotency keys.
"""

import logging

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import PointCredit, User
from app.models.wallet import WalletLedger
from app.repositories.user_repository import UserRepository

logger = logging.getLogger("uvicorn.error")

REFERRER_SOURCE = "referral_referrer"
REFEREE_SOURCE = "referral_referee"


async def _grant_sp(db: AsyncSession, user: User, amount: int, source: str, meta: dict) -> bool:
    if amount <= 0:
        return False
    stmt = (
        pg_insert(PointCredit)
        .values(user_id=user.id, source=source, points=amount, metadata_json=meta)
        .on_conflict_do_nothing(index_elements=["user_id", "source"])
    )
    res = await db.execute(stmt)
    await db.commit()
    if (res.rowcount or 0) == 0:
        return False
    # update balance
    user.service_credit_balance = int(user.service_credit_balance or 0) + amount
    user.points_balance = int(user.points_balance or 0) + amount
    await db.commit()
    await db.refresh(user)
    # unified ledger (idempotent)
    try:
        db.add(WalletLedger(
            user_id=user.id, currency="SP", direction="credit", amount=amount,
            balance_after=int(user.service_credit_balance or 0), source=source,
            reference_type="referral", reference_id=source,
            idempotency_key=f"{source}:{user.id}", metadata_json=meta,
        ))
        await db.commit()
    except Exception:
        await db.rollback()
    return True


async def grant_referral_bonuses(db: AsyncSession, referee: User) -> dict:
    """Credit referrer + referee (100 SP each) once, after referee verifies email."""
    out = {"referrer": False, "referee": False}
    if not referee.email_verified or not referee.referred_by:
        return out
    users = UserRepository(db)
    referrer = await users.get_by_referral_code(referee.referred_by)
    if not referrer or referrer.id == referee.id:
        return out
    try:
        out["referee"] = await _grant_sp(
            db, referee, settings.referral_referee_bonus_sp, REFEREE_SOURCE,
            {"referrer_user_id": referrer.id, "referral_code": referee.referred_by},
        )
    except Exception as exc:
        logger.warning("referee bonus failed user=%s: %s", referee.id, exc)
    try:
        out["referrer"] = await _grant_sp(
            db, referrer, settings.referral_referrer_bonus_sp, REFERRER_SOURCE,
            {"referee_user_id": referee.id, "referral_code": referee.referred_by},
        )
    except Exception as exc:
        logger.warning("referrer bonus failed user=%s: %s", referrer.id, exc)
    return out
