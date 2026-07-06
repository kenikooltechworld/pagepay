"""
Notification preferences and FCM token management.
Phase 3 feature: Push notifications with Firebase Cloud Messaging.
"""
from datetime import datetime, time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ── Schemas ──────────────────────────────────────────────────────────


class NotificationPreferences(BaseModel):
    """User notification preferences."""
    push_enabled: bool = True
    study_reminders: bool = True
    task_alerts: bool = True
    referral_bonuses: bool = True
    wallet_updates: bool = True
    ad_rewards: bool = True
    quiet_hours_start: Optional[str] = None  # Format: "HH:MM"
    quiet_hours_end: Optional[str] = None    # Format: "HH:MM"


class NotificationPreferencesResponse(NotificationPreferences):
    """Response with creation/update timestamps."""
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FCMTokenRequest(BaseModel):
    """Register FCM token for push notifications."""
    token: str = Field(..., min_length=10, max_length=255)
    platform: str = Field(..., pattern="^(android|ios|web)$")
    device_id: Optional[str] = Field(None, max_length=255)


class FCMTokenResponse(BaseModel):
    """FCM token registration response."""
    id: int
    token: str
    platform: str
    device_id: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Endpoints ────────────────────────────────────────────────────────


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_notification_preferences(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get user's notification preferences.
    Creates default preferences if none exist.
    """
    user_id = current_user["id"]

    # Check if preferences exist
    query = select(
        db.bind.execute.__self__.tables["user_notification_preferences"]
    ).where(
        db.bind.execute.__self__.tables["user_notification_preferences"].c.user_id == user_id
    )
    result = await db.execute(query)
    prefs = result.fetchone()

    if not prefs:
        # Create default preferences
        insert_stmt = db.bind.execute.__self__.tables["user_notification_preferences"].insert().values(
            user_id=user_id,
            push_enabled=True,
            study_reminders=True,
            task_alerts=True,
            referral_bonuses=True,
            wallet_updates=True,
            ad_rewards=True,
        )
        await db.execute(insert_stmt)
        await db.commit()

        # Fetch the created preferences
        result = await db.execute(query)
        prefs = result.fetchone()

    # Convert time objects to strings
    prefs_dict = dict(prefs._mapping)
    if prefs_dict.get("quiet_hours_start"):
        prefs_dict["quiet_hours_start"] = prefs_dict["quiet_hours_start"].strftime("%H:%M")
    if prefs_dict.get("quiet_hours_end"):
        prefs_dict["quiet_hours_end"] = prefs_dict["quiet_hours_end"].strftime("%H:%M")

    return prefs_dict


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_notification_preferences(
    preferences: NotificationPreferences,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update user's notification preferences.
    """
    user_id = current_user["id"]

    # Parse time strings if provided
    quiet_start = None
    quiet_end = None
    if preferences.quiet_hours_start:
        try:
            h, m = map(int, preferences.quiet_hours_start.split(":"))
            quiet_start = time(h, m)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="quiet_hours_start must be in HH:MM format"
            )
    if preferences.quiet_hours_end:
        try:
            h, m = map(int, preferences.quiet_hours_end.split(":"))
            quiet_end = time(h, m)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="quiet_hours_end must be in HH:MM format"
            )

    # Upsert preferences
    from sqlalchemy.dialects.mysql import insert

    table = db.bind.execute.__self__.tables["user_notification_preferences"]
    stmt = insert(table).values(
        user_id=user_id,
        push_enabled=preferences.push_enabled,
        study_reminders=preferences.study_reminders,
        task_alerts=preferences.task_alerts,
        referral_bonuses=preferences.referral_bonuses,
        wallet_updates=preferences.wallet_updates,
        ad_rewards=preferences.ad_rewards,
        quiet_hours_start=quiet_start,
        quiet_hours_end=quiet_end,
        updated_at=datetime.utcnow(),
    )
    stmt = stmt.on_duplicate_key_update(
        push_enabled=preferences.push_enabled,
        study_reminders=preferences.study_reminders,
        task_alerts=preferences.task_alerts,
        referral_bonuses=preferences.referral_bonuses,
        wallet_updates=preferences.wallet_updates,
        ad_rewards=preferences.ad_rewards,
        quiet_hours_start=quiet_start,
        quiet_hours_end=quiet_end,
        updated_at=datetime.utcnow(),
    )
    await db.execute(stmt)
    await db.commit()

    # Return updated preferences
    return await get_notification_preferences(current_user, db)


@router.post("/fcm-token", response_model=FCMTokenResponse, status_code=status.HTTP_201_CREATED)
async def register_fcm_token(
    token_req: FCMTokenRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Register FCM token for push notifications.
    If token already exists, mark it as active and update timestamp.
    """
    user_id = current_user["id"]

    # Check if token already exists
    table = db.bind.execute.__self__.tables["fcm_tokens"]
    query = select(table).where(table.c.token == token_req.token)
    result = await db.execute(query)
    existing = result.fetchone()

    if existing:
        # Reactivate existing token
        update_stmt = (
            table.update()
            .where(table.c.token == token_req.token)
            .values(
                is_active=True,
                user_id=user_id,  # Update user_id in case device switched accounts
                platform=token_req.platform,
                device_id=token_req.device_id,
                updated_at=datetime.utcnow(),
            )
        )
        await db.execute(update_stmt)
        await db.commit()

        # Fetch updated token
        result = await db.execute(query)
        token_row = result.fetchone()
        return dict(token_row._mapping)

    # Insert new token
    insert_stmt = table.insert().values(
        user_id=user_id,
        token=token_req.token,
        platform=token_req.platform,
        device_id=token_req.device_id,
        is_active=True,
    )
    result = await db.execute(insert_stmt)
    await db.commit()

    # Fetch the created token
    query = select(table).where(table.c.id == result.lastrowid)
    result = await db.execute(query)
    token_row = result.fetchone()

    return dict(token_row._mapping)


@router.delete("/fcm-token/{token}", status_code=status.HTTP_204_NO_CONTENT)
async def deregister_fcm_token(
    token: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Deregister FCM token (mark as inactive).
    Called when user logs out or uninstalls app.
    """
    user_id = current_user["id"]

    table = db.bind.execute.__self__.tables["fcm_tokens"]
    stmt = (
        table.update()
        .where(table.c.token == token)
        .where(table.c.user_id == user_id)
        .values(is_active=False, updated_at=datetime.utcnow())
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Token not found or already inactive"
        )

    return None


@router.get("/fcm-tokens", response_model=list[FCMTokenResponse])
async def list_fcm_tokens(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    List all active FCM tokens for current user.
    Useful for debugging or device management.
    """
    user_id = current_user["id"]

    table = db.bind.execute.__self__.tables["fcm_tokens"]
    query = select(table).where(
        table.c.user_id == user_id,
        table.c.is_active == True
    ).order_by(table.c.created_at.desc())

    result = await db.execute(query)
    tokens = result.fetchall()

    return [dict(row._mapping) for row in tokens]
