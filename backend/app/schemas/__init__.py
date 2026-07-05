from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal


class UserRegister(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str = Field(min_length=8)
    referral_code: str | None = Field(default=None, max_length=12, description="6-char referral code from inviter")


class UserLogin(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserMe(BaseModel):
    id: int
    email: str | None
    phone: str | None
    points_balance: int
    tier: str
    created_at: datetime
    is_worker: bool = True
    is_sponsor: bool = False
    
    model_config = {"from_attributes": True}


# ══════════════════════════════════════════════════════════════════════
# PHASE 8: BILLS & EARN (VTU)
# ══════════════════════════════════════════════════════════════════════


class AirtimePurchaseRequest(BaseModel):
    """POST /bills/airtime - Buy airtime and earn points."""
    phone: str = Field(min_length=10, max_length=15)
    network: str = Field(..., description="mtn, airtel, glo")
    amount_naira: int = Field(ge=50, le=50000)


class DataPurchaseRequest(BaseModel):
    """POST /bills/data - Buy data bundle and earn points."""
    phone: str = Field(min_length=10, max_length=15)
    network: str = Field(..., description="Data network identifier: mtn_data_share, mtn_gifting_data, glo_data, airtel_data, 9mobile_data, 9mobile_gifting")
    plan_code: str = Field(..., description="Data plan code from Peyflex (e.g. M1GBS)")


class AirtimePurchaseResponse(BaseModel):
    """Response after a successful airtime purchase."""
    reference: str
    phone: str
    amount_naira: int
    network: str
    commission_naira: int
    points_earned: int
    new_balance: int
    status: str


class ElectricityPurchaseRequest(BaseModel):
    """POST /bills/electricity - Buy electricity tokens."""
    meter_number: str = Field(min_length=6, max_length=30)
    plan_id: str = Field(..., description="Peyflex plan_id: ikeja-electric, abuja-electric, etc.")
    meter_type: str = Field(default="prepaid", pattern="^(prepaid|postpaid)$")
    amount_naira: int = Field(ge=500, le=100000)
    phone: str = Field(min_length=10, max_length=15)


class TelevisionPurchaseRequest(BaseModel):
    """POST /bills/tv - Subscribe cable TV."""
    smartcard_number: str = Field(min_length=8, max_length=30)
    provider: str = Field(..., description="dstv, gotv, startimes")
    plan_code: str = Field(..., description="Bouquet plan code from Peyflex")
    phone: str = Field(min_length=10, max_length=15)


class BillsPurchaseResponse(BaseModel):
    """Generic response for bills purchases."""
    reference: str
    commission_naira: int
    points_earned: int
    new_balance: int
    status: str
    # Service-specific fields
    phone: str | None = None
    meter_number: str | None = None
    smartcard_number: str | None = None
    customer_name: str | None = None
    token: str | None = None
    units: str | None = None


class ContentItem(BaseModel):
    id: int
    title: str
    content_type: str
    category: str
    author: str | None
    estimated_read_minutes: int
    is_sponsored: bool


class ContentDetail(BaseModel):
    id: int
    title: str
    content_type: str
    category: str
    author: str | None
    body_text: str | None
    estimated_read_minutes: int
    is_sponsored: bool
    # Set on child slices — the id of the parent work. Lets the reader
    # navigate back to /book/[parent_work_id] after finishing. None for
    # standalone slices (no parent work).
    parent_work_id: int | None = None


class SessionStart(BaseModel):
    content_id: int


class SessionHeartbeat(BaseModel):
    session_id: int
    scroll_events: int = Field(ge=0)
    app_state: Literal["active", "background"] = "active"


class SessionEnd(BaseModel):
    session_id: int


class SessionEndResponse(BaseModel):
    """Return shape of POST /session/end.

    With the reward gate in place, ending a session does NOT credit points
    directly. The client must call POST /session/claim after the user has
    watched the post-read ad. Until then, `pending_points` is staged on the
    session row and `requires_claim=True` signals the client to surface the
    claim modal.
    """
    requires_claim: bool
    pending_points: int  # 0 if the session wasn't eligible (no scroll, too short)
    session_id: int
    verified: bool  # true if scroll_events > 0 (anti-cheat passed)


class SessionClaimResponse(BaseModel):
    """Return shape of POST /session/claim.

    Idempotent: re-claiming a session that was already claimed returns the
    same `points_earned` and the wallet balance as it stood after the first
    claim. Callers can safely retry on network failure.
    """
    points_earned: int
    new_balance: int
    already_claimed: bool


class ContinueReading(BaseModel):
    """Returned by GET /progress/continue — the slice the user should read next."""
    slice_id: int | None
    work_id: int | None
    work_title: str | None
    slice_title: str | None
    slice_order: int
    total_slices: int
    percent_complete: int  # 0-100
    has_in_progress: bool  # False if user has no in-progress work — client should show fresh content
    scroll_offset_px: int  # where within the slice body to resume (0 if first open)


class WorkProgress(BaseModel):
    work_id: int
    work_title: str
    slice_title: str
    slice_order: int
    total_slices: int
    slices_completed: int
    percent_complete: int
    is_finished: bool
    last_read_at: datetime | None


class SliceSummary(BaseModel):
    """One slice of a work. Used by the book detail screen.

    Does NOT include `body_text` — that's only fetched by the reader. This
    keeps the book detail page cheap (a 30-slice work shouldn't ship the
    full text of every slice on every load).
    """
    id: int
    title: str
    read_order: int
    total_slices: int
    estimated_read_minutes: int


class BookDetail(BaseModel):
    """Parent work plus its slice list. Powering the locked-slice detail
    screen. `slices` comes in ascending `read_order` so the screen can
    just render them top-to-bottom with index-based lock states.

    `is_sliced` distinguishes "this work has children" from "this is a
    standalone article." For standalone works, `slices` has one entry
    (the work itself, read_order=1 of 1) and the locked-slices UI is moot.
    """
    id: int
    title: str
    author: str | None
    category: str
    estimated_read_minutes: int
    content_type: str
    is_sliced: bool
    slices: list[SliceSummary] = []


class ResumeState(BaseModel):
    """The user's progress against a specific work. Returned alongside a
    BookDetail so the detail screen knows which slice is the user's
    current one (the unlock frontier) vs the slices they still have to
    earn their way through.
    """
    work_id: int
    current_slice_id: int | None
    slices_completed: int
    total_slices: int
    percent_complete: int
    is_finished: bool


class BookmarkSave(BaseModel):
    slice_id: int
    scroll_offset_px: int = Field(ge=0)


# ── Ad reward schemas ────────────────────────────────────────────────
# Every rewarded ad (pre-read gate, post-read gate, future bonus gates)
# flows through POST /api/v1/ads/credit. The client passes what the ad
# SDK reported for this single impression (USD); the server does the
# conversion math (USD → NGN at the live FX rate, 20% platform cut, 100
# pts = ₦1) and credits the wallet atomically. `transaction_id` is the
# SSV-style dedupe key — replaying the same callback never double-credits.


class AdCreditRequest(BaseModel):
    ad_unit: str = Field(min_length=1, max_length=100)
    provider: Literal["admob", "applovin_max", "mock"]
    # USD revenue for this single impression, as reported by the ad SDK's
    # revenue callback (AdMob `onAdPaid`, AppLovin postback, etc.).
    # Stored as a float — micro-cent precision is preserved by scaling to
    # micros below the wire.
    revenue_usd: float = Field(ge=0)
    # SSV-style transaction id. Unique per impression. Replays are no-ops.
    transaction_id: str = Field(min_length=1, max_length=255)


class AdCreditResponse(BaseModel):
    points_credited: int
    new_balance: int
    fx_rate_used: float
    user_share_ngn: float
    credit_status: Literal["credited", "rejected_low_value", "duplicate"]


# ── Phase 2: impression + reward-claim ──────────────────────────────
# Split the legacy single-call "ad watched → credit" into two
# steps: impression (logged at load time, no credit) and
# reward-claim (logged at SDK revenue callback time, credits the
# wallet). The split lets analytics answer "how many ads were
# shown vs watched" and lets the SSV webhook (which fires
# server-side, no client roundtrip) tie back to the same
# AdEvent row.


class AdImpressionRequest(BaseModel):
    """POST /ads/impression body.

    The client calls this the moment an ad slot finishes loading
    (the SDK's `onAdLoaded` / equivalent). At this point we don't
    have a `transaction_id` or `revenue_usd` — those arrive later
    via the SDK's revenue callback. We just want a load-time row so
    the reward-claim can link back via `ad_event_id`.
    """
    ad_type: Literal["banner", "native", "interstitial", "rewarded"]
    provider: Literal["admob", "applovin_max", "mock"]
    ad_unit: str = Field(min_length=1, max_length=100)
    # The active reading session id, if any. Stored so the wallet
    # transaction list can group ad revenue with the read that
    # triggered it. Optional because banner ads fire on screens
    # without an open session (e.g. the catalog tab).
    session_id: int | None = None


class AdImpressionResponse(BaseModel):
    """Returned by POST /ads/impression.

    `ad_event_id` is the link the client sends to /ads/reward-claim
    to upgrade this load-time row to "watched" + credited. We do
    not return the AdEvent row itself — the client only needs the
    id, and the rest is server-side audit data.
    """
    ad_event_id: int


class AdRewardClaimRequest(BaseModel):
    """POST /ads/reward-claim body.

    Called when the SDK's revenue callback fires (AdMob `onAdPaid`,
    AppLovin postback). The client passes the same `transaction_id`
    the SDK reported, plus the USD revenue amount. We credit the
    wallet using the same 80/20 share as the legacy /ads/credit
    path and link back to the impression row via `ad_event_id` if
    one was logged.
    """
    ad_event_id: int | None = None
    ad_type: Literal["banner", "native", "interstitial", "rewarded"]
    provider: Literal["admob", "applovin_max", "mock"]
    ad_unit: str = Field(min_length=1, max_length=100)
    revenue_usd: float = Field(ge=0)
    # SSV-style transaction id. Unique per impression. Replays are
    # no-ops. Same contract as the legacy /ads/credit endpoint.
    transaction_id: str = Field(min_length=1, max_length=255)


class AdRewardClaimResponse(BaseModel):
    """Returned by POST /ads/reward-claim.

    Mirrors the legacy /ads/credit response shape so the client's
    existing "credit succeeded" branch works without a code
    change. `ad_event_id` is the load-time row this credit is
    linked to (the same id the client sent in the request, or a
    fresh one if the claim arrived without an impression log).
    """
    ad_event_id: int
    points_credited: int
    new_balance: int
    fx_rate_used: float
    user_share_ngn: float
    credit_status: Literal["credited", "rejected_low_value", "duplicate"]


class AdSsvCallbackRequest(BaseModel):
    """Internal Pydantic shape for the AdMob SSV webhook body.

    The actual on-the-wire body is parsed in the handler (AdMob
    sometimes sends form-urlencoded, sometimes JSON). This schema
    is what the parsed payload must conform to before we proceed
    with the credit math. `custom_data` is the dict the client
    SDK attached to the reward event before forwarding to AdMob
    — it carries `user_id` and any other routing we need.
    """
    transaction_id: str = Field(min_length=1, max_length=255)
    ad_unit_id: str = Field(min_length=1, max_length=255)
    # AdMob's reward field is a float; in newer versions it's
    # renamed to `revenue_amount`. The handler reads both.
    reward_amount: float = Field(ge=0)
    custom_data: dict = Field(default_factory=dict)


# ── Profile / Settings schemas ───────────────────────────────────────
# Powers the v1 Profile tab and the payouts placeholder (Paystack
# integration lands in Phase 4 — Payments).


class ChangePasswordRequest(BaseModel):
    """POST /auth/change-password body.

    Requires the user to prove they own the account by supplying the
    current password. The new password is hashed before persistence
    via the same path used at registration (bcrypt, 72-byte limit).
    """
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)


class PayoutAccountLink(BaseModel):
    """PUT /payouts/account body.

    The user links (or replaces) their payout bank account. v1 stores
    the input as given and returns `verified=False`; Phase 4 (Payments)
    will call Paystack's `/transferrecipient/create` to populate
    `recipient_code` and flip `verified` to True once the account
    name resolves.
    """
    bank_code: str = Field(min_length=3, max_length=10)
    bank_name: str = Field(min_length=1, max_length=120)
    # Nigerian NUBAN — always 10 digits. We validate the length on the
    # wire; digit-only enforcement is a client-side affordance.
    account_number: str = Field(min_length=10, max_length=10)
    # Resolved from Paystack in Phase 4. v1 stores the input verbatim
    # (often None) and the row defaults to "Pending validation" until
    # the user re-saves after Paystack is wired.
    account_name: str | None = None


class PayoutAccount(BaseModel):
    """Linked payout account, response shape.

    `account_number_last4` instead of the full number — we never echo
    the full account number back over the wire after the user has
    saved it. The full number lives in the DB (encrypted-at-rest is
    Phase 4) but never leaves the server in this response.

    `recipient_code` is the Paystack transfer-recipient id we cache
    at link time. It's used by the withdraw endpoint to send the
    actual transfer; the client doesn't need to display it.
    """
    bank_code: str
    bank_name: str
    account_number_last4: str
    account_name: str | None
    verified: bool
    linked_at: datetime
    recipient_code: str | None = None

    model_config = {"from_attributes": True}


class AccountResolveRequest(BaseModel):
    bank_code: str = Field(min_length=3, max_length=10)
    account_number: str = Field(min_length=10, max_length=10)


class AccountResolveResponse(BaseModel):
    account_number: str
    account_name: str | None
    verified: bool


# ── Phase 4 — Banks, Withdrawals ─────────────────────────────────────
# Wired once `PAYSTACK_SECRET_KEY` is set in the backend env. The
# payouts router hits Paystack's `/bank`, `/bank/resolve`,
# `/transferrecipient`, and `/transfer` endpoints through
# `app/services/paystack.py`.


class Bank(BaseModel):
    """One Nigerian bank. Returned by GET /payouts/banks.

    Mirrors Paystack's bank object: `code` is the CBN code (the value
    we send to `/bank/resolve` and `/transferrecipient`), `name` is
    the canonical bank name. We drop Paystack's `slug`, `longcode`,
    and `gateway` fields — they aren't needed for the link flow.
    """
    code: str
    name: str


class WithdrawalRequest(BaseModel):
    """POST /payouts/withdraw body.

    Amount is in KOBO (₦1 = 100 kobo). The user pays the withdrawal fee
    in addition to this amount (see `fee_kobo` in the response). The
    wallet is debited `amount_kobo + fee_kobo`; the user receives the
    full `amount_kobo` via Paystack.

    `ge=100000` enforces a ₦1,000 minimum. Below that, the flat fee
    becomes a punishing percentage of the withdrawal. The exact floor
    comes from `settings.min_withdrawal_kobo`; the Pydantic bound
    here is a hard backstop so the API can never accept a sub-floor
    amount even if the env is misconfigured.
    """
    amount_kobo: int = Field(ge=100000)
    reason: str | None = Field(default=None, max_length=100)


class WithdrawalResponse(BaseModel):
    transfer_reference: str
    status: Literal["pending", "success", "failed"]
    new_balance_points: int
    fee_kobo: int
    amount_kobo: int


# ── Phase 3: Study / AI Exam Prep ────────────────────────────────────


class SowUploadRequest(BaseModel):
    text: str = Field(min_length=10, description="SOW or syllabus text to parse")


class SowUploadResponse(BaseModel):
    material_id: int
    title: str
    parsed_structure: dict | None = None


class MaterialSummary(BaseModel):
    id: int
    title: str
    asset_types: list[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class MaterialDetail(BaseModel):
    id: int
    title: str
    parsed_structure: dict | None
    assets: list[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class GenerateAssetRequest(BaseModel):
    material_id: int
    asset_type: Literal["mcq", "flashcard", "essay"] = "mcq"
    count: int = Field(default=5, ge=1, le=20)


class GenerateAssetResponse(BaseModel):
    assets: list[dict]


class ChatRequest(BaseModel):
    material_id: int
    message: str = Field(min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    response: str
    provider: str
    model: str


class UnlockRequest(BaseModel):
    asset_id: int
    method: Literal["points", "ad"] = "points"


class UnlockResponse(BaseModel):
    unlocked: bool
    content: dict | None = None
    new_balance: int
    method: str
    points_spent: int = 0


class StudyTransaction(BaseModel):
    id: int
    asset_id: int | None
    method: str
    points_spent: int
    reward_granted: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class QuizCompleteRequest(BaseModel):
    asset_id: int
    score: int = Field(ge=0, le=100, description="Percentage score 0-100")


class QuizCompleteResponse(BaseModel):
    bonus_awarded: bool
    bonus_points: int
    new_balance: int
    message: str


# ── Phase 3: AI Route Endpoint ───────────────────────────────────────


class AiRouteRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    task_type: Literal["heavy", "fast", "chat"] = "fast"
    max_tokens: int = Field(default=4000, ge=1, le=32000)


class AiRouteResponse(BaseModel):
    response: str
    provider: str
    model: str

# ── Phase 4: Payments (Premium Subscription) ─────────────────────────────


class PaymentInitiateRequest(BaseModel):
    """POST /api/v1/payments/initiate body.
    
    User selects a tier and initiates checkout. Backend returns
    the payment provider's checkout URL.
    """
    tier: Literal["premium_monthly", "premium_yearly"] = "premium_monthly"
    provider: Literal["paystack", "flutterwave"] = "paystack"


class PaymentInitiateResponse(BaseModel):
    """Checkout response with provider-specific URL."""
    payment_url: str
    provider_tx_ref: str
    provider: str
    amount_kobo: int
    tier: str


class PaymentWebhookRequest(BaseModel):
    """Paystack webhook body shape (loose — actual schema varies by event)."""
    event: str
    data: dict


class PaymentWebhookResponse(BaseModel):
    status: str
    message: str


class TierInfo(BaseModel):
    """Public tier pricing info (OTA-configurable via admin)."""
    tier: str
    display_name: str
    price_kobo: int
    duration_days: int
    benefits: list[str]


class UserTierInfo(BaseModel):
    """User's current tier + expiry."""
    current_tier: str
    subscription_expires_at: datetime | None
    is_premium: bool
    days_remaining: int | None

    model_config = {"from_attributes": True}


# ── Phase 5: Referrals & Community ───────────────────────────────────


class ReferralGenerateResponse(BaseModel):
    code: str
    link: str


class ReferralStats(BaseModel):
    code: str
    clicks: int
    signups: int
    pending_rewards: int
    claimed_rewards: int


class ReferralValidateResponse(BaseModel):
    rewarded: bool
    referrer_points: int
    referee_points: int
    message: str


class CommunityNoteCreate(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    content: str = Field(min_length=10)
    course_code: str | None = None
    university: str | None = None


class CommunityNoteOut(BaseModel):
    id: int
    user_id: int
    title: str
    content: str
    course_code: str | None
    university: str | None
    status: str
    likes_count: int
    created_at: datetime
    author_name: str | None = None

    model_config = {"from_attributes": True}


class CommunityFeedItem(BaseModel):
    id: int
    title: str
    content: str
    course_code: str | None
    university: str | None
    likes_count: int
    created_at: datetime
    author_name: str | None = None
    is_liked: bool = False


class StreakResponse(BaseModel):
    current_streak: int
    longest_streak: int
    last_activity_date: str | None
    bonus_multiplier: float
    bonus_label: str


class DailyActiveUsers(BaseModel):
    date: str
    count: int


class RetentionCohort(BaseModel):
    signup_date: str
    day_1: int
    day_7: int


class ContentPerformanceItem(BaseModel):
    content_id: int
    title: str
    reading_sessions: int


# ── Admin System ─────────────────────────────────────────────────────


class AdminLoginRequest(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=6)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    permissions: list[str]


class AdminUserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime
    permissions: list[str] = []

    model_config = {"from_attributes": True}


class AdminUserCreate(BaseModel):
    email: str = Field(min_length=3)
    password: str = Field(min_length=8)
    role: str = Field(default="support", pattern="^(super_admin|finance|moderator|support)$")
    permissions: list[str] | None = None


class AdminAuditLogOut(BaseModel):
    id: int
    admin_email: str | None
    action: str
    target_type: str
    target_id: int | None
    changes: str | None
    ip_address: str | None
    result: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FraudFlagOut(BaseModel):
    id: int
    user_id: int | None
    session_id: int | None
    flag_type: str
    severity: str
    details: str
    status: str
    reviewed_by: int | None
    review_notes: str | None
    created_at: datetime
    reviewed_at: datetime | None

    model_config = {"from_attributes": True}


class ContentImportLogOut(BaseModel):
    id: int
    source: str
    admin_id: int | None
    count_imported: int
    start_page: int | None
    limit: int | None
    status: str
    error_message: str | None
    duration_seconds: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_users: int
    active_users_today: int
    # Ad Revenue breakdown
    ad_revenue_usd: float  # Total ad revenue in USD
    ad_revenue_ngn: int  # Total ad revenue in kobo (using historical FX rates)
    ad_platform_share_usd: float  # 20% platform share in USD
    ad_platform_share_ngn: int  # 20% platform share in kobo
    ad_user_share_usd: float  # 80% user share in USD
    ad_user_share_ngn: int  # 80% user share in kobo
    # Premium Revenue
    premium_revenue_ngn: int  # Premium subscriptions in kobo
    premium_revenue_usd: float  # Premium converted to USD (current FX)
    # Combined totals
    total_revenue_usd: float  # Ad + Premium in USD
    total_revenue_ngn: int  # Ad + Premium in kobo
    platform_earnings_ngn: int  # Ad platform share + Premium in kobo
    user_earnings_ngn: int  # Ad user share in kobo (matches points/100)
    total_points_distributed: int  # Sum of all user_points_credited
    # Other stats
    pending_payouts: int
    pending_notes: int
    high_severity_fraud_flags: int


class RevenueSummary(BaseModel):
    # Ad Revenue breakdown
    ad_revenue_usd: float  # Total ad revenue in USD
    ad_revenue_ngn: int  # Total ad revenue in kobo (using historical FX rates)
    ad_platform_share_usd: float  # 20% platform share in USD
    ad_platform_share_ngn: int  # 20% platform share in kobo
    ad_user_share_usd: float  # 80% user share in USD
    ad_user_share_ngn: int  # 80% user share in kobo
    # Premium Revenue
    premium_revenue_ngn: int  # Premium subscriptions in kobo
    premium_revenue_usd: float  # Premium converted to USD (current FX)
    # Combined totals
    total_revenue_usd: float  # Ad + Premium in USD
    total_revenue_ngn: int  # Ad + Premium in kobo
    platform_earnings_ngn: int  # Ad platform share + Premium in kobo
    user_earnings_ngn: int  # Ad user share in kobo
    total_points_distributed: int  # Sum of all user_points_credited
    average_fx_rate: float  # Average FX rate used during period
    current_fx_rate: float  # Current FX rate for reference
    # Period
    period_start: str
    period_end: str


class ConfigItem(BaseModel):
    key: str
    value: str
    environment: str
    description: str | None
    updated_at: datetime | None


class ConfigUpdateRequest(BaseModel):
    value: str
    description: str | None = None


class UserListResponse(BaseModel):
    items: list[dict]
    total: int
    page: int
    limit: int



# ══════════════════════════════════════════════════════════════════════
# PHASE 7: SOCIAL TASKS MARKETPLACE
# ══════════════════════════════════════════════════════════════════════


class SponsorRegisterRequest(BaseModel):
    """POST /sponsor/register - Sponsor registration.
    
    Anyone can be a sponsor - individuals, influencers, businesses, brands.
    Business information is completely optional.
    """
    email: EmailStr
    phone: str | None = None
    password: str = Field(min_length=8)
    display_name: str = Field(min_length=2, max_length=255, description="Your name or brand name")
    business_name: str | None = Field(default=None, max_length=255, description="Optional: Company name if representing a business")
    business_registration_number: str | None = None


class SponsorKYCSubmitRequest(BaseModel):
    """PUT /sponsor/kyc - Submit KYC documents.
    
    Simplified KYC for individuals and businesses. Only ID is required.
    Business documents are optional for companies.
    """
    # Personal/Individual info
    full_name: str = Field(min_length=2, max_length=255)
    id_document_type: Literal["nin", "drivers_license", "passport", "voters_card"] = "nin"
    id_document_number: str = Field(min_length=5, max_length=100)
    phone_number: str = Field(min_length=10, max_length=20)
    id_document_base64: str | None = None
    business_document_base64: str | None = None
    
    # Optional business info (only if sponsor is a company)
    business_type: Literal["individual", "sole_proprietorship", "partnership", "limited_company", "ngo", "other"] | None = "individual"
    business_address: str | None = None
    business_website: str | None = None


class SponsorKYCResponse(BaseModel):
    """Sponsor KYC status response."""
    status: Literal["none", "pending", "approved", "rejected"]
    submitted_at: datetime | None
    reviewed_at: datetime | None
    rejection_reason: str | None = None
    
    model_config = {"from_attributes": True}


class SponsorWalletDepositRequest(BaseModel):
    """POST /sponsor/wallet/deposit - Initiate Paystack deposit."""
    amount_kobo: int = Field(ge=500000, description="Minimum ₦5,000")


class SponsorWalletDepositResponse(BaseModel):
    """Paystack checkout URL response."""
    payment_url: str
    reference: str
    amount_kobo: int


class TaskCreateRequest(BaseModel):
    """POST /sponsor/tasks - Create new task (draft)."""
    title: str = Field(min_length=5, max_length=255)
    description: str = Field(min_length=20)
    instructions: str = Field(min_length=20)
    task_type: Literal[
        "twitter_follow", "instagram_follow", "tiktok_follow", "youtube_subscribe",
        "twitter_like", "instagram_like", "twitter_retweet", "instagram_comment",
        "website_visit", "website_signup", "app_download", "app_review",
        "photo_upload", "video_upload", "written_review", "survey", "custom"
    ]
    platform: Literal["twitter", "instagram", "tiktok", "youtube", "facebook", "linkedin", "web", "android", "ios", "custom"]
    category: Literal["social_media", "engagement", "website", "app", "content_creation", "surveys", "data_collection", "other"] = "social_media"
    target_url: str | None = None
    proof_type: Literal["screenshot", "link", "text", "photo", "video", "none"]
    proof_instructions: str | None = None
    reward_amount_kobo: int = Field(ge=5000, le=5000000, description="₦50 - ₦50,000 in kobo")
    max_completions: int = Field(ge=1, le=10000)
    expires_in_days: int = Field(default=7, ge=1, le=365, description="Days from now until task expires")
    time_limit_minutes: int | None = Field(default=None, ge=5, le=1440)
    target_countries: list[str] | None = None
    target_cities: list[str] | None = None
    target_gender: Literal["male", "female", "any"] | None = "any"
    target_age_min: int | None = Field(default=None, ge=13, le=100)
    target_age_max: int | None = Field(default=None, ge=13, le=100)
    min_worker_level: int = Field(default=1, ge=1, le=50)
    min_approval_rate: float = Field(default=0.0, ge=0, le=100)


class TaskResponse(BaseModel):
    """Task detail response."""
    id: int
    sponsor_id: int
    title: str
    description: str
    instructions: str
    task_type: str
    platform: str
    category: str
    target_url: str | None
    proof_type: str
    proof_instructions: str | None
    reward_amount: int
    max_completions: int
    completed_count: int
    approved_count: int
    rejected_count: int
    pending_count: int
    total_escrowed: int
    platform_fee_amount: int
    status: str
    expires_at: datetime
    time_limit_minutes: int | None
    min_worker_level: int
    min_approval_rate: float
    created_at: datetime
    published_at: datetime | None
    
    model_config = {"from_attributes": True}


class TaskListItem(BaseModel):
    """Shortened task for list views."""
    id: int
    title: str
    task_type: str
    platform: str
    reward_amount: int
    max_completions: int
    completed_count: int
    expires_at: datetime
    sponsor_business_name: str | None
    time_estimate_minutes: int
    
    model_config = {"from_attributes": True}


class TaskPublishRequest(BaseModel):
    """POST /sponsor/tasks/{id}/publish - Lock escrow and make task live."""
    confirm_escrow: bool = Field(default=True, description="Acknowledge funds will be locked")


class TaskSubmitRequest(BaseModel):
    """POST /tasks/{id}/submit - Worker submits proof."""
    proof_url: str | None = None
    proof_text: str | None = None


class TaskSubmissionResponse(BaseModel):
    """Submission detail response."""
    id: int
    task_id: int
    worker_id: int
    task_title: str
    task_type: str
    platform: str
    reward_amount: int
    proof_type: str
    proof_image_url: str | None
    proof_url: str | None
    proof_text: str | None
    status: Literal["validating", "pending", "approved", "rejected"]
    ai_verified: bool
    ai_confidence: float | None
    verified_at: datetime | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    reward_paid: int
    submitted_at: datetime
    completion_time_seconds: int | None
    
    model_config = {"from_attributes": True}


class WorkerStatsResponse(BaseModel):
    """GET /tasks/my-stats - Worker reputation stats."""
    user_id: int
    worker_level: int
    worker_xp: int
    xp_to_next_level: int
    tasks_completed: int
    tasks_approved: int
    tasks_rejected: int
    approval_rate: float
    total_earned: int
    current_streak: int
    longest_streak: int
    badges: list[str]
    created_at: datetime
    updated_at: datetime
    
    model_config = {"from_attributes": True}


class LeaderboardEntry(BaseModel):
    """One entry in leaderboard."""
    rank: int
    user_id: int
    username: str
    level: int
    score: float
    avatar_url: str | None = None
    
    model_config = {"from_attributes": True}


class LeaderboardResponse(BaseModel):
    """GET /tasks/leaderboard response."""
    entries: list[LeaderboardEntry]
    my_rank: LeaderboardEntry | None
    leaderboard_type: str
    period: str


class TaskMessageResponse(BaseModel):
    """Task message/chat response."""
    id: int
    task_id: int
    submission_id: int | None
    sender_id: int
    receiver_id: int
    message: str
    attachment_url: str | None
    attachment_type: str | None
    read_at: datetime | None
    created_at: datetime
    
    model_config = {"from_attributes": True}


class AchievementResponse(BaseModel):
    """Achievement detail."""
    id: int
    slug: str
    name: str
    description: str
    icon_emoji: str | None
    xp_reward: int
    points_reward: int
    rarity: str
    unlocked: bool
    unlocked_at: datetime | None
    
    model_config = {"from_attributes": True}


class UserAchievementResponse(BaseModel):
    """User achievement record."""
    id: int
    achievement: AchievementResponse
    unlocked_at: datetime
    
    model_config = {"from_attributes": True}


class ForgotPasswordRequest(BaseModel):
    """Request a password reset token."""
    email: str | None = None
    phone: str | None = None


class ResetPasswordRequest(BaseModel):
    """Reset password with a token."""
    token: str
    new_password: str = Field(min_length=8)


class LegalPageResponse(BaseModel):
    """Static legal page content."""
    slug: str
    title: str
    content: str
    updated_at: datetime
