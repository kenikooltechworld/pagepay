"""Admin API router.

Covers dashboard, users, finance, content, fraud, AI, config, and logs.
All endpoints require Bearer JWT issued by POST /api/v1/admin/auth/login.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
import json as json

from app.config import settings
from app.database import get_db
from app.models import (
    User, ReadingSession, ContentCatalog, AdEvent, PayoutTransaction,
    Payment, AdminAuditLog, FraudFlag, ContentImportLog, AdminUser,
    StudyMaterial, StudyAsset, Referral, CommunityNote, AiProviderHealth, AppConfig,
    Task, TaskSubmission, UserReputation, SponsorKYC, SponsorWalletTransaction,
)
from app.schemas import (
    AdminLoginRequest, AdminLoginResponse, AdminUserOut, AdminAuditLogOut,
    FraudFlagOut, ContentImportLogOut, DashboardStats, RevenueSummary,
    ConfigItem, ConfigUpdateRequest, UserListResponse,
)
from app.services.admin_auth import (
    get_current_admin, require_permission, create_admin_token, hash_password, verify_password,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/admin", tags=["admin"])


# ── Helpers ─────────────────────────────────────────────────────────


def _log_admin_action(admin_id: int | None, admin_email: str | None, action: str, target_type: str, target_id: int | None,
                      changes: dict | None, ip: str | None, result: str = "success",
                      error: str | None = None):
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


# ── Admin Auth ──────────────────────────────────────────────────────


@router.post("/auth/login")
async def admin_login(payload: AdminLoginRequest, response: Response, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AdminUser).where(AdminUser.email == payload.email.lower()))
    admin = result.scalar_one_or_none()
    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not admin.is_active:
        raise HTTPException(status_code=403, detail="Admin account is disabled")

    admin.last_login_at = datetime.now(timezone.utc)
    await db.commit()

    perms = []
    if admin.permissions:
        import json
        try:
            perms = json.loads(admin.permissions)
        except (json.JSONDecodeError, TypeError):
            pass

    token = create_admin_token(admin.id, admin.role)
    
    # Set httpOnly cookie instead of returning token in response
    response.set_cookie(
        key="admin_session",
        value=token,
        httponly=True,
        secure=False,  # Set to True in production when using HTTPS
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,  # Convert to seconds
        path="/",
    )
    
    return AdminLoginResponse(
        access_token="",  # Don't send token in response body
        token_type="cookie",
        role=admin.role,
        permissions=perms
    )


@router.get("/auth/me", response_model=AdminUserOut)
async def admin_me(current_admin: AdminUser = Depends(get_current_admin)):
    return AdminUserOut(
        id=current_admin.id,
        email=current_admin.email,
        role=current_admin.role,
        is_active=current_admin.is_active,
        last_login_at=current_admin.last_login_at,
        created_at=current_admin.created_at,
    )


@router.post("/auth/logout")
async def admin_logout(response: Response):
    """Clear the admin session cookie."""
    response.delete_cookie(key="admin_session", path="/")
    return {"success": True, "message": "Logged out successfully"}


# ── Dashboard ───────────────────────────────────────────────────────


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats(
    current_admin: AdminUser = Depends(require_permission("dashboard.view")),
    db: AsyncSession = Depends(get_db),
):
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    active_today = (await db.execute(
        select(func.count(func.distinct(ReadingSession.user_id))).where(ReadingSession.start_time >= today_start)
    )).scalar_one()
    pending_payouts = (await db.execute(
        select(func.count(PayoutTransaction.id)).where(PayoutTransaction.status == "pending")
    )).scalar_one()
    pending_notes = (await db.execute(
        select(func.count(CommunityNote.id)).where(CommunityNote.status == "pending")
    )).scalar_one()
    high_fraud = (await db.execute(
        select(func.count(FraudFlag.id)).where(
            FraudFlag.severity == "high", FraudFlag.status == "pending"
        )
    )).scalar_one()

    ad_revenue = (await db.execute(
        select(func.sum(AdEvent.impression_revenue_usd)).where(AdEvent.created_at >= today_start)
    )).scalar_one() or 0
    premium_revenue = (await db.execute(
        select(func.sum(Payment.amount_kobo)).where(
            Payment.status == "success", Payment.created_at >= today_start
        )
    )).scalar_one() or 0

    return DashboardStats(
        total_users=int(total_users),
        active_users_today=int(active_today),
        total_revenue_ngn=int(ad_revenue) + int(premium_revenue),
        pending_payouts=int(pending_payouts),
        pending_notes=int(pending_notes),
        high_severity_fraud_flags=int(high_fraud),
    )


# ── User Management ─────────────────────────────────────────────────


@router.get("/users", response_model=UserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    tier: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    current_admin: AdminUser = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    query = select(User)
    if tier:
        query = query.where(User.tier == tier)
    if status:
        query = query.where(User.status == status)
    if search:
        query = query.where(
            (User.email.ilike(f"%{search}%")) | (User.phone.ilike(f"%{search}%"))
        )
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    rows = await db.execute(query.order_by(User.created_at.desc()).limit(limit).offset((page - 1) * limit))
    items = []
    for u in rows.scalars().all():
        items.append({
            "id": u.id,
            "email": u.email,
            "phone": u.phone,
            "tier": u.tier.value if hasattr(u.tier, "value") else str(u.tier),
            "status": u.status,
            "points_balance": u.points_balance,
            "referral_code": u.referral_code,
            "created_at": u.created_at.isoformat(),
            "last_active_at": u.last_active_at.isoformat() if u.last_active_at else None,
        })
    return UserListResponse(items=items, total=int(total), page=page, limit=limit)


@router.get("/users/{user_id}")
async def get_user_detail(
    user_id: int,
    current_admin: AdminUser = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "tier": user.tier.value if hasattr(user.tier, "value") else str(user.tier),
        "status": user.status,
        "points_balance": user.points_balance,
        "referral_code": user.referral_code,
        "referred_by": user.referred_by,
        "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
        "created_at": user.created_at.isoformat(),
        "last_active_at": user.last_active_at.isoformat() if user.last_active_at else None,
    }


@router.post("/users/{user_id}/ban")
async def ban_user(
    user_id: int,
    reason: str = Query(...),
    current_admin: AdminUser = Depends(require_permission("users.ban")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = "banned"
    user.banned_at = datetime.now(timezone.utc)
    user.ban_reason = reason
    user.banned_by = current_admin.id
    db.add(_log_admin_action(current_admin.id, current_admin.email, "ban_user", "user", user_id,
                             {"status": {"from": "active", "to": "banned"}, "reason": reason}, None))
    await db.commit()
    return {"success": True}


@router.post("/users/{user_id}/unban")
async def unban_user(
    user_id: int,
    current_admin: AdminUser = Depends(require_permission("users.ban")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.status = "active"
    user.banned_at = None
    user.ban_reason = None
    user.banned_by = None
    db.add(_log_admin_action(current_admin.id, current_admin.email, "unban_user", "user", user_id,
                             {"status": {"from": "banned", "to": "active"}}, None))
    await db.commit()
    return {"success": True}


@router.post("/users/{user_id}/adjust-balance")
async def adjust_balance(
    user_id: int,
    amount: int = Query(...),
    reason: str = Query(...),
    current_admin: AdminUser = Depends(require_permission("users.adjust_balance")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    old_balance = user.points_balance
    user.points_balance = max(0, old_balance + amount)
    db.add(_log_admin_action(current_admin.id, current_admin.email, "adjust_balance", "user", user_id,
                             {"points": {"from": old_balance, "to": user.points_balance}, "reason": reason}, None))
    await db.commit()
    return {"success": True, "new_balance": user.points_balance}


@router.get("/users/{user_id}/sessions")
async def get_user_sessions(
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    q = select(ReadingSession).where(ReadingSession.user_id == user_id).order_by(ReadingSession.start_time.desc())
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.limit(limit).offset((page - 1) * limit))
    items = [{"id": s.id, "content_id": s.content_id, "start_time": s.start_time.isoformat(),
               "duration_seconds": s.duration_seconds, "verified": s.verified, "points_earned": s.points_earned}
              for s in rows.scalars().all()]
    return {"items": items, "total": int(total), "page": page, "limit": limit}


@router.get("/users/{user_id}/transactions")
async def get_user_transactions(
    user_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(require_permission("users.view")),
    db: AsyncSession = Depends(get_db),
):
    from app.models import PayoutTransaction, Payment, StudyTransaction
    payout_q = select(PayoutTransaction).where(PayoutTransaction.user_id == user_id)
    payment_q = select(Payment).where(Payment.user_id == user_id)
    study_q = select(StudyTransaction).where(StudyTransaction.user_id == user_id)
    # simplified: return all as items
    items = []
    for q in [payout_q, payment_q, study_q]:
        rows = await db.execute(q.limit(limit).offset((page - 1) * limit))
        for r in rows.scalars().all():
            items.append({"type": type(r).__name__, "id": r.id, "created_at": r.created_at.isoformat()})
    return {"items": items, "total": len(items), "page": page, "limit": limit}


# ── Finance ─────────────────────────────────────────────────────────


@router.get("/revenue/summary")
async def revenue_summary(
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    current_admin: AdminUser = Depends(require_permission("finance.view")),
    db: AsyncSession = Depends(get_db),
):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=30)
    if start_date:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
    if end_date:
        end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)

    ad_rev = (await db.execute(
        select(func.sum(AdEvent.impression_revenue_usd)).where(
            AdEvent.created_at >= start, AdEvent.created_at <= end
        )
    )).scalar_one() or 0
    prem_rev = (await db.execute(
        select(func.sum(Payment.amount_kobo)).where(
            Payment.status == "success", Payment.created_at >= start, Payment.created_at <= end
        )
    )).scalar_one() or 0
    return RevenueSummary(
        total_revenue_ngn=int(ad_rev) + int(prem_rev),
        ad_revenue_ngn=int(ad_rev),
        premium_revenue_ngn=int(prem_rev),
        gross_profit_ngn=int(ad_rev) + int(prem_rev),
        period_start=start.isoformat(),
        period_end=end.isoformat(),
    )


@router.get("/payouts")
async def list_payouts(
    status_filter: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(require_permission("finance.view")),
    db: AsyncSession = Depends(get_db),
):
    q = select(PayoutTransaction)
    if status_filter:
        q = q.where(PayoutTransaction.status == status_filter)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.order_by(PayoutTransaction.created_at.desc()).limit(limit).offset((page - 1) * limit))
    items = [{"id": p.id, "user_id": p.user_id, "amount_kobo": p.amount_kobo, "fee_kobo": p.fee_kobo,
               "status": p.status, "recipient_code": p.recipient_code, "created_at": p.created_at.isoformat()}
              for p in rows.scalars().all()]
    return {"items": items, "total": int(total), "page": page, "limit": limit}


@router.post("/payouts/{payout_id}/approve")
async def approve_payout(
    payout_id: int,
    current_admin: AdminUser = Depends(require_permission("finance.approve")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PayoutTransaction).where(PayoutTransaction.id == payout_id))
    payout = result.scalar_one_or_none()
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    payout.status = "success"
    db.add(_log_admin_action(current_admin.id, current_admin.email, "approve_payout", "payout", payout_id, {}, None))
    await db.commit()
    return {"success": True}


@router.post("/payouts/{payout_id}/reject")
async def reject_payout(
    payout_id: int,
    reason: str = Query(...),
    current_admin: AdminUser = Depends(require_permission("finance.approve")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(PayoutTransaction).where(PayoutTransaction.id == payout_id))
    payout = result.scalar_one_or_none()
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    payout.status = "failed"
    payout.reason = reason
    db.add(_log_admin_action(current_admin.id, current_admin.email, "reject_payout", "payout", payout_id, {"reason": reason}, None))
    await db.commit()
    return {"success": True}


# ── Content ─────────────────────────────────────────────────────────


@router.get("/content")
async def list_content(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    content_type: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    current_admin: AdminUser = Depends(require_permission("content.view")),
    db: AsyncSession = Depends(get_db),
):
    q = select(ContentCatalog)
    if content_type:
        q = q.where(ContentCatalog.content_type == content_type)
    if category:
        q = q.where(ContentCatalog.category == category)
    if search:
        q = q.where(ContentCatalog.title.ilike(f"%{search}%"))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.order_by(ContentCatalog.created_at.desc()).limit(limit).offset((page - 1) * limit))
    items = [{"id": c.id, "title": c.title, "content_type": c.content_type, "category": c.category,
               "author": c.author, "created_at": c.created_at.isoformat()}
              for c in rows.scalars().all()]
    return {"items": items, "total": int(total), "page": page, "limit": limit}


@router.delete("/content/{content_id}")
async def delete_content(
    content_id: int,
    current_admin: AdminUser = Depends(require_permission("content.delete")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(ContentCatalog).where(ContentCatalog.id == content_id))
    content = result.scalar_one_or_none()
    if not content:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(content)
    db.add(_log_admin_action(current_admin.id, current_admin.email, "delete_content", "content", content_id,
                             {"title": content.title}, None))
    await db.commit()
    return {"success": True}


# ── Fraud Detection ─────────────────────────────────────────────────


@router.get("/fraud/sessions")
async def list_fraud_sessions(
    severity: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(require_permission("fraud.view")),
    db: AsyncSession = Depends(get_db),
):
    q = select(FraudFlag).where(FraudFlag.flag_type == "suspicious_session")
    if severity:
        q = q.where(FraudFlag.severity == severity)
    if status:
        q = q.where(FraudFlag.status == status)
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.order_by(FraudFlag.created_at.desc()).limit(limit).offset((page - 1) * limit))
    items = [ FraudFlagOut.model_validate(f).model_dump() for f in rows.scalars().all()]
    return {"items": items, "total": int(total), "page": page, "limit": limit}


@router.get("/fraud/duplicates")
async def list_fraud_duplicates(
    current_admin: AdminUser = Depends(require_permission("fraud.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(FraudFlag).where(FraudFlag.flag_type == "duplicate_account")
        .order_by(FraudFlag.created_at.desc()).limit(50)
    )
    items = [ FraudFlagOut.model_validate(f).model_dump() for f in rows.scalars().all()]
    return {"items": items, "total": len(items)}


@router.get("/fraud/referrals")
async def list_fraud_referrals(
    current_admin: AdminUser = Depends(require_permission("fraud.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(FraudFlag).where(FraudFlag.flag_type == "referral_abuse")
        .order_by(FraudFlag.created_at.desc()).limit(50)
    )
    items = [ FraudFlagOut.model_validate(f).model_dump() for f in rows.scalars().all()]
    return {"items": items, "total": len(items)}


# ── AI Monitoring ──────────────────────────────────────────────────


@router.get("/ai/health")
async def ai_health(
    current_admin: AdminUser = Depends(require_permission("ai.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(select(AiProviderHealth).order_by(AiProviderHealth.provider_name))
    return [{"provider": h.provider_name, "consecutive_failures": h.consecutive_failures,
             "circuit_open_until": h.circuit_open_until.isoformat() if h.circuit_open_until else None,
             "last_failure_at": h.last_failure_at.isoformat() if h.last_failure_at else None}
            for h in rows.scalars().all()]


# ── Config ──────────────────────────────────────────────────────────


@router.get("/config")
async def list_config(
    current_admin: AdminUser = Depends(require_permission("config.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(select(AppConfig).order_by(AppConfig.key))
    return [ConfigItem(key=c.key, value=c.value, environment=c.environment,
                       description=c.description, updated_at=c.updated_at).model_dump()
            for c in rows.scalars().all()]


@router.put("/config/{key}")
async def update_config(
    key: str,
    payload: ConfigUpdateRequest,
    current_admin: AdminUser = Depends(require_permission("config.edit")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AppConfig).where(AppConfig.key == key))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config key not found")
    old = config.value
    config.value = payload.value
    if payload.description is not None:
        config.description = payload.description
    db.add(_log_admin_action(current_admin.id, current_admin.email, "update_config", "config", None,
                             {"key": key, "old": old, "new": payload.value}, None))
    await db.commit()
    return {"success": True}


# ── Audit Logs ──────────────────────────────────────────────────────


@router.get("/logs", response_model=list[AdminAuditLogOut])
async def list_audit_logs(
    action: str | None = Query(None),
    target_type: str | None = Query(None),
    admin_id: int | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(require_permission("logs.view")),
    db: AsyncSession = Depends(get_db),
):
    q = select(AdminAuditLog)
    if action:
        q = q.where(AdminAuditLog.action == action)
    if target_type:
        q = q.where(AdminAuditLog.target_type == target_type)
    if admin_id:
        q = q.where(AdminAuditLog.admin_id == admin_id)
    if start_date:
        q = q.where(AdminAuditLog.created_at >= datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc))
    if end_date:
        q = q.where(AdminAuditLog.created_at <= datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.order_by(AdminAuditLog.created_at.desc()).limit(limit).offset((page - 1) * limit))
    items = [AdminAuditLogOut.model_validate(r).model_dump() for r in rows.scalars().all()]
    return items


# ── Analytics ───────────────────────────────────────────────────────────


@router.get("/analytics/dau")
async def admin_dau(
    days: int = Query(7, ge=1, le=90),
    current_admin: AdminUser = Depends(require_permission("analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = await db.execute(
        select(func.date(ReadingSession.start_time).label("day"), func.count(func.distinct(ReadingSession.user_id)).label("count"))
        .where(ReadingSession.start_time >= cutoff)
        .group_by(func.date(ReadingSession.start_time)).order_by(func.date(ReadingSession.start_time).desc())
    )
    return [{"date": str(r.day), "count": int(r.count)} for r in rows.all()]


@router.get("/analytics/retention")
async def admin_retention(
    current_admin: AdminUser = Depends(require_permission("analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    cutoff_7 = datetime.now(timezone.utc) - timedelta(days=7)
    users = {r.id: r.created_at for r in (await db.execute(select(User.id, User.created_at).where(User.created_at >= cutoff_7))).all()}
    sessions: dict[int, set[str]] = {}
    for uid, day in (await db.execute(select(ReadingSession.user_id, func.date(ReadingSession.start_time)).where(ReadingSession.start_time >= cutoff_7))).all():
        sessions.setdefault(uid, set()).add(str(day))
    cohorts: dict[str, dict] = {}
    for uid, created in users.items():
        key = created.date().isoformat()
        cohorts.setdefault(key, {"day_1": 0, "day_7": 0})
        signup_day = created.date()
        if any(d == (signup_day + timedelta(days=1)).isoformat() for d in sessions.get(uid, set())):
            cohorts[key]["day_1"] += 1
        if any(d == (signup_day + timedelta(days=7)).isoformat() for d in sessions.get(uid, set())):
            cohorts[key]["day_7"] += 1
    return [{"signup_date": k, "day_1": v["day_1"], "day_7": v["day_7"]} for k, v in sorted(cohorts.items())]


@router.get("/analytics/content-performance")
async def admin_content_performance(
    limit: int = Query(20, ge=1, le=100),
    current_admin: AdminUser = Depends(require_permission("analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    rows = await db.execute(
        select(ContentCatalog.id, ContentCatalog.title, func.count(ReadingSession.id).label("reading_sessions"))
        .join(ReadingSession, ReadingSession.content_id == ContentCatalog.id)
        .group_by(ContentCatalog.id, ContentCatalog.title)
        .order_by(desc(func.count(ReadingSession.id))).limit(limit)
    )
    return [{"content_id": r.id, "title": r.title, "reading_sessions": int(r.reading_sessions)} for r in rows.all()]


# ══════════════════════════════════════════════════════════════════════
# PHASE 7: SOCIAL TASKS ADMIN
# ══════════════════════════════════════════════════════════════════════


@router.get("/tasks/kyc/pending")
async def list_pending_kyc(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(require_permission("tasks.kyc")),
    db: AsyncSession = Depends(get_db),
):
    """List pending KYC applications from sponsors."""
    q = (
        select(SponsorKYC, User)
        .join(User, User.id == SponsorKYC.sponsor_id)
        .where(SponsorKYC.status == "pending")
        .order_by(SponsorKYC.submitted_at.desc())
    )
    
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.limit(limit).offset((page - 1) * limit))
    
    items = []
    for kyc, user in rows.all():
        items.append({
            "sponsor_id": kyc.sponsor_id,
            "user_email": user.email,
            "user_phone": user.phone,
            "business_name": kyc.business_name,
            "business_type": kyc.business_type,
            "business_registration_number": kyc.business_registration_number,
            "id_document_type": kyc.id_document_type,
            "id_document_number": kyc.id_document_number,
            "id_document_url": kyc.id_document_url,
            "business_document_url": kyc.business_document_url,
            "contact_person_name": kyc.contact_person_name,
            "contact_person_phone": kyc.contact_person_phone,
            "contact_person_email": kyc.contact_person_email,
            "submitted_at": kyc.submitted_at.isoformat(),
            "status": kyc.status,
        })
    
    return {"items": items, "total": int(total), "page": page, "limit": limit}


@router.post("/tasks/kyc/{sponsor_id}/approve")
async def approve_kyc(
    sponsor_id: int,
    admin_notes: str | None = Query(None),
    current_admin: AdminUser = Depends(require_permission("tasks.kyc")),
    db: AsyncSession = Depends(get_db),
):
    """Approve sponsor KYC application."""
    # Fetch KYC record
    result = await db.execute(select(SponsorKYC).where(SponsorKYC.sponsor_id == sponsor_id))
    kyc = result.scalar_one_or_none()
    
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC application not found")
    
    if kyc.status != "pending":
        raise HTTPException(status_code=400, detail=f"KYC already {kyc.status}")
    
    # Update KYC status
    kyc.status = "approved"
    kyc.reviewed_at = datetime.now(timezone.utc)
    kyc.reviewed_by = current_admin.id
    if admin_notes:
        kyc.admin_notes = admin_notes
    
    # Update user sponsor status
    user_result = await db.execute(select(User).where(User.id == sponsor_id))
    user = user_result.scalar_one_or_none()
    
    if user:
        user.sponsor_verified = True
        user.sponsor_kyc_status = "approved"
        user.sponsor_kyc_reviewed_at = datetime.now(timezone.utc)
        user.sponsor_kyc_reviewer_id = current_admin.id
    
    # Log action
    db.add(_log_admin_action(
        current_admin.id,
        current_admin.email,
        "approve_kyc",
        "sponsor_kyc",
        sponsor_id,
        {"status": "approved", "notes": admin_notes},
        None
    ))
    
    await db.commit()
    
    logger.info(f"Admin {current_admin.id} approved KYC for sponsor {sponsor_id}")
    return {"success": True, "message": "KYC approved successfully"}


@router.post("/tasks/kyc/{sponsor_id}/reject")
async def reject_kyc(
    sponsor_id: int,
    reason: str = Query(..., min_length=10, max_length=500),
    admin_notes: str | None = Query(None),
    current_admin: AdminUser = Depends(require_permission("tasks.kyc")),
    db: AsyncSession = Depends(get_db),
):
    """Reject sponsor KYC application."""
    # Fetch KYC record
    result = await db.execute(select(SponsorKYC).where(SponsorKYC.sponsor_id == sponsor_id))
    kyc = result.scalar_one_or_none()
    
    if not kyc:
        raise HTTPException(status_code=404, detail="KYC application not found")
    
    if kyc.status != "pending":
        raise HTTPException(status_code=400, detail=f"KYC already {kyc.status}")
    
    # Update KYC status
    kyc.status = "rejected"
    kyc.rejection_reason = reason
    kyc.reviewed_at = datetime.now(timezone.utc)
    kyc.reviewed_by = current_admin.id
    if admin_notes:
        kyc.admin_notes = admin_notes
    
    # Update user sponsor status
    user_result = await db.execute(select(User).where(User.id == sponsor_id))
    user = user_result.scalar_one_or_none()
    
    if user:
        user.sponsor_kyc_status = "rejected"
        user.sponsor_kyc_reviewed_at = datetime.now(timezone.utc)
        user.sponsor_kyc_reviewer_id = current_admin.id
    
    # Log action
    db.add(_log_admin_action(
        current_admin.id,
        current_admin.email,
        "reject_kyc",
        "sponsor_kyc",
        sponsor_id,
        {"status": "rejected", "reason": reason, "notes": admin_notes},
        None
    ))
    
    await db.commit()
    
    logger.info(f"Admin {current_admin.id} rejected KYC for sponsor {sponsor_id}: {reason}")
    return {"success": True, "message": "KYC rejected", "reason": reason}


@router.get("/tasks/submissions/flagged")
async def list_flagged_submissions(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_admin: AdminUser = Depends(require_permission("tasks.review")),
    db: AsyncSession = Depends(get_db),
):
    """List task submissions flagged for manual review."""
    q = (
        select(TaskSubmission, Task, User)
        .join(Task, Task.id == TaskSubmission.task_id)
        .join(User, User.id == TaskSubmission.worker_id)
        .where(
            (TaskSubmission.flagged_for_review == True) |
            (TaskSubmission.status == "pending")
        )
        .order_by(TaskSubmission.created_at.desc())
    )
    
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar_one()
    rows = await db.execute(q.limit(limit).offset((page - 1) * limit))
    
    items = []
    for submission, task, worker in rows.all():
        items.append({
            "submission_id": submission.id,
            "task_id": task.id,
            "task_title": task.title,
            "worker_id": worker.id,
            "worker_email": worker.email,
            "proof_type": submission.proof_type,
            "proof_url": submission.proof_url,
            "proof_image_url": submission.proof_image_url,
            "proof_text": submission.proof_text,
            "status": submission.status,
            "ai_confidence": submission.ai_confidence,
            "ai_verification_details": submission.ai_verification_details,
            "fraud_score": submission.fraud_score,
            "flagged_for_review": submission.flagged_for_review,
            "duplicate_screenshot_detected": submission.duplicate_screenshot_detected,
            "submitted_at": submission.submitted_at.isoformat(),
            "reward_amount": task.reward_amount,
        })
    
    return {"items": items, "total": int(total), "page": page, "limit": limit}


@router.post("/tasks/submissions/{submission_id}/approve")
async def admin_approve_submission(
    submission_id: int,
    notes: str | None = Query(None),
    current_admin: AdminUser = Depends(require_permission("tasks.review")),
    db: AsyncSession = Depends(get_db),
):
    """Manually approve a task submission."""
    # Fetch submission
    result = await db.execute(
        select(TaskSubmission, Task)
        .join(Task, Task.id == TaskSubmission.task_id)
        .where(TaskSubmission.id == submission_id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    submission, task = row
    
    if submission.status == "approved":
        raise HTTPException(status_code=400, detail="Submission already approved")
    
    # Update submission
    submission.status = "approved"
    submission.reviewed_by = current_admin.id
    submission.reviewed_at = datetime.now(timezone.utc)
    
    # Credit worker (same logic as task_processor)
    worker_result = await db.execute(select(User).where(User.id == submission.worker_id))
    worker = worker_result.scalar_one_or_none()
    
    if worker:
        net_reward = int(task.reward_amount * (100 - task.platform_fee_percent) / 100)
        worker.points_balance += net_reward
        submission.reward_paid = net_reward
        submission.payment_status = "paid"
        submission.paid_at = datetime.now(timezone.utc)
    
    # Update task stats
    task.approved_count += 1
    task.completed_count += 1
    
    if task.pending_count > 0:
        task.pending_count -= 1
    
    if task.completed_count >= task.max_completions:
        task.status = "completed"
        task.completed_at = datetime.now(timezone.utc)
    
    # Update reputation
    rep_result = await db.execute(select(UserReputation).where(UserReputation.user_id == submission.worker_id))
    reputation = rep_result.scalar_one_or_none()
    
    if not reputation:
        reputation = UserReputation(user_id=submission.worker_id)
        db.add(reputation)
    
    reputation.tasks_approved += 1
    reputation.tasks_completed += 1
    reputation.total_earnings += submission.reward_paid
    
    if reputation.tasks_completed > 0:
        reputation.approval_rate = reputation.tasks_approved / reputation.tasks_completed
    
    # Log action
    db.add(_log_admin_action(
        current_admin.id,
        current_admin.email,
        "approve_submission",
        "task_submission",
        submission_id,
        {"task_id": task.id, "worker_id": submission.worker_id, "reward": net_reward, "notes": notes},
        None
    ))
    
    await db.commit()
    
    logger.info(f"Admin {current_admin.id} approved submission {submission_id}")
    return {"success": True, "message": "Submission approved", "reward_paid": net_reward}


@router.post("/tasks/submissions/{submission_id}/reject")
async def admin_reject_submission(
    submission_id: int,
    reason: str = Query(..., min_length=10, max_length=500),
    current_admin: AdminUser = Depends(require_permission("tasks.review")),
    db: AsyncSession = Depends(get_db),
):
    """Manually reject a task submission."""
    # Fetch submission
    result = await db.execute(
        select(TaskSubmission, Task)
        .join(Task, Task.id == TaskSubmission.task_id)
        .where(TaskSubmission.id == submission_id)
    )
    row = result.one_or_none()
    
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    submission, task = row
    
    if submission.status in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail=f"Submission already {submission.status}")
    
    # Update submission
    submission.status = "rejected"
    submission.rejection_reason = reason
    submission.reviewed_by = current_admin.id
    submission.reviewed_at = datetime.now(timezone.utc)
    
    # Update task stats
    task.rejected_count += 1
    
    if task.pending_count > 0:
        task.pending_count -= 1
    
    # Update reputation
    rep_result = await db.execute(select(UserReputation).where(UserReputation.user_id == submission.worker_id))
    reputation = rep_result.scalar_one_or_none()
    
    if reputation:
        reputation.tasks_rejected += 1
        if reputation.tasks_completed > 0:
            reputation.approval_rate = reputation.tasks_approved / (reputation.tasks_approved + reputation.tasks_rejected)
    
    # Log action
    db.add(_log_admin_action(
        current_admin.id,
        current_admin.email,
        "reject_submission",
        "task_submission",
        submission_id,
        {"task_id": task.id, "worker_id": submission.worker_id, "reason": reason},
        None
    ))
    
    await db.commit()
    
    logger.info(f"Admin {current_admin.id} rejected submission {submission_id}: {reason}")
    return {"success": True, "message": "Submission rejected", "reason": reason}


@router.get("/tasks/analytics")
async def tasks_analytics(
    days: int = Query(30, ge=1, le=90),
    current_admin: AdminUser = Depends(require_permission("analytics.view")),
    db: AsyncSession = Depends(get_db),
):
    """Get Phase 7 tasks analytics."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Task stats
    total_tasks = (await db.execute(select(func.count(Task.id)))).scalar_one()
    active_tasks = (await db.execute(select(func.count(Task.id)).where(Task.status == "active"))).scalar_one()
    completed_tasks = (await db.execute(select(func.count(Task.id)).where(Task.status == "completed"))).scalar_one()
    
    # Submission stats
    total_submissions = (await db.execute(
        select(func.count(TaskSubmission.id)).where(TaskSubmission.created_at >= cutoff)
    )).scalar_one()
    
    approved_submissions = (await db.execute(
        select(func.count(TaskSubmission.id)).where(
            TaskSubmission.status == "approved",
            TaskSubmission.created_at >= cutoff
        )
    )).scalar_one()
    
    pending_submissions = (await db.execute(
        select(func.count(TaskSubmission.id)).where(TaskSubmission.status == "pending")
    )).scalar_one()
    
    # Revenue stats
    platform_revenue = (await db.execute(
        select(func.sum(Task.platform_fee_amount)).where(Task.status == "completed")
    )).scalar_one() or 0
    
    total_paid_out = (await db.execute(
        select(func.sum(TaskSubmission.reward_paid)).where(TaskSubmission.payment_status == "paid")
    )).scalar_one() or 0
    
    # User stats
    total_workers = (await db.execute(
        select(func.count(User.id)).where(User.is_worker == True)
    )).scalar_one()
    
    total_sponsors = (await db.execute(
        select(func.count(User.id)).where(User.is_sponsor == True)
    )).scalar_one()
    
    verified_sponsors = (await db.execute(
        select(func.count(User.id)).where(User.sponsor_verified == True)
    )).scalar_one()
    
    pending_kyc = (await db.execute(
        select(func.count(SponsorKYC.sponsor_id)).where(SponsorKYC.status == "pending")
    )).scalar_one()
    
    return {
        "period_days": days,
        "tasks": {
            "total": int(total_tasks),
            "active": int(active_tasks),
            "completed": int(completed_tasks),
        },
        "submissions": {
            "total": int(total_submissions),
            "approved": int(approved_submissions),
            "pending": int(pending_submissions),
            "approval_rate": round(approved_submissions / total_submissions * 100, 2) if total_submissions > 0 else 0,
        },
        "revenue": {
            "platform_fee_collected": int(platform_revenue),
            "total_paid_to_workers": int(total_paid_out),
            "net_margin": int(platform_revenue) - int(total_paid_out),
        },
        "users": {
            "total_workers": int(total_workers),
            "total_sponsors": int(total_sponsors),
            "verified_sponsors": int(verified_sponsors),
            "pending_kyc": int(pending_kyc),
        },
    }
