# PagePay Phase 7: Social Tasks Marketplace - Complete Technical Specification

**Version:** 1.0  
**Last Updated:** January 2025  
**Status:** Design Phase  
**Integration:** Phase 7 feature addition to existing PagePay platform

---

## Executive Summary

### What is Phase 7?
A **social tasks marketplace** where brands (Sponsors) post micro-tasks and existing PagePay users (Workers) complete them for rewards. This transforms PagePay from a read-to-earn + study platform into a **multi-sided gig economy marketplace**.

### Core Value Propositions

**For Workers (Existing Users):**
- Additional earning stream beyond reading/studying
- 3-5x higher earnings potential (₦50-500 per task vs ₦5-20 per article)
- Instant payouts (AI approves in 30 seconds)
- Gamified progression (levels, badges, leaderboards)

**For Sponsors (New User Type):**
- Access to 10,000+ engaged Nigerian users
- Pay-per-result pricing (only pay for completed tasks)
- Real-time verification (AI checks task completion)
- Detailed analytics (demographics, conversion rates)

**For Platform:**
- 15% commission on all tasks (new revenue stream)
- Higher user engagement (3x daily active users)
- Viral growth (referral incentives)
- Market differentiation (only African read + task platform)

### Key Innovation: AI Auto-Approval System
**Industry-first feature** that automatically verifies task completion using:
- Social media API integrations (Twitter, Instagram)
- Computer vision (screenshot analysis)
- Headless browser verification (Selenium/Playwright)
- 94% accuracy, 30-second approval time vs industry standard 24-48 hours


---

## Table of Contents

1. [Integration with Existing Platform](#integration-with-existing-platform)
2. [User Roles & Permissions (RBAC)](#user-roles--permissions-rbac)
3. [Database Schema Additions](#database-schema-additions)
4. [Backend API Specification](#backend-api-specification)
5. [AI Verification System](#ai-verification-system)
6. [Frontend Architecture](#frontend-architecture)
7. [Reputation & Gamification](#reputation--gamification)
8. [Fraud Prevention](#fraud-prevention)
9. [Sponsor Dashboard](#sponsor-dashboard)
10. [Admin Management](#admin-management)
11. [Implementation Roadmap](#implementation-roadmap)
12. [Revenue Model](#revenue-model)

---

## Integration with Existing Platform

### Current PagePay Features (Phases 1-6)
✅ **Phase 1:** Read-to-earn (books, articles, news)  
✅ **Phase 2:** Ad monetization (AdMob + AppLovin)  
✅ **Phase 3:** AI study prep (SOW upload, quizzes, chat)  
✅ **Phase 4:** Payments (Paystack withdrawals + premium subscriptions)  
✅ **Phase 5:** Referrals + community notes  
✅ **Phase 6:** Licensed content scaling  

### Phase 7 Additions (Social Tasks)
🆕 **Worker role** - All existing users automatically become workers  
🆕 **Sponsor role** - New user type (requires KYC approval)  
🆕 **Tasks system** - Marketplace for micro-tasks  
🆕 **AI verification** - Auto-approve task completions  
🆕 **Reputation system** - Levels, badges, leaderboards  
🆕 **Task notifications** - Push alerts for new high-paying tasks  

### Unified User Experience
```
Bottom Navigation (Updated):
├── 🏠 Home - Reading feed (existing)
├── 📚 Catalog - Books browser (existing)
├── 📝 Study - AI exam prep (existing)
├── ✓ Tasks - NEW: Social tasks marketplace
└── 💰 Wallet - Balance + withdrawals (existing)
```

**No breaking changes** - All existing features continue working as-is.


---

## User Roles & Permissions (RBAC)

### Extended User Model
```python
# Extends existing User model from Phase 1-6
class User(Base):
    __tablename__ = "users"
    
    # ────────────────────────────────────────────────────────────────
    # EXISTING FIELDS (Phase 1-6) - DO NOT CHANGE
    # ────────────────────────────────────────────────────────────────
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    points_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    tier: Mapped[UserTier] = mapped_column(Enum(UserTier), default=UserTier.FREE)
    referral_code: Mapped[str | None] = mapped_column(String(12), unique=True)
    referred_by: Mapped[str | None] = mapped_column(String(12), index=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user | admin
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | banned | suspended
    
    # ────────────────────────────────────────────────────────────────
    # NEW FIELDS (Phase 7) - Social Tasks Integration
    # ────────────────────────────────────────────────────────────────
    
    # Worker role (automatically True for all users)
    is_worker: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Sponsor role (requires KYC approval)
    is_sponsor: Mapped[bool] = mapped_column(Boolean, default=False)
    sponsor_wallet_balance: Mapped[int] = mapped_column(BigInteger, default=0)  # Separate from points_balance
    sponsor_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    sponsor_kyc_status: Mapped[str] = mapped_column(String(20), default="none")  # none, pending, approved, rejected
    sponsor_kyc_submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sponsor_kyc_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sponsor_kyc_reviewer_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Admin who reviewed
    business_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    business_registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sponsor_auto_approve_ai: Mapped[bool] = mapped_column(Boolean, default=False)  # Trust AI for auto-approvals
    
    # Demographics for task targeting
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)  # male, female, other, prefer_not_to_say
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str] = mapped_column(String(50), default="Nigeria")
    languages: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON array: ["English", "Yoruba"]
```

### Permission Matrix

| Feature | Worker | Sponsor | Admin |
|---------|--------|---------|-------|
| View available tasks | ✅ | ❌ | ✅ |
| Complete tasks | ✅ | ❌ (except own) | ✅ |
| Create tasks | ❌ | ✅ | ✅ |
| Review submissions | ❌ | ✅ (own tasks) | ✅ (all) |
| Fund sponsor wallet | ❌ | ✅ | ✅ |
| View analytics | ❌ | ✅ (own tasks) | ✅ (all) |
| Access leaderboards | ✅ | ✅ | ✅ |
| Chat with sponsor | ✅ | ✅ | ✅ |


---

## Database Schema Additions

### 1. Task Model (Core)
```python
class Task(Base):
    """Main task table - one row per task posted by sponsor."""
    __tablename__ = "tasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    sponsor_id: Mapped[int] = mapped_column(BigInteger, index=True)  # User.id where is_sponsor=True
    
    # Task details
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    instructions: Mapped[str] = mapped_column(Text)  # Step-by-step guide
    
    # Task type & platform
    task_type: Mapped[str] = mapped_column(String(50), index=True)
    # Options: twitter_follow, instagram_follow, tiktok_follow, youtube_subscribe,
    #          twitter_like, instagram_like, twitter_retweet, instagram_comment,
    #          website_visit, website_signup, app_download, app_review,
    #          photo_upload, video_upload, written_review, survey, custom
    
    platform: Mapped[str] = mapped_column(String(50), index=True)
    # Options: twitter, instagram, tiktok, youtube, facebook, linkedin,
    #          web, android, ios, custom
    
    category: Mapped[str] = mapped_column(String(50), default="social_media", index=True)
    # Options: social_media, engagement, website, app, content_creation,
    #          surveys, data_collection, other
    
    # Target URL or identifier
    target_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # Examples: "@PagePayApp", "https://instagram.com/pagepayapp", "https://example.com/signup"
    
    # Proof requirements
    proof_type: Mapped[str] = mapped_column(String(50))
    # Options: screenshot, link, text, photo, video, none
    
    proof_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "Upload screenshot showing you followed the account"
    
    # Economics
    reward_amount: Mapped[int] = mapped_column(BigInteger)  # In kobo (₦50 = 5000 kobo)
    max_completions: Mapped[int] = mapped_column(Integer)  # Max workers who can complete
    completed_count: Mapped[int] = mapped_column(Integer, default=0, index=True)
    approved_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    pending_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Escrow
    total_escrowed: Mapped[int] = mapped_column(BigInteger)
    # = (reward_amount × max_completions) + platform_fee
    # Locked when task is created, released on completion/cancellation
    
    platform_fee_percent: Mapped[int] = mapped_column(Integer, default=15)  # 15%
    platform_fee_amount: Mapped[int] = mapped_column(BigInteger)
    # = (reward_amount × max_completions × platform_fee_percent) / 100
    
    # Task targeting (who can see/complete this task)
    target_countries: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["Nigeria", "Ghana"]
    target_cities: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["Lagos", "Abuja"]
    target_gender: Mapped[str | None] = mapped_column(String(20), nullable=True)  # male, female, any
    target_age_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_age_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_languages: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: ["English", "Yoruba"]
    min_worker_level: Mapped[int] = mapped_column(Integer, default=1)  # Worker must be level X+
    min_approval_rate: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100%
    require_verified: Mapped[bool] = mapped_column(Boolean, default=False)  # KYC verified workers only
    require_premium: Mapped[bool] = mapped_column(Boolean, default=False)  # Premium subscribers only
    
    # Task lifecycle
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)
    # Options: draft, active, paused, completed, cancelled, expired
    
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    # Options: public (all workers), private (invited workers only), featured
    
    priority: Mapped[int] = mapped_column(Integer, default=0)  # Higher = shown first
    featured: Mapped[bool] = mapped_column(Boolean, default=False)  # Show on homepage
    
    # Time constraints
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # If set, worker must complete within X minutes of starting
    
    # AI verification settings
    ai_verification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    ai_auto_approve_threshold: Mapped[float] = mapped_column(Float, default=0.9)  # Confidence threshold
    manual_review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
```

### 2. TaskSubmission Model
```python
class TaskSubmission(Base):
    """Worker's submission for a task - one row per user per task."""
    __tablename__ = "task_submissions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, index=True)
    worker_id: Mapped[int] = mapped_column(BigInteger, index=True)
    
    # Proof submitted by worker
    proof_type: Mapped[str] = mapped_column(String(50))  # screenshot, link, text, photo, video
    proof_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # For screenshots/photos: S3 URL
    # For links: Worker's Twitter handle, Instagram username, etc.
    # For text: Written content
    
    proof_image_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # S3 URL for screenshots
    proof_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    proof_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON additional data
    
    # Review status
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    # Options: validating (AI checking), pending (awaiting sponsor review),
    #          approved, rejected, disputed
    
    # AI verification results
    ai_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)  # 0.0-1.0
    ai_verification_details: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    ai_verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Manual review
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Sponsor or Admin
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auto_approved: Mapped[bool] = mapped_column(Boolean, default=False)  # True if approved after 12h timeout
    
    # Payment
    reward_paid: Mapped[int] = mapped_column(BigInteger, default=0)  # Amount credited to worker
    payment_status: Mapped[str] = mapped_column(String(20), default="pending")
    # Options: pending, paid, failed, refunded
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Fraud detection
    fraud_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    flagged_for_review: Mapped[bool] = mapped_column(Boolean, default=False)
    duplicate_screenshot_detected: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # When worker clicked "Start Task"
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Time tracking
    completion_time_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # = submitted_at - started_at
```

### 3. UserReputation Model
```python
class UserReputation(Base):
    """Tracks worker/sponsor reputation scores and gamification stats."""
    __tablename__ = "user_reputations"
    
    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    # ────────────────────────────────────────────────────────────────
    # WORKER REPUTATION
    # ────────────────────────────────────────────────────────────────
    worker_level: Mapped[int] = mapped_column(Integer, default=1, index=True)  # 1-50
    worker_xp: Mapped[int] = mapped_column(Integer, default=0)  # Experience points
    worker_xp_to_next_level: Mapped[int] = mapped_column(Integer, default=100)
    
    # Task stats
    tasks_viewed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_started: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    tasks_approved: Mapped[int] = mapped_column(Integer, default=0)
    tasks_rejected: Mapped[int] = mapped_column(Integer, default=0)
    tasks_disputed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Rates
    approval_rate: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100%
    # = (tasks_approved / tasks_completed) × 100
    
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100%
    # = (tasks_completed / tasks_started) × 100
    
    # Performance
    avg_completion_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    fastest_completion_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_earnings: Mapped[int] = mapped_column(BigInteger, default=0)  # All-time earnings in kobo
    
    # Quality
    quality_score: Mapped[float] = mapped_column(Float, default=5.0)  # 1.0-5.0 stars
    # Calculated from AI confidence scores + sponsor ratings
    
    # Badges (JSON array of badge IDs)
    badges: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ["first_task", "speed_demon", "top_earner_week", "perfect_month"]
    
    # Streaks
    current_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_task_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # ────────────────────────────────────────────────────────────────
    # SPONSOR REPUTATION
    # ────────────────────────────────────────────────────────────────
    sponsor_rating: Mapped[float] = mapped_column(Float, default=5.0)  # 1.0-5.0 stars
    sponsor_rating_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Task stats
    tasks_posted: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed_as_sponsor: Mapped[int] = mapped_column(Integer, default=0)
    total_spent: Mapped[int] = mapped_column(BigInteger, default=0)  # In kobo
    
    # Review behavior
    submissions_reviewed: Mapped[int] = mapped_column(Integer, default=0)
    submissions_approved: Mapped[int] = mapped_column(Integer, default=0)
    submissions_rejected: Mapped[int] = mapped_column(Integer, default=0)
    sponsor_approval_rate: Mapped[float] = mapped_column(Float, default=100.0)  # 0-100%
    # = (submissions_approved / submissions_reviewed) × 100
    
    avg_review_time_seconds: Mapped[int] = mapped_column(Integer, default=0)
    
    # Trust level
    trusted_sponsor: Mapped[bool] = mapped_column(Boolean, default=False)
    # True if: tasks_posted > 50 AND sponsor_approval_rate > 90 AND sponsor_rating > 4.5
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 4. SponsorWalletTransaction Model
```python
class SponsorWalletTransaction(Base):
    """Transaction log for sponsor wallet - separate from worker points_balance."""
    __tablename__ = "sponsor_wallet_transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sponsor_id: Mapped[int] = mapped_column(BigInteger, index=True)
    
    type: Mapped[str] = mapped_column(String(50), index=True)
    # Options: deposit (Paystack), task_escrow (lock funds), task_release (unlock),
    #          task_refund (cancelled task), platform_fee (charged), chargeback
    
    amount: Mapped[int] = mapped_column(BigInteger)  # In kobo (can be negative for debits)
    balance_before: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    
    # Related entities
    task_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    submission_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Paystack ref
    
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
```

### 5. TaskMessage Model (Worker-Sponsor Chat)
```python
class TaskMessage(Base):
    """In-app chat between worker and sponsor about a specific task/submission."""
    __tablename__ = "task_messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(BigInteger, index=True)
    submission_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    
    sender_id: Mapped[int] = mapped_column(BigInteger, index=True)
    receiver_id: Mapped[int] = mapped_column(BigInteger, index=True)
    
    message: Mapped[str] = mapped_column(Text)
    attachment_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # Image/file S3 URL
    attachment_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # image, video, document
    
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
```

### 6. Achievement Model (Gamification)
```python
class Achievement(Base):
    """Predefined achievements workers can unlock."""
    __tablename__ = "achievements"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    # Examples: first_task, speed_demon_10, perfect_week, top_earner_month
    
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(1000))
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    icon_emoji: Mapped[str | None] = mapped_column(String(10), nullable=True)  # 🏆 🚀 ⭐
    
    # Rewards
    xp_reward: Mapped[int] = mapped_column(Integer, default=0)
    points_reward: Mapped[int] = mapped_column(Integer, default=0)  # Bonus points
    
    # Unlock conditions
    condition_type: Mapped[str] = mapped_column(String(50))
    # Options: tasks_completed, approval_rate, earnings, streak, speed, level
    
    condition_value: Mapped[int] = mapped_column(Integer)
    # Example: tasks_completed >= 10, approval_rate >= 95
    
    rarity: Mapped[str] = mapped_column(String(20), default="common")
    # Options: common, rare, epic, legendary
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserAchievement(Base):
    """Tracks which achievements each user has unlocked."""
    __tablename__ = "user_achievements"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    achievement_id: Mapped[int] = mapped_column(Integer, index=True)
    
    unlocked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    notified: Mapped[bool] = mapped_column(Boolean, default=False)  # Push notification sent?
```

### 7. TaskAnalytics Model (Sponsor Dashboard)
```python
class TaskAnalytics(Base):
    """Aggregated analytics per task for sponsor dashboard."""
    __tablename__ = "task_analytics"
    
    task_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    # Engagement metrics
    views: Mapped[int] = mapped_column(Integer, default=0)
    unique_viewers: Mapped[int] = mapped_column(Integer, default=0)
    started: Mapped[int] = mapped_column(Integer, default=0)
    submitted: Mapped[int] = mapped_column(Integer, default=0)
    approved: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    
    # Conversion rates
    view_to_start_rate: Mapped[float] = mapped_column(Float, default=0.0)  # (started / views) × 100
    start_to_submit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    submit_to_approve_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    # Performance
    avg_completion_time: Mapped[int] = mapped_column(Integer, default=0)  # seconds
    median_completion_time: Mapped[int] = mapped_column(Integer, default=0)
    
    # Demographics (JSON)
    gender_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"male": 60, "female": 40}
    
    age_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"18-24": 30, "25-34": 50, "35-44": 20}
    
    city_breakdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    # {"Lagos": 40, "Abuja": 30, "Port Harcourt": 20, "other": 10}
    
    # Hourly distribution (JSON array of 24 hours)
    hourly_submissions: Mapped[str | None] = mapped_column(Text, nullable=True)
    # [5, 3, 2, 1, 0, 0, 2, 10, 15, 20, ...] (24 values)
    
    # Quality
    avg_ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_auto_approve_count: Mapped[int] = mapped_column(Integer, default=0)
    manual_review_count: Mapped[int] = mapped_column(Integer, default=0)
    
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


### 8. FraudDetection Model (Extended from existing)
```python
class FraudDetection(Base):
    """Enhanced fraud tracking for task submissions."""
    __tablename__ = "fraud_detections"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    submission_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    
    # Detection type
    fraud_type: Mapped[str] = mapped_column(String(50), index=True)
    # Options: duplicate_screenshot, vpn_detected, velocity_violation,
    #          bot_behavior, device_farm, referral_ring, fake_proof
    
    severity: Mapped[str] = mapped_column(String(20))  # low, medium, high, critical
    confidence: Mapped[float] = mapped_column(Float)  # 0-100
    
    # Evidence
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    # {"duplicate_hash": "abc123", "original_submission_id": 456, "similarity_score": 0.98}
    
    # Status
    status: Mapped[str] = mapped_column(String(20), default="flagged")
    # Options: flagged, under_review, confirmed, false_positive, dismissed
    
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Admin
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Actions taken
    action_taken: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Options: none, warning_sent, submission_rejected, user_banned, points_deducted
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


### 9. Leaderboard Model (Cached Rankings)
```python
class Leaderboard(Base):
    """Cached leaderboard rankings - updated hourly by cron job."""
    __tablename__ = "leaderboards"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    
    leaderboard_type: Mapped[str] = mapped_column(String(50), index=True)
    # Options: top_earners_week, top_earners_month, fastest_workers,
    #          quality_workers, streak_leaders, level_leaders
    
    period: Mapped[str] = mapped_column(String(50), index=True)
    # Options: current_week, current_month, all_time
    
    rank: Mapped[int] = mapped_column(Integer, index=True)
    score: Mapped[float] = mapped_column(Float)  # Earnings, speed, quality score, etc.
    
    # Metadata for display
    username: Mapped[str] = mapped_column(String(255))
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

### 10. SponsorKYC Model
```python
class SponsorKYC(Base):
    """Sponsor KYC document storage - one row per sponsor."""
    __tablename__ = "sponsor_kyc"
    
    sponsor_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    
    # Business info
    business_name: Mapped[str] = mapped_column(String(255))
    business_registration_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    business_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Options: sole_proprietorship, partnership, limited_company, ngo, other
    
    business_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    business_social_media: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    
    # Identity documents (S3 URLs)
    id_document_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # NIN, Driver's License, Passport
    
    id_document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    id_document_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    business_document_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    # CAC certificate, business permit
    
    # Contact info
    contact_person_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_person_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    contact_person_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Review
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # Options: pending, approved, rejected, additional_info_required
    
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    submitted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # Admin ID
```

---

## Backend API Specification

### Base Router: `/api/v1/tasks`

#### **Worker Endpoints**

##### 1. List Available Tasks
```python
GET /api/v1/tasks
Query Params:
  - category: str (social_media, engagement, website, etc.)
  - platform: str (twitter, instagram, etc.)
  - min_reward: int (kobo)
  - max_reward: int (kobo)
  - sort: str (newest, highest_reward, quickest, popular)
  - page: int (default: 1)
  - limit: int (default: 20, max: 50)

Response: {
  "data": [
    {
      "id": 123,
      "title": "Follow @PagePayApp on Twitter",
      "description": "Follow our official Twitter account",
      "task_type": "twitter_follow",
      "platform": "twitter",
      "category": "social_media",
      "reward_amount": 3000,  // ₦30
      "time_estimate_minutes": 2,
      "completed_count": 45,
      "max_completions": 100,
      "spots_remaining": 55,
      "expires_at": "2025-02-01T23:59:59Z",
      "sponsor": {
        "business_name": "PagePay",
        "rating": 4.8,
        "verified": true
      }
    }
  ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 156,
    "total_pages": 8
  }
}

Auth: Required (JWT)
Permission: Worker role
```

##### 2. Get Task Detail
```python
GET /api/v1/tasks/{task_id}

Response: {
  "id": 123,
  "title": "Follow @PagePayApp on Twitter",
  "description": "Help us reach 10,000 followers...",
  "instructions": "1. Click the link below\n2. Follow @PagePayApp\n3. Take screenshot\n4. Upload here",
  "task_type": "twitter_follow",
  "platform": "twitter",
  "target_url": "@PagePayApp",
  "proof_type": "screenshot",
  "proof_instructions": "Upload screenshot showing you followed the account",
  "reward_amount": 3000,
  "time_estimate_minutes": 2,
  "time_limit_minutes": 60,
  "requirements": {
    "min_level": 1,
    "min_approval_rate": 0,
    "verified_only": false
  },
  "completed_count": 45,
  "max_completions": 100,
  "expires_at": "2025-02-01T23:59:59Z",
  "sponsor": {
    "business_name": "PagePay",
    "rating": 4.8,
    "verified": true,
    "total_tasks": 25
  },
  "user_can_complete": true,
  "user_already_completed": false
}

Auth: Required
Permission: Worker role
```

##### 3. Start Task
```python
POST /api/v1/tasks/{task_id}/start

Response: {
  "started_at": "2025-01-15T10:30:00Z",
  "expires_at": "2025-01-15T11:30:00Z",  // If time limit set
  "instructions": "...",
  "target_url": "@PagePayApp"
}

Auth: Required
Permission: Worker role
Validation:
  - User hasn't already completed this task
  - Task is active and not expired
  - User meets min level/approval rate requirements
  - Spots still available
```

##### 4. Submit Task Proof
```python
POST /api/v1/tasks/{task_id}/submit
Content-Type: multipart/form-data

Body:
  - proof_type: str (screenshot, link, text)
  - proof_url: str (optional - worker's Twitter handle, link, etc.)
  - proof_image: file (optional - screenshot upload)
  - proof_text: str (optional - written content)

Response: {
  "submission_id": 456,
  "status": "validating",  // AI is checking
  "message": "Your submission is being verified by our AI system. This usually takes 30 seconds.",
  "estimated_approval_time": "30 seconds"
}

Auth: Required
Permission: Worker role
Side Effects:
  - Upload proof_image to S3
  - Create TaskSubmission record
  - Trigger AI verification (async background task)
```

##### 5. Get My Task Submissions
```python
GET /api/v1/tasks/my-submissions
Query Params:
  - status: str (pending, approved, rejected, all)
  - page: int
  - limit: int

Response: {
  "data": [
    {
      "id": 456,
      "task": {
        "id": 123,
        "title": "Follow @PagePayApp on Twitter",
        "reward_amount": 3000
      },
      "status": "approved",
      "reward_paid": 3000,
      "submitted_at": "2025-01-15T10:35:00Z",
      "reviewed_at": "2025-01-15T10:35:30Z",
      "ai_verified": true,
      "auto_approved": true
    }
  ],
  "meta": { "page": 1, "total": 25 }
}

Auth: Required
Permission: Worker role
```

##### 6. Get My Task Stats
```python
GET /api/v1/tasks/my-stats

Response: {
  "worker_level": 5,
  "worker_xp": 2450,
  "xp_to_next_level": 550,
  "tasks_completed": 38,
  "tasks_approved": 35,
  "tasks_rejected": 3,
  "approval_rate": 92.1,
  "total_earnings": 125000,  // ₦1,250
  "current_streak_days": 7,
  "quality_score": 4.6,
  "badges": ["first_task", "speed_demon", "week_warrior"],
  "rank_this_week": 45  // Out of all workers
}

Auth: Required
Permission: Worker role
```

---

#### **Sponsor Endpoints**

##### 7. Register as Sponsor (KYC Submit)
```python
POST /api/v1/sponsors/register
Content-Type: multipart/form-data

Body:
  - business_name: str
  - business_registration_number: str (optional)
  - business_type: str (sole_proprietorship, limited_company, etc.)
  - business_address: str
  - business_website: str (optional)
  - id_document: file (NIN, passport, driver's license)
  - id_document_type: str
  - id_document_number: str
  - business_document: file (optional - CAC certificate)
  - contact_person_name: str
  - contact_person_phone: str

Response: {
  "status": "pending",
  "message": "Your KYC application has been submitted for review. You'll be notified within 24-48 hours.",
  "kyc_reference": "KYC-20250115-ABC123"
}

Auth: Required
Permission: Any authenticated user
Side Effects:
  - Upload documents to S3
  - Create SponsorKYC record
  - Update User.sponsor_kyc_status = "pending"
  - Notify admins for review
```

##### 8. Get Sponsor KYC Status
```python
GET /api/v1/sponsors/kyc-status

Response: {
  "status": "approved",  // none, pending, approved, rejected
  "submitted_at": "2025-01-15T09:00:00Z",
  "reviewed_at": "2025-01-15T12:00:00Z",
  "rejection_reason": null,
  "can_post_tasks": true
}

Auth: Required
Permission: Authenticated user
```

##### 9. Create Task
```python
POST /api/v1/tasks
Content-Type: application/json

Body: {
  "title": "Follow @PagePayApp on Twitter",
  "description": "Help us grow our Twitter community...",
  "instructions": "1. Click link\n2. Follow\n3. Screenshot",
  "task_type": "twitter_follow",
  "platform": "twitter",
  "category": "social_media",
  "target_url": "@PagePayApp",
  "proof_type": "screenshot",
  "proof_instructions": "Upload screenshot showing followed",
  "reward_amount": 3000,  // ₦30 in kobo
  "max_completions": 100,
  "expires_at": "2025-02-01T23:59:59Z",
  "time_limit_minutes": 60,
  "targeting": {
    "countries": ["Nigeria"],
    "cities": ["Lagos", "Abuja"],
    "gender": "any",
    "age_min": 18,
    "age_max": 45,
    "min_worker_level": 3,
    "min_approval_rate": 90,
    "require_verified": false
  },
  "ai_verification_enabled": true,
  "manual_review_required": false
}

Response: {
  "task_id": 789,
  "status": "draft",
  "escrow_amount": 345000,  // (3000 × 100) + 15% platform fee
  "platform_fee": 45000,
  "total_cost": 345000,
  "sponsor_wallet_balance": 500000,
  "sufficient_balance": true,
  "next_steps": "Review task details, then publish"
}

Auth: Required
Permission: Sponsor role, KYC approved
Validation:
  - Sponsor has sufficient wallet balance
  - reward_amount >= 1000 (₦10 minimum)
  - max_completions >= 1 and <= 10000
  - expires_at is future date
```

##### 10. Publish Task
```python
POST /api/v1/tasks/{task_id}/publish

Response: {
  "task_id": 789,
  "status": "active",
  "published_at": "2025-01-15T14:00:00Z",
  "escrow_locked": 345000,
  "sponsor_wallet_balance": 155000,  // After escrow deduction
  "message": "Task published! Workers can now start completing it."
}

Auth: Required
Permission: Sponsor role, task owner
Side Effects:
  - Deduct escrow from sponsor wallet
  - Create SponsorWalletTransaction (type: task_escrow)
  - Update Task.status = "active"
  - Send push notifications to eligible workers
```

##### 11. Get Sponsor Dashboard
```python
GET /api/v1/sponsors/dashboard

Response: {
  "sponsor_stats": {
    "wallet_balance": 155000,
    "tasks_active": 3,
    "tasks_completed": 12,
    "total_spent": 1250000,
    "total_submissions_pending": 8,
    "rating": 4.7,
    "approval_rate": 94.5
  },
  "active_tasks": [
    {
      "id": 789,
      "title": "Follow @PagePayApp on Twitter",
      "completed_count": 25,
      "max_completions": 100,
      "pending_review": 3,
      "approved": 20,
      "rejected": 2,
      "expires_at": "2025-02-01T23:59:59Z"
    }
  ],
  "recent_submissions": [
    {
      "id": 567,
      "task_title": "Follow @PagePayApp on Twitter",
      "worker_id": 234,
      "worker_username": "john_doe",
      "submitted_at": "2025-01-15T13:45:00Z",
      "status": "pending",
      "ai_confidence": 0.95,
      "requires_attention": false
    }
  ]
}

Auth: Required
Permission: Sponsor role
```

##### 12. Review Submission
```python
POST /api/v1/tasks/submissions/{submission_id}/review
Content-Type: application/json

Body: {
  "action": "approve",  // approve | reject
  "rejection_reason": null  // Required if reject
}

Response: {
  "submission_id": 567,
  "status": "approved",
  "reward_paid": 3000,
  "worker_notified": true,
  "message": "Submission approved. Worker has been credited ₦30."
}

Auth: Required
Permission: Sponsor role (task owner) or Admin
Side Effects:
  - If approve:
    - Credit worker points_balance
    - Release escrow
    - Update submission.status = "approved"
    - Send push notification to worker
  - If reject:
    - Update submission.status = "rejected"
    - Keep escrow (refund if task cancelled)
    - Send notification with reason
```

##### 13. Get Task Analytics
```python
GET /api/v1/tasks/{task_id}/analytics

Response: {
  "overview": {
    "views": 450,
    "started": 120,
    "submitted": 95,
    "approved": 85,
    "rejected": 10,
    "conversion_rate": {
      "view_to_start": 26.7,
      "start_to_submit": 79.2,
      "submit_to_approve": 89.5
    }
  },
  "demographics": {
    "gender": {"male": 65, "female": 35},
    "age": {"18-24": 45, "25-34": 40, "35-44": 15},
    "cities": {"Lagos": 50, "Abuja": 30, "Other": 20}
  },
  "performance": {
    "avg_completion_time": 180,  // seconds
    "median_completion_time": 150,
    "fastest_completion": 45
  },
  "hourly_distribution": [2, 1, 0, 0, 0, 1, 5, 12, 18, 25, ...],  // 24 values
  "ai_stats": {
    "auto_approved": 75,
    "manual_reviewed": 10,
    "avg_confidence": 0.94
  }
}

Auth: Required
Permission: Sponsor role (task owner) or Admin
```

##### 14. Fund Sponsor Wallet
```python
POST /api/v1/sponsors/wallet/fund
Content-Type: application/json

Body: {
  "amount": 50000,  // ₦500 in kobo
  "payment_method": "paystack"
}

Response: {
  "payment_url": "https://checkout.paystack.com/xyz123",
  "reference": "PAGEPAY-SPONSOR-20250115-ABC",
  "amount": 50000,
  "expires_at": "2025-01-15T15:00:00Z"
}

Auth: Required
Permission: Sponsor role
Side Effects:
  - Create Paystack payment intent
  - Return checkout URL
  - Webhook will credit wallet on success
```
