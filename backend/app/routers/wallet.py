import logging
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.database import get_db
from app.models import ReadingSession, ContentCatalog, AdEvent
from app.routers.auth import get_current_user
from app.models import User

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/wallet", tags=["wallet"])


class Transaction(BaseModel):
    id: int
    type: str  # "earn" | "pending" | "ad_reward"
    points: int
    description: str
    date: datetime


@router.get("/transactions", response_model=list[Transaction])
async def list_transactions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 50,
):
    """Unified point-earning history combining reading sessions and ad rewards."""
    # Reading sessions
    session_stmt = (
        select(ReadingSession, ContentCatalog.title)
        .join(ContentCatalog, ContentCatalog.id == ReadingSession.content_id)
        .where(ReadingSession.user_id == current_user.id)
        .order_by(ReadingSession.start_time.desc())
        .limit(limit)
    )
    sessions = (await db.execute(session_stmt)).all()

    # Ad reward events
    ad_stmt = (
        select(AdEvent)
        .where(AdEvent.user_id == current_user.id)
        .where(AdEvent.credit_status == "credited")
        .where(AdEvent.user_points_credited > 0)
        .order_by(AdEvent.created_at.desc())
        .limit(limit)
    )
    ad_events = (await db.execute(ad_stmt)).scalars().all()

    out: list[Transaction] = []
    for session, title in sessions:
        sid = session.id
        if session.claimed_at is not None and session.points_earned > 0:
            out.append(
                Transaction(
                    id=sid, type="earn", points=session.points_earned,
                    description=f'Earned on "{title}"', date=session.claimed_at,
                )
            )
        elif (session.pending_points or 0) > 0:
            out.append(
                Transaction(
                    id=sid, type="pending", points=0,
                    description=f'Watch an ad to claim "{title}"',
                    date=session.end_time or session.start_time,
                )
            )
        else:
            desc = "Reading..." if session.end_time is None else f'Read "{title}"'
            out.append(
                Transaction(
                    id=sid, type="pending", points=0,
                    description=desc,
                    date=session.end_time or session.start_time,
                )
            )

    for event in ad_events:
        out.append(
            Transaction(
                id=event.id, type="earn", points=event.user_points_credited,
                description="Ad reward", date=event.created_at,
            )
        )

    # Sort newest first, limit
    out.sort(key=lambda t: t.date, reverse=True)
    return out[:limit]
