from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Literal


class UserRegister(BaseModel):
    email: EmailStr | None = None
    phone: str | None = None
    password: str = Field(min_length=8)


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

    model_config = {"from_attributes": True}


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
    """Returned by POST /payouts/withdraw.

    `transfer_reference` is the UUID we passed as `reference` to
    Paystack. We persist it on the `payout_transactions` row so the
    webhook handler can join on it when Paystack reports settlement.
    `new_balance_points` reflects the wallet AFTER the debit (which
    includes the fee, not just the withdrawal amount).

    `fee_kobo` is the flat fee the user paid for this withdrawal,
    computed from `settings.withdrawal_fee_tiers`. `amount_kobo +
    fee_kobo` is the total debit; the user receives the full
    `amount_kobo` via Paystack.
    """
    transfer_reference: str
    status: Literal["pending", "success", "failed"]
    new_balance_points: int
    fee_kobo: int
    amount_kobo: int
