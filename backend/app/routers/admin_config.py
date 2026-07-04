"""Configuration management endpoints.

Manage application configuration values stored in database.
Update feature flags, thresholds, and settings without redeployment.
All changes are logged in audit trail.
"""

import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AppConfig, AdminUser, AdminAuditLog
from app.schemas import ConfigItem, ConfigUpdateRequest
from app.services.admin_auth import require_permission

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/config", tags=["admin-config"])


# ── Helpers ─────────────────────────────────────────────────────────


def _log_admin_action(
    admin_id: int | None,
    admin_email: str | None,
    action: str,
    target_type: str,
    target_id: int | None,
    changes: dict | None,
    ip: str | None,
    result: str = "success",
    error: str | None = None,
):
    """Create an audit log entry for admin actions."""
    return AdminAuditLog(
        admin_id=admin_id,
        admin_email=admin_email,
        action=action,
        target_type=target_type,
        target_id=target_id,
        changes=json.dumps(changes) if changes else None,
        ip_address=ip,
        result=result,
        error_message=error,
    )


# ── Configuration Management ────────────────────────────────────────


@router.get("")
async def list_config(
    current_admin: AdminUser = Depends(require_permission("config.view")),
    db: AsyncSession = Depends(get_db),
):
    """List all application configuration values."""
    rows = await db.execute(
        select(AppConfig).order_by(AppConfig.key)
    )
    
    return [
        ConfigItem(
            key=c.key,
            value=c.value,
            environment=c.environment,
            description=c.description,
            updated_at=c.updated_at,
        ).model_dump()
        for c in rows.scalars().all()
    ]


@router.put("/{key}")
async def update_config(
    key: str,
    payload: ConfigUpdateRequest,
    current_admin: AdminUser = Depends(require_permission("config.edit")),
    db: AsyncSession = Depends(get_db),
):
    """Update a configuration value."""
    result = await db.execute(
        select(AppConfig).where(AppConfig.key == key)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config key not found")
    
    old = config.value
    config.value = payload.value
    if payload.description is not None:
        config.description = payload.description
    
    db.add(
        _log_admin_action(
            current_admin.id,
            current_admin.email,
            "update_config",
            "config",
            None,
            {"key": key, "old": old, "new": payload.value},
            None,
        )
    )
    
    await db.commit()
    
    return {"success": True}
