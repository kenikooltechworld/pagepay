# PagePay Auth System — Complete Implementation Guide

This document is the single source of truth for how the auth system in `app/backend` was built, file by file, from an empty folder to a fully tested, production-ready auth system.

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Prerequisites](#2-prerequisites)
3. [Step-by-Step Build](#3-step-by-step-build-file-by-file)
4. [Database Setup (Neon + Docker)](#4-database-setup-neon--docker)
5. [Environment Variables](#5-environment-variables-env)
6. [Configuration (core/config.py)](#6-configuration)
7. [Database Layer (core/database.py)](#7-database-layer)
8. [Models (models/user.py)](#8-models)
9. [Schemas](#9-schemas)
10. [Repositories](#10-repositories)
11. [Services](#11-services)
12. [Controllers](#12-controllers)
13. [Routers](#13-routers)
14. [Main App (main.py)](#14-main-app)
15. [Limiter](#15-limiter)
16. [Socket.IO](#16-socketio)
17. [Firebase/FCM](#17-firebasefcm)
18. [Cloudflare R2](#18-cloudflare-r2)
19. [Alembic](#19-alembic)
20. [Endpoint Reference](#20-endpoint-reference)
21. [MVC/OOP Pattern](#21-mvcoop-pattern)
22. [Testing Checklist](#22-testing-checklist)

---

## 1. Project Structure

```
app/backend/
├── .env                          # Secrets (never committed)
├── .env.example                  # Template (committed)
├── Dockerfile                    # Container build
├── Dockerfile.cron               # Cron job container
├── docker-compose.yml            # Local dev orchestration
├── requirements.txt              # Python dependencies
├── requirements-dev.txt          # Dev/test dependencies
├── alembic.ini                   # Alembic config
├── alembic/
│   ├── env.py                    # Async migration env
│   ├── script.py.mako            # Migration template
│   └── versions/                 # Migration files
├── app/
│   ├── __init__.py
│   ├── main.py                   # FastAPI app entrypoint
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # Pydantic Settings (from .env)
│   │   ├── database.py           # Async SQLAlchemy engine + session
│   │   └── socketio.py           # Socket.IO server
│   ├── models/
│   │   ├── __init__.py           # Exports all models
│   │   └── user.py               # ORM models
│   ├── schemas/
│   │   ├── __init__.py           # Exports all schemas
│   │   ├── auth.py               # Auth request/response DTOs
│   │   ├── pin.py                # PIN request/response DTOs
│   │   └── notifications.py      # Notification DTOs
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── user_repository.py
│   │   ├── refresh_token_repository.py
│   │   ├── password_reset_token_repository.py
│   │   ├── point_credit_repository.py
│   │   ├── user_audit_repository.py
│   │   ├── notification_repository.py
│   │   ├── fcm_token_repository.py
│   │   └── user_notification_preference_repository.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py       # Password hashing, JWT, revocation
│   │   ├── email_service.py      # Resend email sending
│   │   ├── email_verification_service.py
│   │   ├── password_reset_service.py
│   │   ├── welcome_bonus_service.py
│   │   ├── google_auth_service.py
│   │   ├── cloudflare_r2.py      # R2 upload/compress
│   │   ├── fcm_service.py        # Firebase push
│   │   └── sms_service.py        # SMS (placeholder)
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── auth_controller.py    # Auth use-case orchestration
│   │   ├── pin_controller.py     # PIN use-case orchestration
│   │   └── notification_controller.py
│   └── routers/
│       ├── __init__.py
│       ├── auth.py               # Thin HTTP layer for auth
│       ├── pin.py                # Thin HTTP layer for PIN
│       └── notifications.py      # Thin HTTP layer for notifications
└── firebase-service-account.json  # Firebase credentials (gitignored)
```

## 2. Prerequisites

- Python 3.11+
- Docker Desktop (running)
- Neon PostgreSQL account (free tier works)
- Resend account (for emails)
- Cloudflare R2 bucket (for media)
- Google Cloud Console project (for OAuth)
- Firebase project (for push notifications)

## 3. Step-by-Step Build (File by File)

### Step 1: Create folder structure

```powershell
$base = "app/backend/app"
$dirs = @("$base", "$base/core", "$base/models", "$base/schemas", "$base/routers",
          "$base/services", "$base/repositories", "$base/controllers")
foreach ($d in $dirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
foreach ($d in $dirs) { $f = Join-Path $d "__init__.py"; if (-not (Test-Path $f)) { New-Item -ItemType File -Path $f | Out-Null } }
```

### Step 2: Create requirements.txt

Key auth-related packages: fastapi, uvicorn, gunicorn, sqlalchemy (asyncio), asyncpg, pydantic, pydantic-settings, python-jose (JWT), bcrypt, slowapi (rate limiting), resend (email), google-auth (OAuth), boto3 + Pillow (R2), firebase-admin (FCM), python-socketio, alembic (migrations), python-multipart (form data).

### Step 3: Create Dockerfile

```dockerfile
FROM python:3.11
RUN useradd --create-home appuser
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip setuptools wheel && \
    pip install --retries 10 -r requirements.txt -r requirements-dev.txt
COPY . .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/v1/health')" || exit 1
USER appuser
CMD ["gunicorn", "app.main:socket_app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000", "--timeout", "120"]
```

### Step 4: Create docker-compose.yml

```yaml
services:
  api:
    build:
      context: .
      dockerfile: Dockerfile
    env_file:
      - .env
    ports:
      - "8000:8000"
    restart: unless-stopped
```

Note: No local Postgres container — Neon is the database (remote).

### Step 5-19: Create all Python files (see sections below)

### Step 20: Build and test

```powershell
docker compose -f app/backend/docker-compose.yml up -d --build
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/health/db
```

---

## 4. Database Setup (Neon + Docker)

1. Create free account at https://neon.tech
2. Create project → get connection string: `postgresql://user:pass@ep-xxx.neon.tech/dbname?sslmode=require`
3. Docker runs only the API container (no local Postgres)
4. API connects to Neon via `DATABASE_URL` in `.env`
5. SSL: asyncpg doesn't accept `sslmode` in URL → convert to `postgresql+asyncpg://`, strip params, pass SSLContext via `connect_args["ssl"]`

## 5. Environment Variables (.env)

See the full .env template in the project. Key variables:
- `DATABASE_URL` — Neon connection string
- `SECRET_KEY` — JWT signing key (generate: `openssl rand -hex 32`)
- `ALGORITHM` — HS256
- `ACCESS_TOKEN_EXPIRE_MINUTES` — 10080 (7 days)
- `AUTH_MAX_FAILED_ATTEMPTS` — 5
- `AUTH_LOCKOUT_MINUTES` — 15
- `AUTH_LOGIN_RATE_LIMIT` — 5/15minutes
- `RESEND_API_KEY` — Resend API key
- `EMAIL_FROM` — sender email
- `CLOUDFLARE_*` — R2 credentials
- `GOOGLE_CLIENT_ID` — Google OAuth client ID
- `FIREBASE_SERVICE_ACCOUNT_FILE` — firebase-service-account.json
- `WELCOME_BONUS_POINTS` — 100
- `POINTS_PER_NAIRA` — 10
- `WALLET_SPLIT_ENABLED` — True
- `PUBLIC_BASE_URL` — http://localhost:8000

## 6. Configuration (core/config.py)

Uses `pydantic-settings` to load from `.env`. All settings are typed. `extra="ignore"` allows many keys in `.env` while only defining what we use.

Key settings: database_url, environment, secret_key, algorithm, access_token_expire_minutes, auth_max_failed_attempts, auth_lockout_minutes, auth_login_rate_limit, resend_api_key, email_from, public_base_url, google_client_id, cloudflare_* (R2), firebase_service_account_key/file, welcome_bonus_points, points_per_naira, wallet_split_enabled.

## 7. Database Layer (core/database.py)

- Async SQLAlchemy engine for Neon (asyncpg driver)
- Converts `postgresql://` → `postgresql+asyncpg://`
- Strips unsupported query params (sslmode, channel_binding, etc.)
- Sets SSL via `connect_args["ssl"]` (strict in prod, relaxed in dev)
- Connection pool: pool_size=5, max_overflow=10, pool_recycle=1800, pool_pre_ping=True
- Exports: engine, AsyncSessionLocal, Base, get_db() (FastAPI dependency)

## 8. Models (models/user.py)

### User (table: users)
- Identity: email, phone, username (all unique, nullable)
- Auth: password_hash (bcrypt), email_verified, email_verification_token/code/expires_at
- Security: failed_login_attempts, locked_until, last_login_at/ip/user_agent, device_fingerprint
- Profile: tier (enum), role, status, avatar_url, referral_code, referred_by
- Wallet: points_balance, service_credit_balance, cashable_balance
- Transaction PIN: transaction_pin_hash
- Timestamps: created_at

### RefreshToken (table: refresh_tokens)
- user_id, token_hash (SHA-256), expires_at, revoked, ip_address, user_agent, device_fingerprint, created_at

### RevokedJWT (table: revoked_jwts)
- jti (unique), user_id, reason, expires_at, created_at

### PasswordResetToken (table: password_reset_tokens)
- user_id, token_hash (unique), expires_at, used_at, created_at

### PointCredit (table: point_credits)
- user_id, source, points, metadata_json, created_at
- UNIQUE(user_id, source) for idempotent grants

### UserAuditLog (table: user_audit_logs)
- user_id, action, ip_address, user_agent, device_fingerprint, extra_data, created_at

### Notification (table: notifications)
- user_id, title, body, category, data, read, created_at

### UserNotificationPreference (table: user_notification_preferences)
- user_id (PK), push_enabled, study_reminders, task_alerts, referral_bonuses, wallet_updates, ad_rewards, quiet_hours_start/end, created_at, updated_at

### FCMToken (table: fcm_tokens)
- id, user_id, token, platform, device_id, is_active, created_at, updated_at

### UserTier (enum)
- FREE, STUDY_PLUS_MONTHLY, STUDY_PLUS_YEARLY, COMPLETE_PLUS_MONTHLY, COMPLETE_PLUS_YEARLY

## 9. Schemas (schemas/auth.py, schemas/pin.py, schemas/notifications.py)

### Auth Schemas (schemas/auth.py)

**UserRegister**: email (EmailStr|None), phone (str|None), username (str|None, max 12, validated), password (str, min 8, strength validated), referral_code (str|None, max 12)
- Validators: password strength (uppercase, digit, special char), username (allowed chars, reserved names)

**TokenResponse**: access_token, refresh_token, token_type (default "bearer")

**UserMe**: id, email, phone, username, tier, role, status, created_at, email_verified, avatar_url, transaction_pin_set
- model_config = ConfigDict(from_attributes=True)

**RefreshRequest**: refresh_token

**EmailVerificationRequest**: email, token
**EmailVerificationCodeRequest**: email, code

**ForgotPasswordRequest**: email|None, phone|None, username|None
**ForgotPasswordVerifyOtpRequest**: email/phone/username, otp (6 chars)
**ForgotPasswordVerifyOtpResponse**: ok, reset_token

**ResetPasswordRequest**: token, new_password (min 8, strength validated)

**GoogleAuthRequest**: id_token (10-4096 chars)

**AvatarUploadRequest**: image (base64 data URL)

**DeleteAccountRequest**: password (min 6), confirmation (must be "DELETE")

**ChangePasswordRequest**: current_password (min 8), new_password (min 8, strength validated)

**UserUpdate**: username (str|None), avatar_url (str|None)

**AuditLogsResponse**: logs (list), total

### Pin Schemas (schemas/pin.py)

**PinSetupRequest**: password (min 8), pin (4-6 digits, regex ^\d+$)
**PinVerifyRequest**: pin (4-6 digits)
**PinChangeRequest**: current_pin, new_pin (4-6 digits)
**PinStatusResponse**: has_pin (bool)

### Notification Schemas (schemas/notifications.py)

**NotificationPreferences**: push_enabled, study_reminders, task_alerts, referral_bonuses, wallet_updates, ad_rewards, quiet_hours_start/end (Optional[str] "HH:MM")
**NotificationPreferencesResponse**: extends above + created_at, updated_at
**FCMTokenRequest**: token (10-512), platform (android/ios/web), device_id (optional)
**FCMTokenResponse**: id, token, platform, device_id, is_active, created_at
**NotificationResponse**: id, user_id, title, body, category, data, read, created_at
**NotificationsListResponse**: notifications (list), unread_count (int)

## 10. Repositories (data access)

Each repository is a class that takes AsyncSession and provides async CRUD methods. See full list in Section 1 of project structure.

Key repositories:
- UserRepository: get_by_id, get_by_email, get_by_phone, get_by_username, get_by_identity, get_by_referral_code, create, update, delete
- RefreshTokenRepository: create, get_valid_by_hash, revoke, revoke_all_for_user
- PasswordResetTokenRepository: create, get_valid_by_hash, mark_used
- PointCreditRepository: grant_welcome_bonus (idempotent via ON CONFLICT DO NOTHING)
- UserAuditLogRepository: create, list_for_user
- NotificationRepository: create, list_for_user, count_unread, get_by_id, mark_read, mark_all_read
- FCMTokenRepository: get_by_token, get_by_token_and_user, list_active_for_user, create, update_existing, deactivate, deactivate_by_token
- UserNotificationPreferenceRepository: get_for_user, create_default, update

## 11. Services (business logic)

### AuthService (services/auth_service.py)
- hash_password(password) → str (bcrypt, 72-byte limit, rounds=12)
- verify_password(password, hash) → bool
- create_access_token(user_id, jti) → str (JWT: sub, exp, type, jti)
- decode_access_token(token) → dict
- create_refresh_token() → str (opaque, 64 bytes)
- revoke_jwt(db, jti, user_id, reason, expires_at) → None
- is_jwt_revoked(db, jti) → bool
- resolve_current_user(token) → User (FastAPI dependency)
- generate_referral_code() → str (6-char alphanumeric)

### EmailService (services/email_service.py)
- send_email(to, subject, html) → bool (Resend)
- send_verification_email(to, token, code) → bool
- send_password_reset_otp_email(to, otp) → bool

### EmailVerificationService (services/email_verification_service.py)
- issue(user) → (token_raw, code_raw) — generates, hashes, stores (24h expiry)
- verify_by_token(email, token) → None (raises ValueError on failure)
- verify_by_code(email, code) → None
- resend(user) → (token_raw, code_raw)

### PasswordResetService (services/password_reset_service.py)
- request_reset(payload) → dict (generates OTP + reset token, sends email/SMS, returns dev_otp)
- verify_otp(payload) → str (returns raw reset token)
- reset(token, new_password) → None (marks token used, updates password)

### WelcomeBonusService (services/welcome_bonus_service.py)
- grant(user) → bool (idempotent points credit + welcome email + notification + Socket.IO emit + FCM push)

### GoogleAuthService (services/google_auth_service.py)
- verify_id_token(id_token) → dict (email, name) — verifies with Google, requires verified email

### CloudflareR2Service (services/cloudflare_r2.py)
- decode_base64(data_url) → bytes
- compress_image(data, max_size, quality) → bytes (Pillow, JPEG, quality=85)
- upload_base64(data_url, folder) → str (public URL)
- upload_bytes(data, filename, folder) → str
- delete(public_url) → None (best-effort)

### FCMService (services/fcm_service.py)
- initialize_firebase() → app (from service account JSON/file)
- send_push_notification(db, user_id, title, body, data) → bool
- send_push_background(user_id, title, body, data) → None (background task)

### SMSService (services/sms_service.py)
- send_password_reset_sms(to, code) → bool (placeholder)

## 12. Controllers (orchestration)

### AuthController (controllers/auth_controller.py)

Orchestrates all auth use-cases by combining repositories and services. Each method:
1. Validates input (raises HTTPException on failure)
2. Calls repository/service methods
3. Returns response DTOs or dicts

Methods: register, login, me, refresh, logout, verify_email, verify_email_code, resend_verification, forgot_password, verify_forgot_otp, reset_password, google_auth, upload_avatar, delete_account, get_audit_logs, update_profile, change_password

### PinController (controllers/pin_controller.py)
Methods: status, setup, verify, change

### NotificationController (controllers/notification_controller.py)
Methods: get_preferences, update_preferences, register_fcm_token, deregister_fcm_token, list_fcm_tokens, list_notifications, get_notification, mark_read, mark_all_read

## 13. Routers (HTTP layer)

All routers are **thin** — they only:
1. Parse/validate input via Pydantic schemas
2. Call the controller
3. Return the response

### auth.py (prefix="/auth", tags=["auth"]) — 17 endpoints
### pin.py (prefix="/pin", tags=["pin"]) — 4 endpoints
### notifications.py (prefix="/notifications", tags=["notifications"]) — 9 endpoints

## 14. Main App (main.py)

FastAPI app with:
- Rate limiting (slowapi, app.state.limiter, 429 handler)
- Router mounting (auth, pin, notifications under /api/v1)
- Startup: create_all tables + Firebase init
- Health endpoints: /api/v1/health, /api/v1/health/db
- Socket.IO wrapper: socket_app = socketio.ASGIApp(sio, app)

## 15. Limiter (rate limiting)

Key function: authenticated user ID (from JWT) or IP address. Applied to login endpoint (5/15minutes by default).

## 16. Socket.IO (real-time)

AsyncServer with ASGI mode. Tracks connected users by user_id. Provides emit_to_user and emit_notification helpers. Mounted as socket_app in main.py. Dockerfile CMD uses app.main:socket_app.

## 17. Firebase/FCM (push notifications)

- initialize_firebase(): loads service account from JSON string or file
- send_push_notification(db, user_id, title, body, data): sends to all active FCM tokens
- Deactivates invalid tokens (UnregisteredError)
- send_push_background(): background task with own DB session

## 18. Cloudflare R2 (media storage)

- S3-compatible (uses boto3 with Cloudflare S3 API endpoint)
- Base64 data URL → decode → Pillow compress (JPEG, quality=85, max 1MB) → upload → public URL
- Folder structure: pagepay/avatars/, pagepay/uploads/
- Delete old avatar before uploading new one (best-effort)
- Public URL format: {CLOUDFLARE_R2_PUBLIC_URL}/{key}

## 19. Alembic (migrations)

- Async env.py with create_async_engine
- Overrides sqlalchemy.url from settings
- Transforms postgresql:// → postgresql+asyncpg://
- Strips unsupported query params, sets SSL context
- Imports all models for Base.metadata
- Initial migration created and stamped

Commands:
- Create: python -m alembic revision -m "description"
- Apply: python -m alembic upgrade head
- Check: python -m alembic current
- Stamp: python -m alembic stamp head

## 20. Endpoint Reference

### Auth Router (/api/v1/auth) — 17 endpoints

1. POST /register — Create user. Validates email/phone/username/password/referral. Generates referral code. Creates verification token+code (bcrypt, 24h). Sends verification email. Issues access+refresh tokens.
2. POST /login — OAuth2 form login. Accepts email/phone/username. Rate-limited. Lockout after 5 failures for 15 min. Returns tokens.
3. GET /me — Returns current user profile.
4. PATCH /me — Update profile (username, avatar_url). Logs profile_update.
5. POST /me/avatar — Upload avatar (base64 → Cloudflare R2, compress). Returns avatar_url.
6. POST /change-password — Verify current password, set new hash, revoke current JWT (password_change), log action.
7. POST /logout — Revoke current JWT (logout). Returns 204.
8. DELETE /me — Delete account. Requires password + "DELETE" confirmation. Deletes avatar, revokes JWT, deletes refresh tokens, deletes user. Returns 204.
9. POST /refresh — Exchange refresh token for new access+refresh tokens (rotation). Reuse detection: revoked token → revoke all user tokens.
10. POST /forgot-password — Start reset. Generates 6-digit OTP + reset token (15 min). Sends OTP via email+SMS. Returns dev_otp.
11. POST /forgot-password/verify-otp — Verify OTP → returns reset_token.
12. POST /reset-password — Set new password with valid reset token. Marks token used.
13. POST /verify-email — Verify email via token. Marks email_verified=True. Grants welcome bonus.
14. POST /verify-email-code — Verify email via 6-digit code. Same as above.
15. POST /resend-verification — Resend verification email. Requires unverified email.
16. POST /google — Google OAuth. Verifies ID token, finds/creates user, issues tokens.
17. GET /audit-logs — User audit trail. Query: limit (≤100), offset.

### Pin Router (/api/v1/pin) — 4 endpoints

1. GET /status — Returns {has_pin: bool}.
2. POST /setup — Set PIN (requires password, 409 if already set).
3. POST /verify — Verify PIN → {valid: true}.
4. POST /change — Change PIN (requires current PIN).

### Notification Router (/api/v1/notifications) — 9 endpoints

1. GET /preferences — Get notification preferences (creates default if none).
2. PUT /preferences — Update preferences (push_enabled, category toggles, quiet hours).
3. POST /fcm-token — Register FCM token for push (upserts).
4. DELETE /fcm-token/{token} — Deregister FCM token (mark inactive).
5. GET /fcm-tokens — List active FCM tokens.
6. GET "" — List notifications (paginated, newest first, unread count).
7. GET /{notification_id} — Get single notification.
8. POST /{notification_id}/read — Mark notification as read.
9. POST /read-all — Mark all notifications as read.

### Health Endpoints — 2 endpoints

1. GET /api/v1/health — App liveness check. Returns {"status": "ok"}.
2. GET /api/v1/health/db — DB connectivity check (SELECT 1 to Neon).

Total: 32 endpoints

## 21. MVC/OOP Pattern Summary

### Layer Responsibilities

| Layer | Directory | Responsibility |
|-------|-----------|----------------|
| Models | models/ | ORM table definitions (SQLAlchemy). No business logic. |
| Schemas | schemas/ | Pydantic DTOs for request/response validation. No DB queries. |
| Repositories | repositories/ | All SQL/ORM queries for one aggregate. Services call these. |
| Services | services/ | Business logic, crypto, external API calls. Framework-agnostic where possible. |
| Controllers | controllers/ | Orchestrate use-cases: validate → call repos/services → return DTOs. Raise HTTPException for HTTP concerns. |
| Routers | routers/ | Thin HTTP layer: parse → call controller → return. No business logic, no SQL. |
| Core | core/ | Config, database, Socket.IO. Shared infrastructure. |

### Dependency Flow (one direction only)

Router → Controller → Service → Repository → Model

- Routers depend on controllers + schemas + auth dependency
- Controllers depend on repositories + services + schemas
- Services depend on repositories + core (config, db)
- Repositories depend on models + core (db)
- No circular dependencies

### OOP Patterns Used

- Repository pattern: Each aggregate has a repository class with async methods
- Service classes: AuthService, EmailService, etc. encapsulate business logic
- Controller classes: AuthController, PinController, NotificationController orchestrate use-cases
- Dependency injection: FastAPI Depends() for DB sessions, current user, controllers
- DTOs: Pydantic schemas for request/response validation

## 22. Testing Checklist

### Auth Flow (real email: kenikooltechworld@gmail.com)

- [x] Register → verification email sent
- [x] Verify email code (726983) → email_verified=True
- [x] Welcome bonus: 100 points credited, notification created, audit log recorded
- [x] Login → tokens issued
- [x] Me → profile returned
- [x] Patch Me → username updated
- [x] Change Password → old token revoked (401)
- [x] Login with new password → tokens issued
- [x] Refresh → new tokens (rotation)
- [x] Avatar upload → Cloudflare R2 URL returned
- [x] Audit logs → 12+ entries
- [x] PIN status/setup/verify/change → all work
- [x] Notification preferences (get/update) → works
- [x] List notifications → 1 welcome notification
- [x] Logout → token revoked (401)
- [x] Forgot password → OTP sent to Gmail
- [x] Verify OTP → reset token issued
- [x] Reset password → login with new password works

### Infrastructure

- [x] Docker container builds and runs
- [x] Neon DB connected (SELECT 1 → OK)
- [x] Firebase initialized (project_id=pagepay-17639)
- [x] Socket.IO responding (session IDs returned)
- [x] Cloudflare R2 upload (avatar → public URL)
- [x] Resend email (verification + OTP + welcome delivered)
- [x] Alembic configured (initial migration stamped)

Generated from the actual implementation in app/backend/. All code follows MVC/OOP with consistent patterns across all layers.