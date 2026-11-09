"""Data-access layer for the `user_audit_logs` table."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserAuditLog


class UserAuditLogRepository:
    """Repository for `UserAuditLog` persistence operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        user_id: int,
        action: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
        device_fingerprint: str | None = None,
        extra_data: str | None = None,
    ) -> UserAuditLog:
        row = UserAuditLog(
            user_id=user_id,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            device_fingerprint=device_fingerprint,
            extra_data=extra_data,
        )
        self.db.add(row)
        await self.db.commit()
        return row

    async def list_for_user(self, user_id: int, limit: int = 50, offset: int = 0) -> list[UserAuditLog]:
        result = await self.db.execute(
            select(UserAuditLog)
            .where(UserAuditLog.user_id == user_id)
            .order_by(UserAuditLog.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
