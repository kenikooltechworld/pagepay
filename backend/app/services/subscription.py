"""Subscription enforcement helpers.

Used by routers to check if a user's premium tier is valid.
"""

from datetime import datetime, timezone
from fastapi import HTTPException
from app.models import User, UserTier


def require_premium(user: User) -> None:
    """Raise 403 if user is not premium or subscription expired.
    
    Call this in route handlers that require active premium.
    """
    if user.tier == UserTier.FREE:
        raise HTTPException(
            status_code=403,
            detail="Premium subscription required",
        )
    
    if user.subscription_expires_at:
        now = datetime.now(timezone.utc)
        if now > user.subscription_expires_at:
            raise HTTPException(
                status_code=403,
                detail="Subscription expired. Please renew.",
            )


def is_premium(user: User) -> bool:
    """Check if user has active premium subscription."""
    if user.tier == UserTier.FREE:
        return False
    
    if user.subscription_expires_at:
        now = datetime.now(timezone.utc)
        if now > user.subscription_expires_at:
            return False
    
    return True


def get_points_multiplier(user: User) -> float:
    """Return points earned multiplier for the user's tier.
    
    Free: 1.0x
    Premium Monthly: 1.5x
    Premium Yearly: 2.0x
    """
    if not is_premium(user):
        return 1.0
    
    if user.tier == UserTier.PREMIUM_YEARLY:
        return 2.0
    
    return 1.5
