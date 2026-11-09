"""Notification HTTP routes (thin layer)."""

import json

from fastapi import APIRouter, Depends, HTTPException

from app.controllers.notification_controller import NotificationController
from app.core.database import get_db
from app.models.user import User
from app.schemas.notifications import (
    FCMTokenRequest,
    FCMTokenResponse,
    NotificationPreferences,
    NotificationPreferencesResponse,
    NotificationResponse,
    NotificationsListResponse,
)
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_controller(db=Depends(get_db)) -> NotificationController:
    return NotificationController(db)


@router.get("/preferences", response_model=NotificationPreferencesResponse)
async def get_preferences(current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    prefs = await controller.get_preferences(current_user)
    return NotificationPreferencesResponse(
        push_enabled=prefs.push_enabled,
        study_reminders=prefs.study_reminders,
        task_alerts=prefs.task_alerts,
        referral_bonuses=prefs.referral_bonuses,
        wallet_updates=prefs.wallet_updates,
        ad_rewards=prefs.ad_rewards,
        quiet_hours_start=prefs.quiet_hours_start.strftime("%H:%M") if prefs.quiet_hours_start else None,
        quiet_hours_end=prefs.quiet_hours_end.strftime("%H:%M") if prefs.quiet_hours_end else None,
        created_at=prefs.created_at,
        updated_at=prefs.updated_at,
    )


@router.put("/preferences", response_model=NotificationPreferencesResponse)
async def update_preferences(payload: NotificationPreferences, current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    prefs = await controller.update_preferences(current_user, payload.model_dump())
    return NotificationPreferencesResponse(
        push_enabled=prefs.push_enabled,
        study_reminders=prefs.study_reminders,
        task_alerts=prefs.task_alerts,
        referral_bonuses=prefs.referral_bonuses,
        wallet_updates=prefs.wallet_updates,
        ad_rewards=prefs.ad_rewards,
        quiet_hours_start=prefs.quiet_hours_start.strftime("%H:%M") if prefs.quiet_hours_start else None,
        quiet_hours_end=prefs.quiet_hours_end.strftime("%H:%M") if prefs.quiet_hours_end else None,
        created_at=prefs.created_at,
        updated_at=prefs.updated_at,
    )


@router.post("/fcm-token", response_model=FCMTokenResponse, status_code=201)
async def register_fcm_token(payload: FCMTokenRequest, current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    return await controller.register_fcm_token(current_user, payload.token, payload.platform, payload.device_id)


@router.delete("/fcm-token/{token}", status_code=204)
async def deregister_fcm_token(token: str, current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    ok = await controller.deregister_fcm_token(current_user, token)
    if not ok:
        raise HTTPException(status_code=404, detail="Token not found or already inactive")
    return None


@router.get("/fcm-tokens", response_model=list[FCMTokenResponse])
async def list_fcm_tokens(current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    return await controller.list_fcm_tokens(current_user)


@router.get("", response_model=NotificationsListResponse)
async def list_notifications(limit: int = 50, offset: int = 0, current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    notifs, unread = await controller.list_notifications(current_user, limit=limit, offset=offset)
    return NotificationsListResponse(
        notifications=[
            NotificationResponse(
                id=n.id,
                user_id=n.user_id,
                title=n.title,
                body=n.body,
                category=n.category,
                data=__import__("json").loads(n.data) if n.data else None,
                read=n.read,
                created_at=n.created_at,
            )
            for n in notifs
        ],
        unread_count=unread,
    )


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(notification_id: int, current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    notif = await controller.get_notification(current_user, notification_id)
    return NotificationResponse(
        id=notif.id,
        user_id=notif.user_id,
        title=notif.title,
        body=notif.body,
        category=notif.category,
        data=__import__("json").loads(notif.data) if notif.data else None,
        read=notif.read,
        created_at=notif.created_at,
    )


@router.post("/{notification_id}/read", status_code=204)
async def mark_notification_read(notification_id: int, current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    await controller.mark_read(current_user, notification_id)
    return None


@router.post("/read-all", status_code=204)
async def mark_all_notifications_read(current_user: User = Depends(get_current_user), controller: NotificationController = Depends(get_controller)):
    await controller.mark_all_read(current_user)
    return None
