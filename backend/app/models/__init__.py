from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, BigInteger, Boolean, Text, DateTime, Enum
from datetime import datetime
import enum


class Base(DeclarativeBase):
    pass


class UserTier(enum.Enum):
    FREE = "free"
    PREMIUM_MONTHLY = "premium_monthly"
    PREMIUM_YEARLY = "premium_yearly"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    points_balance: Mapped[int] = mapped_column(BigInteger, default=0)
    tier: Mapped[UserTier] = mapped_column(Enum(UserTier), default=UserTier.FREE)
    referral_code: Mapped[str | None] = mapped_column(String(12), unique=True)
    referred_by: Mapped[str | None] = mapped_column(String(12), index=True)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ReadingSession(Base):
    __tablename__ = "reading_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    content_id: Mapped[int] = mapped_column(BigInteger, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    points_earned: Mapped[int] = mapped_column(BigInteger, default=0)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    scroll_events: Mapped[int] = mapped_column(BigInteger, default=0)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    total_paused_seconds: Mapped[int] = mapped_column(BigInteger, default=0)
    # Reward-gate fields. `pending_points` is what the user *would* earn if
    # they complete the post-read ad claim. `points_earned` only becomes >0
    # after a successful POST /session/claim (which also stamps `claimed_at`).
    # This keeps the no-claim case from leaking free points into the wallet.
    pending_points: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ContentCatalog(Base):
    __tablename__ = "content_catalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(50))
    category: Mapped[str] = mapped_column(String(100), index=True)
    source_url: Mapped[str | None] = mapped_column(String(500), unique=True)
    body_text: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(255))
    cover_image_url: Mapped[str | None] = mapped_column(String(500))
    estimated_read_minutes: Mapped[int] = mapped_column(Integer, default=5)
    is_sponsored: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Short-read slicing. Each book/article is one "parent work" and many
    # slices of ~2-minute reads. parent_work_id is the id of the original
    # full-content row (when present); read_order is the 1-indexed slice
    # number within the work. A standalone slice (no parent) has both NULL.
    # word_count and char_count enable the client to size banners / track
    # scroll-distance targets without re-measuring the body.
    parent_work_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)
    read_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_slices: Mapped[int | None] = mapped_column(Integer, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class AdEvent(Base):
    __tablename__ = "ad_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    session_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    ad_type: Mapped[str] = mapped_column(String(50))
    ad_unit: Mapped[str] = mapped_column(String(100))
    provider: Mapped[str] = mapped_column(String(50))
    impression_revenue_usd: Mapped[float | None] = mapped_column(BigInteger, nullable=True)
    watched_fully: Mapped[bool] = mapped_column(Boolean, default=False)
    reward_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    transaction_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # ── Per-impression reward math fields ───────────────────────────────
    # `revenue_usd` is what the network reported for this single impression
    # (AdMob's onAdPaid callback, AppLovin's postback, etc.). Distinct from
    # `impression_revenue_usd` (BigInteger, micro-USD) which is the legacy
    # column kept for Phase 1 reporting compatibility.
    #
    # `fx_rate_used` is the live USD→NGN rate captured at credit time.
    # We persist it so a future reconciliation pass (Phase 4, Flutterwave
    # payout) can audit: "we credited at rate X; what was the rate Y minutes
    # later when the network settled?"
    #
    # `user_points_credited` is what we added to the wallet for this
    # impression. The math: revenue_usd × fx_rate_used × 0.80 (user share)
    # × 100 (100 pts = ₦1). Persisted so the wallet transaction list and
    # any future reconciliation can show the exact value the user earned.
    revenue_usd: Mapped[float | None] = mapped_column(BigInteger, nullable=True)
    fx_rate_used: Mapped[float | None] = mapped_column(BigInteger, nullable=True)
    user_points_credited: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Lifecycle of the credit itself:
    #   "credited"          — user share > 0, wallet bumped
    #   "rejected_low_value" — user share rounded to 0 pts; no credit (we
    #                          still record the impression but don't
    #                          fabricate a "1 point" floor)
    #   "duplicate"          — transaction_id already seen; idempotent no-op
    credit_status: Mapped[str] = mapped_column(String(50), default="credited")


class ReadingProgress(Base):
    """Where a user is within a long-form work (book, article series).

    One row per (user, work). The `work_id` is the id of the parent
    ContentCatalog row (the unsliced book). The pointer at
    `current_slice_id` is which child slice they should read next, and
    `slices_completed` counts how many child slices they've finished.

    When a user opens the app, we read this to put them back where they
    left off. When they finish a slice, we bump `current_slice_id` to
    the next slice in the work; when they finish the last slice we set
    `is_finished=True` and stop tracking.

    Indexes: (user_id, work_id) is unique — one progress row per work
    per user. work_id is indexed because the catalog queries
    "who's mid-way through work X".
    """

    __tablename__ = "reading_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    work_id: Mapped[int] = mapped_column(BigInteger, index=True)
    current_slice_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    current_slice_order: Mapped[int] = mapped_column(Integer, default=1)
    slices_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_slices: Mapped[int] = mapped_column(Integer, default=0)
    is_finished: Mapped[bool] = mapped_column(Boolean, default=False)
    last_read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SliceBookmark(Base):
    """Scroll offset within a single slice body.

    One row per (user, slice). When a user scrolls past the saved
    offset by >300px we update the row. On resume, the reader fetches
    this row and scrolls to the saved offset.

    Separate from ReadingProgress because a user can be mid-scroll
    within a slice without having "finished" it. ReadingProgress is
    the coarse-grained "which slice"; SliceBookmark is the
    fine-grained "where within the slice".
    """

    __tablename__ = "slice_bookmarks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    slice_id: Mapped[int] = mapped_column(BigInteger, index=True)
    scroll_offset_px: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PayoutAccount(Base):
    """The user's payout bank account. One row per user.

    Paystack-validated in Phase 4 (Payments). v1 stores the input as
    the user typed it (`verified=False`) so the UI can surface the
    link without Paystack being wired yet. When Phase 4 lands, the
    payouts router will call Paystack's `/transferrecipient/create`
    to populate `recipient_code` and flip `verified` to True once the
    account number resolves against the resolved name.

    `account_number` is the full 10-digit NUBAN. We never expose it
    back over the wire after the user has saved it — see
    `account_number_last4` on the PayoutAccount Pydantic response.
    Phase 4 should encrypt this column at rest.

    `user_id` is UNIQUE so we get idempotent inserts (the payouts
    router does an upsert-by-user pattern, not append). Indexed on
    `user_id` so the per-user lookup is O(log n).
    """

    __tablename__ = "payout_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    bank_code: Mapped[str] = mapped_column(String(10))
    bank_name: Mapped[str] = mapped_column(String(120))
    account_number: Mapped[str] = mapped_column(String(10))
    # Phase 4 will populate this from Paystack's `/transferrecipient/create`
    # response. The id we pass to /transfer when withdrawing.
    recipient_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Free-text account name. Phase 4 sets this from Paystack's `/verify`
    # response. v1 stores "Pending validation" if the user didn't supply one.
    account_name: Mapped[str] = mapped_column(String(255))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PayoutTransaction(Base):
    """One row per initiated Paystack transfer.

    Lifecycle:
      1. The withdraw handler creates the row BEFORE calling Paystack
         (status='pending'). The balance debit happens in the same
         transaction so we never end up with a debit and no transfer
         record.
      2. Paystack's webhook handler updates the row when settlement
         lands:
           - 'transfer.success' → status='success', settled_at=now
           - 'transfer.failed' / 'transfer.reversed' → status='failed',
             points_balance is restored by the webhook handler too
      3. The row stays around as the audit trail.

    `reference` is the UUID we passed as `reference` to Paystack's
    `/transfer` call. Paystack's webhook payload echoes the same
    `reference` back, so the join is `WHERE reference = ?`. UNIQUE
    so a retried-withdraw call can't double-charge.

    `amount_kobo` is stored in kobo (1/100 NGN) to avoid float-rounding
    in money math. The wallet's points are 1:1 with kobo.

    `fee_kobo` is the flat fee the user paid on top of `amount_kobo`
    (set from `settings.withdrawal_fee_tiers`). The user's wallet is
    debited `amount_kobo + fee_kobo`; they receive the full
    `amount_kobo` via Paystack. On `transfer.failed` the webhook
    handler reverses the gross debit (amount + fee) so the user
    ends up with their original balance.

    `balance_after_debit` snapshots `User.points_balance` at the
    moment the gross debit hit. This is the audit value: if the row
    ends up `status='failed'`, the reversal should put the balance
    back exactly to `balance_after_debit + amount_kobo + fee_kobo`.
    """

    __tablename__ = "payout_transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    reference: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    amount_kobo: Mapped[int] = mapped_column(BigInteger)
    fee_kobo: Mapped[int] = mapped_column(BigInteger, default=0)
    recipient_code: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    paystack_transfer_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    balance_after_debit: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
