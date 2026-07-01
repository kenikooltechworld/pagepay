# PagePay Admin Management: Gap Analysis

## Current Admin Implementation Status

### ✅ Implemented Admin Endpoints

#### Content Management (`/admin/content/*`)
- `POST /admin/content/import` - Import books/articles from Gutendex/GNews
- `POST /admin/content/slice` - Slice long content into 2-minute reads
- `POST /admin/content/reslice` - Re-slice all content from scratch
- `GET /admin/content/platform-balance` - Monitor Paystack balance

#### Analytics (Partially Public - `/api/v1/analytics/*`)
- `GET /analytics/dau` - Daily active users (last 7 days)
- `GET /analytics/retention` - User retention cohorts
- `GET /analytics/content-performance` - Top performing content

### ❌ Missing Critical Admin Features

## 1. USER MANAGEMENT (High Priority - Phase 1-6)

### Missing Endpoints:
- `GET /admin/users` - List all users with filters (tier, status, date range)
- `GET /admin/users/{user_id}` - View detailed user profile
- `PATCH /admin/users/{user_id}` - Update user (ban, tier upgrade, role change)
- `DELETE /admin/users/{user_id}` - Delete/deactivate user account
- `POST /admin/users/{user_id}/adjust-balance` - Manually adjust points balance
- `GET /admin/users/{user_id}/sessions` - View user's reading history
- `GET /admin/users/{user_id}/transactions` - View all transactions (wallet, payouts)

### Use Cases:
- Ban abusive users trying to game the system
- Manually grant premium tier to partners/beta testers
- Investigate fraud complaints (review user sessions + transactions)
- Adjust balance when bugs cause incorrect credits
- Monitor top earners for anti-cheat validation

---

## 2. FINANCIAL MANAGEMENT (Critical - Phase 2, 4)

### Missing Endpoints:
- `GET /admin/revenue/summary` - Total revenue breakdown (ads vs premium)
- `GET /admin/revenue/ads` - Ad revenue by provider (AdMob vs AppLovin)
- `GET /admin/payouts/pending` - Pending withdrawal requests requiring manual review
- `GET /admin/payouts/history` - All payout transactions with filters
- `POST /admin/payouts/{tx_id}/approve` - Manually approve stuck withdrawals
- `POST /admin/payouts/{tx_id}/reject` - Reject fraudulent withdrawal
- `GET /admin/payments/subscriptions` - All premium subscriptions (active, expired, failed)
- `POST /admin/payments/refund` - Issue refund for subscription

### Use Cases:
- Monitor daily ad revenue vs user payouts (profit margin)
- Detect withdrawal fraud patterns (same bank account, multiple users)
- Handle Paystack webhook failures (manual approval)
- Track premium subscription churn rate
- Reconcile Paystack auto-settlement issues

---

## 3. CONTENT MODERATION (Medium Priority - Phase 3, 5)

### Missing Endpoints:
- `GET /admin/content/catalog` - Full catalog with management actions
- `DELETE /admin/content/{content_id}` - Remove inappropriate content
- `PATCH /admin/content/{content_id}` - Edit content metadata
- `GET /admin/community/notes/pending` - Community notes awaiting approval
- `POST /admin/community/notes/{note_id}/approve` - Approve community note
- `POST /admin/community/notes/{note_id}/reject` - Reject community note
- `GET /admin/community/reports` - User-reported content

### Use Cases:
- Remove copyright-infringing books
- Moderate community study notes before public display
- Handle DMCA takedown requests
- Flag inappropriate/offensive content

---

## 4. AI PROVIDER MONITORING (Medium Priority - Phase 3)

### Missing Endpoints:
- `GET /admin/ai/health` - Current health status of all AI providers
- `GET /admin/ai/usage` - Token usage + costs per provider
- `POST /admin/ai/reset-circuit` - Manually reset circuit breaker for provider
- `GET /admin/ai/errors` - Recent AI failures by provider + task type

### Use Cases:
- Monitor Gemini/Groq/OpenRouter rate limits
- Detect when a provider goes down (circuit breaker stuck open)
- Estimate monthly AI costs
- Optimize provider routing based on success rates

---

## 5. FRAUD DETECTION & SECURITY (High Priority - Phase 1-6)

### Missing Endpoints:
- `GET /admin/fraud/suspicious-sessions` - Sessions flagged by anti-cheat
- `GET /admin/fraud/duplicate-accounts` - Users with shared device IDs
- `GET /admin/fraud/referral-abuse` - Suspicious referral patterns
- `POST /admin/fraud/flag-user` - Mark user for manual review
- `GET /admin/fraud/ad-fraud` - Invalid traffic patterns (ad clicks without revenue)

### Use Cases:
- Detect bots auto-scrolling through content
- Catch referral fraud (self-referrals, farms)
- Prevent AdMob account suspension from invalid traffic
- Identify users exploiting bugs for free points

---

## 6. SYSTEM CONFIGURATION (Low Priority - OTA)

### Missing Endpoints:
- `GET /admin/config` - List all app_config key-value pairs
- `PUT /admin/config/{key}` - Update config value (point rates, ad unit IDs)
- `POST /admin/config/rollback` - Revert to previous config snapshot
- `GET /admin/config/history` - Audit log of config changes

### Use Cases:
- Change point earn rate without deploying new backend
- Swap AdMob ad unit IDs when testing new placements
- A/B test different fee tiers for withdrawals
- Rollback bad config that broke production

---

## 7. CRON JOB MONITORING (Low Priority - DevOps)

### Missing Endpoints:
- `GET /admin/jobs/status` - Status of all scheduled jobs (import, slice, expire subs)
- `POST /admin/jobs/trigger` - Manually trigger a cron job
- `GET /admin/jobs/logs` - Recent job execution logs

### Use Cases:
- Debug why content import stopped running
- Manually trigger subscription expiration after Paystack auto-settlement
- Monitor job health (last run time, success rate)

---

## 8. REFERRAL & GROWTH ANALYTICS (Low Priority - Phase 5)

### Missing Endpoints:
- `GET /admin/referrals/leaderboard` - Top referrers by count
- `GET /admin/referrals/fraud-check` - Suspicious referral patterns
- `GET /admin/growth/cohorts` - User acquisition cohorts by source

### Use Cases:
- Reward top referrers with bonuses
- Track organic vs paid user acquisition
- Measure referral conversion rates

---

## Recommended Implementation Priority

### Phase 1: Core Admin (Week 1-2)
**Blocking revenue operations:**
1. User management (list, view, ban, adjust balance)
2. Financial dashboard (revenue summary, payout management)
3. Fraud detection basics (suspicious sessions, duplicate accounts)

### Phase 2: Operational Tools (Week 3-4)
**Reducing manual work:**
4. Content moderation (community notes approval, content removal)
5. AI provider monitoring (health, usage, circuit breaker reset)
6. Payout manual approval/rejection flow

### Phase 3: Optimization (Week 5+)
**Nice-to-have analytics:**
7. System config OTA editor
8. Cron job monitoring
9. Referral analytics + fraud check

---

## Security Requirements

### Authentication
Current: X-Admin-Token header (shared secret from settings.admin_token)
**Recommendation:** Keep for now (simple, works), but add:
- Admin user login with separate admin JWT
- Role-based access (super_admin vs support_agent)
- Audit log of all admin actions (who changed what, when)

### Authorization
Current: All admin endpoints require same token
**Recommendation:**
- Support agents: Read-only access (view users, view transactions)
- Moderators: Approve/reject community content only
- Finance team: Payout approval, revenue reports only
- Super admin: Full access

### Rate Limiting
Current: None on admin endpoints
**Recommendation:**
- 100 requests/minute per admin token
- Extra strict on mutation endpoints (10/minute for balance adjustments)

---

## Database Schema Additions Needed

### Admin Audit Log
```python
class AdminAuditLog(Base):
    __tablename__ = "admin_audit_log"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    admin_user_id: Mapped[int] = mapped_column(BigInteger, index=True)  # Or admin_token hash
    action: Mapped[str] = mapped_column(String(100))  # "ban_user", "adjust_balance", etc
    target_type: Mapped[str] = mapped_column(String(50))  # "user", "content", "payment"
    target_id: Mapped[int] = mapped_column(BigInteger)
    changes: Mapped[str] = mapped_column(Text)  # JSON of before/after values
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

### Fraud Flags
```python
class FraudFlag(Base):
    __tablename__ = "fraud_flags"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    flag_type: Mapped[str] = mapped_column(String(50))  # "suspicious_session", "referral_abuse", etc
    severity: Mapped[str] = mapped_column(String(20))  # "low", "medium", "high"
    details: Mapped[str] = mapped_column(Text)  # JSON
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | reviewed | resolved
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

---

## Frontend Admin Dashboard

**Not yet built.** Options:

### Option 1: Web Admin Dashboard (Recommended)
- Separate Next.js/React app (`/admin-dashboard`)
- Consumes same FastAPI backend via admin endpoints
- Easy to deploy alongside backend (Railway, Vercel)
- No mobile app complexity

### Option 2: React Native Admin App
- Build separate Expo app for admins
- Uses same PagePay codebase
- Harder to maintain, slower to build

### Option 3: Third-Party Tools
- Retool, Forest Admin, Budibase
- Connect directly to MySQL + FastAPI
- Fastest to ship but limited customization

**Recommendation:** Build Web Admin Dashboard (Option 1) in Phase 1-2 for critical ops. Use Retool (Option 3) as temporary bridge until then.

---

## Immediate Action Items

1. **This week:** Implement user management endpoints (list, view, ban, balance adjustment)
2. **This week:** Build financial dashboard endpoints (revenue summary, payout management)
3. **Next week:** Add fraud detection endpoints (suspicious sessions, duplicate accounts)
4. **Next week:** Create admin audit log table + logging middleware
5. **Later:** Build web admin dashboard UI

---

## Estimated Development Time

- User management endpoints: **2 days**
- Financial management endpoints: **3 days**
- Fraud detection endpoints: **2 days**
- Content moderation endpoints: **1 day**
- AI provider monitoring endpoints: **1 day**
- Admin audit log + middleware: **1 day**
- Web admin dashboard (basic): **5 days**

**Total:** ~15 days for full admin system (excluding dashboard UI).

---

## Summary

**Current State:** 
- 4 admin endpoints (content import/slice, balance check)
- No user management, no financial oversight, no fraud tools

**Blocker for Scale:**
- Cannot handle fraud at 1,000+ users without manual SQL queries
- Cannot approve/reject stuck payouts without direct DB access
- Cannot monitor revenue vs costs in real-time

**Immediate Need:** User management + financial dashboard (Week 1-2)
