# PagePay backend — complete authentication system (from `pagepay/backend`)

This document captures the **auth system as implemented in `pagepay/backend`** (source of truth), covering routes, services, models, schemas, config, rate limiting, and dependencies. It is intended as the reference for rebuilding auth into `app/backend` file-by-file.

> Scope note: “everything for auth” in this repo touches shared infra (`config`, `database`, `limiter`, `main` wiring) and several services (`email`, `sms`, `cloudinary`, `user_audit`, `welcome_bonus`, `sanitize`, `notifications/fcm`). Some are optional at runtime (guarded), but the router imports them.

## 1. HTTP routes (`app/routers/auth.py`)

Router: `APIRouter(prefix="/auth", tags=["auth"])` mounted in `main.py` under `API_PREFIX` (`/api/v1`) → **`/api/v1/auth/*`**.

| Method | Path | Auth | Purpose | Key deps/behavior |
|---|---|---:|---|---|
| POST | `/register` | No | Create user, issue tokens | Validates email/phone, username uniqueness, optional referral; generates referral code; hashes password (bcrypt via `services.auth.hash_password`); creates email verification token+6-digit code (bcrypt-hashed, 24h); sends verification email (best-effort); grants welcome bonus **after verification only** (not here); issues access JWT + refresh token (stored hashed). |
| GET | `/me` | Yes (`get_current_user`) | Current user profile | Returns `UserMe` (balances, tier, worker/sponsor flags, email_verified, avatar_url). |
| PATCH | `/me` | Yes | Update profile | Username change (lowercased, uniqueness check) or clear; avatar_url; logs `profile_update`. |
| POST | `/me/avatar` | Yes | Upload avatar | Accepts base64 `data:image/*`; deletes old Cloudinary avatar; uploads to `pagepay/avatars/user_{id}`; logs `avatar_upload`. |
| POST | `/login` | No | Login (OAuth2 form) | `@limiter.limit(settings.auth_login_rate_limit)`; accepts email/phone/username in `form.username`; lockout check (`locked_until`); verifies password; increments `failed_login_attempts`, locks after `MAX_FAILED_ATTEMPTS` for `LOCKOUT_MINUTES`; on success resets attempts, updates `last_login_*`, logs `login`; issues access+refresh tokens. |
| POST | `/change-password` | Yes | Change password | Verifies current password; sets new hash; revokes **current JWT jti** (`reason="password_change"`); logs action. |
| POST | `/logout` | Yes | Logout | Revokes **current JWT only** (refresh tokens intentionally kept for biometric/other sessions); logs `logout`; returns 204. |
| DELETE | `/me` | Yes | Delete account | Requires password (if set) + `confirmation=="DELETE"` (schema); logs start; deletes Cloudinary avatar; revokes current JWT; deletes all `RefreshToken` rows for user; deletes `User` (cascades); returns 204. |
| POST | `/refresh` | No (body token) | Rotate tokens | Reads JSON `refresh_token`; looks up non-revoked, unexpired hashed refresh token; checks user active; issues new access + new refresh, revokes old refresh; commits. |
| POST | `/forgot-password` | No | Start reset (OTP + token) | Accepts email/phone/username; if user exists creates `PasswordResetToken` (hashed, 15 min); generates 6-digit OTP stored in **in-memory** `_dev_otps` (15 min) keyed by identity; best-effort sends OTP via email/SMS; returns `ok`, `dev_otp`, message. **Note:** returns `dev_otp` (dev convenience/security risk in prod). |
| POST | `/forgot-password/verify-otp` | No | Verify OTP → reset token | Validates OTP from `_dev_otps`, deletes it, returns `reset_token` (raw) for reset. |
| POST | `/reset-password` | No | Set new password | Validates hashed `PasswordResetToken` (unused, unexpired); hashes new password; marks token used; logs `password_reset`. |
| POST | `/verify-email` | No | Verify via token | Finds unverified user by email; checks bcrypt-hashed `email_verification_token` and expiry; marks verified, clears tokens; logs; grants welcome bonus (best-effort). |
| POST | `/verify-email-code` | No | Verify via 6-digit code | Same as token verify but checks bcrypt-hashed `email_verification_code`; clears token+code; grants welcome bonus. |
| POST | `/resend-verification` | Yes | Resend verification | Requires user email and not verified; generates new token+code (bcrypt-hashed, 24h); sends email. |
| POST | `/google` | No | Google OAuth login/register | Requires `settings.google_client_id`; verifies ID token via `google.oauth2.id_token`; requires verified Google email; finds/creates user (auto username), sets `email_verified=True`; issues access+refresh tokens. |
| GET | `/audit-logs` | Yes | User audit trail | Query params `limit` (<=100), `offset`; returns logs from `get_user_audit_logs`. |

### Auth router helpers
- `_get_jti_from_request`: decodes Bearer token (without DB revoke check here) to extract `jti` for revocation on logout/password change/delete.
- `_generate_referral_code`, `_hash_token` (SHA-256), `_hash_refresh_token` (SHA-256).
- In-memory OTP store: `_dev_otps: dict[str, tuple[str,str,datetime]]` + `_cleanup_expired_otps()` (process-local, not durable).

## 2. Auth/security services (`app/services/auth.py`)

- **Password hashing:** `bcrypt` (`hashpw`/`gensalt(rounds=12)`), input truncated to 72 bytes (bcrypt limit). `verify_password` catches `ValueError/TypeError`.
- **Access token (JWT):** `python-jose` `jwt.encode/decode`. Payload: `sub` (user id string), `exp` (now + `settings.access_token_expire_minutes`), `type="access"`, `jti` (`secrets.token_hex(16)` if not provided). Signed with `settings.secret_key`, `settings.algorithm` (default HS256).
- **Refresh token:** opaque `secrets.token_urlsafe(64)` (stored as SHA-256 hash in DB, 30-day expiry in router).
- **Revocation:** `revoke_jwt` inserts `RevokedJWT(jti,user_id,reason,expires_at=now+24h)` (note: revocation TTL fixed at 24h in service; access token expiry is config-driven). `is_jwt_revoked` checks unexpired revocation row.
- **`get_current_user` dependency:** `OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")`; decodes JWT; requires `sub` and `jti`; rejects if revoked; loads `User`; rejects if `user.status != "active"` (403). Used by protected endpoints and by rate-limit key derivation.
- **`decode_token`:** decode without user/revocation checks (used by limiter).

## 3. Rate limiting (`app/limiter.py`, `main.py`)

- Uses `slowapi`. Key func `_get_user_id_or_ip`: if Bearer token decodes to `sub` → `user:{id}`, else client IP. Prevents shared-NAT unfairness for authenticated users.
- `limiter = Limiter(key_func=...)` attached to `app.state.limiter` in `main.py`.
- Login endpoint: `@limiter.limit(settings.auth_login_rate_limit)` (DSL string, e.g. `5/15minutes`).

## 4. Database/session (`app/database.py`) — shared but required for auth

- Async SQLAlchemy: converts `postgresql://` → `postgresql+asyncpg://`; strips libpq params (`sslmode`, etc.) and sets `connect_args["ssl"]` via `ssl.create_default_context()` (strict in production, relaxed otherwise). Pool: `pool_size`, `max_overflow`, `pool_recycle`, `pool_pre_ping=True`. `AsyncSessionLocal`, `Base` (DeclarativeBase), `get_db()` dependency.
- **Note:** `pagepay/backend` uses `database_url`, pool settings, etc. from its larger `config.py`; `app/backend` currently has a minimal config and must be expanded carefully when porting.

## 5. Config relevant to auth (`app/config.py` in pagepay)

Key settings (names as in Pydantic settings / env): `database_url`, `secret_key`, `algorithm`, `access_token_expire_minutes`, `environment`, `cors_origins`, `auth_max_failed_attempts`, `auth_lockout_minutes`, `auth_login_rate_limit`, `google_client_id` (optional), `public_base_url`/`frontend_url` (email/reset links in services), email/SMS/cloudinary/provider keys, `admin_token` (production guard), `wallet_split_enabled`/welcome bonus points (welcome flow). Production validator enforces strong `SECRET_KEY`/`ADMIN_TOKEN`.

## 6. Models (`app/models/__init__.py`) — auth-related

- **`User`**: identity (`email`, `phone`, `username` unique, `password_hash` nullable for OAuth), balances/tier/role/status/ban/subscription/referrals, **auth security** (`failed_login_attempts`, `locked_until`, `email_verified`, `email_verification_token/code` + expires, `last_login_*`, `device_fingerprint`, `transaction_pin_hash`), worker/sponsor/profile fields, `study_data` JSON, `created_at`, etc.
- **`RefreshToken`**: `user_id`, `token_hash`, `expires_at`, `revoked`, `ip_address`, `user_agent`, `device_fingerprint`, timestamps.
- **`RevokedJWT`**: `jti` unique, `user_id`, `reason`, `expires_at`, `created_at`.
- **`PasswordResetToken`**: `user_id`, `token_hash` unique, `expires_at`, `used_at`, `created_at`.
- **`UserAuditLog`**: `user_id`, `action`, ip/ua/device, `extra_data`, `created_at`.
- **`PointCredit`**: `UNIQUE(user_id, source)` — used for idempotent welcome bonus (`welcome_bonus`).
- **`Notification`**: in-app notifications (welcome bonus side effect).
- Enums: `UserTier`. Shared `Base = DeclarativeBase()`.

## 7. Pydantic schemas (`app/schemas.py`) — auth-related

- `UserRegister` (email/phone, username<=12, password>=6 + strong-password validator, `referral_code`; username validator), `TokenResponse(access_token, refresh_token, token_type)`, `UserMe` (balances, tier, flags, `model_config from_attributes`), `UserUpdate`, `ChangePasswordRequest(current/new >=8)`, `DeleteAccountRequest(password>=6, confirmation=="DELETE")`.
- Forgot/reset: `ForgotPasswordRequest` (email/phone/username), `ForgotPasswordVerifyOtpRequest` (+otp 6), `ForgotPasswordVerifyOtpResponse`, `ResetPasswordRequest(token, new_password>=8)`.
- Verification: `EmailVerificationRequest(email, token)`, `EmailVerificationCodeRequest(email, code)`. OAuth: `GoogleAuthRequest(id_token, length bounds)`.
- Shared validators in schema module: `_validate_password_strength`, `_validate_username` (also used by sponsor register).

## 8. Supporting services used by auth router

- `services.sanitize.sanitize_for_log` — log injection mitigation.
- `services.email` — `send_verification_email`, `send_password_reset_otp_email` (and reset/welcome helpers); uses Resend + settings (`resend_api_key`, `email_from`, `public_base_url`).
- `services.sms.send_password_reset_sms` — OTP SMS (best-effort).
- `services.cloudinary.upload_base64_image` / `delete_image` — avatar.
- `services.user_audit.log_user_action` / `get_user_audit_logs` — writes `UserAuditLog`.
- `services.welcome_bonus.grant_welcome_bonus` — idempotent `PointCredit` insert (PG/SQLite dialect handling), credits wallet (split-ledger aware via settings), sends welcome email/notification/push best-effort. **Auth calls it only after successful email verification**.
- `services.notifications.create_notification` (used by welcome bonus).
- `services.fcm` push (welcome bonus, optional/background).

## 9. `main.py` wiring (auth-relevant)

- Creates FastAPI app, sets `app.state.limiter`, adds middleware (request-id, size limit, security headers, CORS from `settings.cors_origins_list`), includes routers: `app.include_router(auth.router, prefix=API_PREFIX)` where `API_PREFIX="/api/v1"`. Runs migrations/seeds/background tasks and other infra (Socket.IO, scheduler, Firebase) — not strictly required to understand auth endpoints but present in production app.

## 10. Rebuild plan for `app/backend` (file-by-file, minimal safe order)

1. **Core/config expansion** — add auth settings: `secret_key`, `algorithm`, `access_token_expire_minutes`, `auth_*`, `cors_origins`, `google_client_id` (optional), plus env validation as needed. Keep `extra="ignore"`.
2. **DB models (auth subset)** — `Base`, `User` (auth fields + minimal required columns), `RefreshToken`, `RevokedJWT`, `PasswordResetToken`, `UserAuditLog`, `UserTier` (and later `PointCredit`/`Notification` if welcome bonus kept). Use Alembic/migrations strategy appropriate for Neon.
3. **Schemas** — auth DTOs + validators.
4. **Security service** — `services/auth.py` (hash/verify, JWT create/decode, revoke, `get_current_user`, `OAuth2PasswordBearer`).
5. **Limiter** — key func + limiter instance; wire `app.state.limiter` and exception handler.
6. **Supporting services (stubs or real, incremental)** — `sanitize_for_log`, `user_audit`; then `email/sms/cloudinary` only if needed; `welcome_bonus/notifications/fcm` can be deferred/feature-flagged.
7. **Router** — port endpoints in slices (register/login/me/refresh first; verification/reset/google/avatar/delete later). Register under `/api/v1`.
8. **Tests** — unit (password/JWT), integration (register→login→me→refresh→logout, lockout, revoked JWT).

## 11. Risks/notes observed in source

- **Forgot-password returns `dev_otp`** in response (and uses in-memory OTP store) — convenient for dev, dangerous if exposed in production.
- **Revocation record TTL fixed to 24h** in `services.auth.revoke_jwt`; should be >= access token lifetime or derived from token `exp`.
- **`get_current_user` does a DB lookup per request** and checks `RevokedJWT` — correct for revocation, but has cost; acceptable with indexing.
- **Refresh flow** accepts JSON body (not form) and rotates refresh token (revokes old). Consider reuse detection/family rotation hardening later.
- **Account deletion** cascades rely on DB constraints; ensure migrations/FKs match model expectations.
- **Encoding artifacts** appear in copied text (mojibake in comments) — cosmetic; logic unaffected.

---
Generated for rebuild reference. Source inspected: `pagepay/backend/app/routers/auth.py`, `services/auth.py`, `services/email.py`, `services/user_audit.py`, `services/welcome_bonus.py`, `models/__init__.py` (auth sections), `schemas.py` (auth sections), `config.py` (auth/db/cors), `database.py`, `limiter.py`, `main.py` (wiring), `routers/__init__.py`.
