# All fastapi app settings
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080
    cors_origins: str = "http://localhost:8081,http://localhost:3000,https://pagepay.onrender.com"

    gnews_api_key: str | None = None
    gutendex_base_url: str = "https://gutendex.com"

    flutterwave_client_id: str | None = None
    flutterwave_client_secret: str | None = None
    flutterwave_secret_hash: str | None = None
    flutterwave_base_url: str = "https://api.flutterwave.com"

    # Payments provider for Phase 4. We're switching from Flutterwave to
    # Paystack — this is the placeholder where the secret key will live
    # when Phase 4 wires the payouts router to Paystack's
    # /transferrecipient, /transfer, and /verify endpoints. v1 leaves
    # the payouts endpoints as stubs and never reads this value.
    paystack_secret_key: str | None = None
    # Public key — used by the client (Paystack inline / popup) and also
    # surfaced in our backend logs when an operator needs to verify
    # which environment (test vs live) is configured.
    paystack_public_key: str | None = None
    # Shared secret Paystack uses to sign webhooks. We validate the
    # `X-Paystack-Signature` header against the raw body with HMAC-SHA512
    # in `services/paystack.py`. Mismatched signatures return 401.
    paystack_webhook_secret: str | None = None
    # Base URL we expose to Paystack's dashboard (return URLs after a
    # checkout session; the webhook URL). Defaults to localhost so
    # `paystack-cli listen-forward` works out of the box. In production
    # this must be set to the real public domain (e.g.
    # `https://api.pagepay.ng`).
    public_base_url: str = "http://localhost:8000"

    # ── Withdrawal fee tiers ────────────────────────────────────────
    # Mirrors Paystack's flat-fee transfer schedule (₦10 / ₦25 / ₦50) with
    # a markup on top. The user pays the fee in addition to the
    # withdrawal amount and receives the full amount they requested.
    # Markup goes to the merchant (us) as profit. The user always gets
    # the full amount they typed; we eat the difference between the fee
    # they pay and the fee Paystack charges us.
    #
    # Default schedule (set in ops meeting 2026-06-30):
    #   ≤ ₦5,000          → ₦15 total user fee (Paystack ₦10, profit ₦5)
    #   ₦5,001 – ₦50,000  → ₦35 total user fee (Paystack ₦25, profit ₦10)
    #   > ₦50,000         → ₦70 total user fee (Paystack ₦50, profit ₦20)
    #
    # Stored as a comma-separated list of `max_kobo:fee_kobo` pairs,
    # last pair has no max (interpreted as "everything above"). Example
    # for the default schedule:
    #   WITHDRAWAL_FEE_TIERS=500000:1500,5000000:3500,inf:7000
    #
    # The payouts router uses `compute_withdrawal_fee(amount_kobo)` which
    # walks the tiers in order and returns the matching fee.
    withdrawal_fee_tiers: str = "500000:1500,5000000:3500,inf:7000"
    # Minimum withdrawal in kobo. We default to ₦1,000 (100,000 kobo) so
    # the fee never exceeds 1.5% of the withdrawal — below that, the fee
    # feels punitive to the user. Bumping to ₦5,000 would push the max
    # fee-to-amount ratio down to 0.3%, at the cost of requiring more
    # points to cash out.
    min_withdrawal_kobo: int = 100000

    admob_app_id_android: str | None = None
    admob_app_id_ios: str | None = None
    applovin_sdk_key: str | None = None
    # Shared secret for AdMob Server-Side Verification webhooks.
    # AdMob signs each callback with this value via HMAC-SHA256; we
    # verify in `routers/ads.py:admob_ssv_callback` and return 401
    # on mismatch. Configure in the AdMob dashboard under
    # "SSV settings" — must match this value exactly.
    admob_webhook_secret: str | None = None
    # AppLovin SSV shared secret. The AppLovin webhook handler
    # returns 501 until this is set (the rest of the AppLovin
    # integration lands when the spec calls for it).
    applovin_webhook_secret: str | None = None

    # ── Phase 3: AI providers ────────────────────────────────────────
    # Free-tier keys for the multi-provider router. All three are
    # optional: if a key is missing the router simply skips that
    # provider and falls through to the next one in the priority list.
    # Never commit real keys — use env vars or a secrets manager.
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None

    # ── Phase 8: Bills & Earn (VTU aggregator) ────────────────────────
    # Peyflex is the primary VTU provider (airtime, data, electricity, TV).
    # API key from peyflex.com.ng dashboard — never commit the real value.
    peyflex_api_key: str | None = None
    peyflex_base_url: str = "https://portal.peyflex.com.ng/api/v1"

    # Commission split: portion of the aggregator's commission that goes
    # back to the user as points (the rest funds the platform).
    # 0.67 = user gets 67% of the commission, platform keeps 33%.
    bills_user_share: float = 0.67
    # Every Nth item in the catalog feed is a sponsored slot. The
    # spec's default is 4 (in-feed native every 4th item). Set to
    # 0 to disable sponsored rotation entirely (rare — only for
    # diagnosing ad-funnel issues).
    feed_sponsored_every: int = 4
    # Maximum number of sponsored items returned per feed request.
    # Bounds the response size and prevents a sparse catalog from
    # returning a wall of ads.
    feed_max_sponsored: int = 5

    # Shared secret required by X-Admin-Token on /admin/* endpoints. The
    # cron container and any operator script must send the same value.
    # In dev it's the default below; production must override via env.
    admin_token: str = "dev-admin-token"
    
    # ── Phase 7: Cloudinary for task proof uploads ───────────────────
    cloudinary_cloud_name: str | None = None
    cloudinary_api_key: str | None = None
    cloudinary_api_secret: str | None = None
    cloudinary_upload_folder: str = "pagepay/tasks"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def withdrawal_fee_tiers_parsed(self) -> list[tuple[int | None, int]]:
        """Parse `withdrawal_fee_tiers` into a list of (max_kobo, fee_kobo).

        The first tier whose `max_kobo >= amount_kobo` (or whose
        `max_kobo` is None) wins. The "inf" sentinel in the env value
        desugars to `None` (no upper bound).

        Format: comma-separated `max_kobo:fee_kobo` pairs, max
        ascending. Tiers MUST be sorted by `max_kobo` ascending or the
        router will apply the wrong fee. The default value is in that
        order. If the env value is malformed, the default is returned
        so dev/test never see a 500 from a typo.
        """
        default: list[tuple[int | None, int]] = [
            (500_000, 1_500),
            (5_000_000, 3_500),
            (None, 7_000),
        ]
        raw = (self.withdrawal_fee_tiers or "").strip()
        if not raw:
            return default
        parsed: list[tuple[int | None, int]] = []
        for piece in raw.split(","):
            piece = piece.strip()
            if not piece:
                continue
            try:
                max_str, fee_str = piece.split(":")
                max_str = max_str.strip()
                fee_str = fee_str.strip()
                max_kobo: int | None
                if max_str.lower() in ("inf", "none", "*"):
                    max_kobo = None
                else:
                    max_kobo = int(max_str)
                fee_kobo = int(fee_str)
            except (ValueError, AttributeError):
                # Malformed entry — fall back to the schedule we ship
                # in the default. This is a config bug, not a runtime
                # error, so don't crash the request path.
                return default
            parsed.append((max_kobo, fee_kobo))
        # Sanity: must be at least one tier.
        return parsed or default


settings = Settings()  # type: ignore[call-arg]
