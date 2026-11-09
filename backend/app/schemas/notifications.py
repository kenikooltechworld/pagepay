"""Pydantic schemas for notification endpoints."""

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class NotificationPreferences(BaseModel):
    """User notification preferences."""

    push_enabled: bool = True
    study_reminders: bool = True
    task_alerts: bool = True
    referral_bonuses: bool = True
    wallet_updates: bool = True
    ad_rewards: bool = True
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


class NotificationPreferencesResponse(NotificationPreferences):
    """Response with timestamps."""

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FCMTokenRequest(BaseModel):
    """Register FCM token."""

    token: str = Field(..., min_length=10, max_length=512)
    platform: str = Field(..., pattern="^(android|ios|web)$")
    device_id: Optional[str] = Field(None, max_length=255)


class FCMTokenResponse(BaseModel):
    """FCM token response."""

    id: int
    token: str
    platform: str
    device_id: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationResponse(BaseModel):
    """Notification detail."""

    id: int
    user_id: int
    title: str
    body: str
    category: Optional[str] = None
    data: Optional[dict] = None
    read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationsListResponse(BaseModel):
    """List of notifications with unread count."""

    notifications: list[NotificationResponse]
    unread_count: int
