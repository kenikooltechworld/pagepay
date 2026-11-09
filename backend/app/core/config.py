from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database / runtime ---
    database_url: str
    environment: str = "development"

    # --- Auth / JWT ---
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 10080

    # --- Login protection ---
    auth_max_failed_attempts: int = 5
    auth_lockout_minutes: int = 15
    auth_login_rate_limit: str = "5/15minutes"

    # --- Welcome bonus (credited after email verification) ---
    welcome_bonus_points: int = 1000  # SP
    points_per_naira: int = 10
    wallet_split_enabled: bool = True

    # --- Referrals (credited when referee verifies email; SP, idempotent) ---
    referral_referrer_bonus_sp: int = 100
    referral_referee_bonus_sp: int = 100

    # --- Wallet / SP-CB ---
    # CB is cashable balance in kobo (integer). SP is non-cashable service points.
    # Conversion: SP = floor(cb_kobo * sp_per_naira / 100). Default 10 SP per ₦1.
    sp_per_naira: int = 10
    study_unlock_default_points: int = 50
    # Guard for pre-Paystack grant endpoints (POST /wallet/*/grant). If unset, grants are disabled.
    wallet_grant_secret: str | None = None

    # --- Email (Resend) ---
    resend_api_key: str | None = None
    email_from: str = "PagePay <noreply@pagepay.app>"
    public_base_url: str = "http://localhost:8000"

    # --- Google OAuth ---
    google_client_id: str | None = None

    # --- Firebase ---
    firebase_service_account_key: str | None = None
    firebase_service_account_file: str = "firebase-service-account.json"

    # --- Cloudflare R2 (S3-compatible storage) ---
    cloudflare_access_key: str | None = None
    cloudflare_secret_access_key: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    cloudflare_s3_api_endpoint: str | None = None
    cloudflare_r2_public_url: str | None = None
    cloudflare_bucket: str | None = None


settings = Settings()
