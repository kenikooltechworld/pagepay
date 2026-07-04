"""Content management endpoints.

Manage educational content in the catalog: view, filter, and delete content.
Supports filtering by content type and category with full-text search.
"""

import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import ContentCatalog, AdminUser, AdminAuditLog
from app.services.admin_auth import require_permission

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/content", tags=["admin-content"])


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


# ── Content Management ──────────────────────────────────────────────


@router.get("")
async def list_content(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    content_type: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    current_admin: AdminUser = Depends(require_permission("content.view")),
    db: AsyncSession = Depends(get_db),
):
    """List content catalog with filtering and search."""
    q = select(ContentCatalog)
    
    if content_type:
        q = q.where(ContentCatalog.content_type == content_type)
    if category:
        q = q.where(ContentCatalog.category == category)
    if search:
        q = q.where(ContentCatalog.title.ilike(f"%{search}%"))
    
    total = (
        await db.execute(select(func.count()).select_from(q.subquery()))
    ).scalar_one()
    rows = await db.execute(
        q.order_by(ContentCatalog.created_at.desc())
        .limit(limit)
        .offset((page - 1) * limit)
    )
    
    items = [
        {
            "id": c.id,
            "title": c.title,
            "content_type": c.content_type,
            "category": c.category,
            "author": c.author,
            "created_at": c.created_at.isoformat(),
        }
        for c in rows.scalars().all()
    ]
    
    return {"items": items, "total": int(total), "page": page, "limit": limit}


@router.delete("/{content_id}")
async def delete_content(
    content_id: int,
    current_admin: AdminUser = Depends(require_permission("content.delete")),
    db: AsyncSession = Depends(get_db),
):
    """Delete content from catalog."""
    result = await db.execute(
        select(ContentCatalog).where(ContentCatalog.id == content_id)
    )
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    
    db.add(
        _log_admin_action(
            current_admin.id,
            current_admin.email,
            "delete_content",
            "content",
            content_id,
            {"title": content.title},
            None,
        )
    )
    
    await db.delete(content)
    await db.commit()
    
    return {"success": True}
