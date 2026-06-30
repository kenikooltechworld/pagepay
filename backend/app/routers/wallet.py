import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import ReadingSession, ContentCatalog
from app.routers.auth import get_current_user
from app.models import User

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/wallet", tags=["wallet"])


class Transaction(BaseModel):
    id: int
    type: str  # "earn" | "pending"
    points: int
    description: str
    date: datetime


@router.get("/transactions", response_model=list[Transaction])
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """User's point-earning history. Each row is a reading session — title,
    points earned, and the date the session ended. Sessions with zero points
    (e.g. user backgrounded and didn't scroll) are surfaced as `pending` so the
    user understands why their balance didn't move.

    The shape matches what the frontend previously hardcoded as mock data so
    the wallet screen can render the same rows without code duplication.
    """
    stmt = (
        select(ReadingSession, ContentCatalog.title)
        .join(ContentCatalog, ContentCatalog.id == ReadingSession.content_id)
        .where(ReadingSession.user_id == current_user.id)
        .order_by(ReadingSession.start_time.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    out: list[Transaction] = []
    for session, title in rows:
        if session.end_time is None:
            # Session in flight — never resolved, no points awarded yet.
            out.append(
                Transaction(
                    id=session.id,
                    type="pending",
                    points=0,
                    description=f"Reading \"{title}\"",
                    date=session.start_time,
                )
            )
            continue

        # Reward-gate accounting: a session can end in three states.
        #   1. claimed   → points_earned > 0, claimed_at set   → "earn"
        #   2. claimable → pending_points > 0, claimed_at null → "pending"
        #                   (user stopped reading but didn't watch the post-read ad)
        #   3. nothing   → 0 points, 0 pending, not verified   → "pending" with 0 pts
        if session.claimed_at is not None and session.points_earned > 0:
            out.append(
                Transaction(
                    id=session.id,
                    type="earn",
                    points=session.points_earned,
                    description=f'Earned on "{title}"',
                    date=session.claimed_at,
                )
            )
        elif (session.pending_points or 0) > 0:
            out.append(
                Transaction(
                    id=session.id,
                    type="pending",
                    points=0,
                    description=f'Watch an ad to claim "{title}"',
                    date=session.end_time,
                )
            )
        else:
            out.append(
                Transaction(
                    id=session.id,
                    type="pending",
                    points=0,
                    description=f'Read "{title}"',
                    date=session.end_time,
                )
            )
    return out
