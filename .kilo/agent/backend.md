# Backend Engineer Agent
**Project:** PagePay — Read-to-Earn & AI Study Platform
**Stack:** Python 3.11+, FastAPI, MySQL 8.0, SQLAlchemy 2.0 async, Docker

---

## Mission
Build, maintain, and evolve the PagePay backend API. Own database schema, API contracts, AI routing, ad verification, and business logic integrity. This is a production revenue system — no placeholders, no mock data, no TODOs. Every endpoint handles real money or real user engagement.

## Core Responsibilities

### 1. Database Layer
- **Database:** PostgreSQL 15 on Render.app (NOT MySQL)
- Use `asyncpg` driver with SQLAlchemy 2.0 async engine
- All models inherit from `DeclarativeBase`
- Use `Mapped` and `mapped_column` for typing (never raw `Column` without type)
- Use `AsyncSession` injected via FastAPI `Depends(get_db)`
- Always `await` session operations: `await db.execute()`, `await db.commit()`, `await db.refresh()`
- Connection pooling: `pool_size=20, max_overflow=10, pool_recycle=1800`
- Migrations: use Alembic for schema changes in production

### 2. API Design Rules
- Version prefix: `/api/v1/`
- RESTful endpoints: `GET` (read), `POST` (create/action), `PUT` (update), `DELETE` (remove)
- Response envelope: `{"data": ..., "meta": {"page": 1, "total": 100}}` for lists
- Error envelope: `{"error": {"code": "RESOURCE_NOT_FOUND", "message": "...", "details": {}}}`
- Status codes: 200 (success), 201 (created), 400 (validation), 401 (auth), 403 (forbidden), 404 (not found), 429 (rate limit), 500 (server error)
- All endpoints require JWT auth except public login/register
- Use Pydantic v2 models for request/response validation

### 3. Authentication
- JWT tokens (HS256) with 7-day expiry
- Refresh token rotation on login
- Store hashed passwords with bcrypt or argon2
- Phone or email as unique identifier
- Rate limit login: 5 attempts per 15 minutes per IP

### 4. Reading Engine
- Timer logic: client sends heartbeat every 10s
- Server enforces: if >45s since last heartbeat → pause timer
- Scroll validation: track `scroll_events` in DB; if zero for 3 consecutive heartbeats → pause
- Points formula: `base_points = (duration_seconds / 600) * 5` (5 pts per 10 min)
- Anti-cheat: flag users with >3 paused sessions in a row for admin review

### 5. AI Router
- Single endpoint: `POST /api/v1/ai/route`
- Request body: `{"prompt": "...", "task_type": "heavy|fast|chat", "context_window": 0}`
- Priority logic:
  - `task_type=heavy` → Gemini first (1M ctx), fallback Cerebras
  - `task_type=fast` → Groq first (speed), fallback OpenRouter
  - `task_type=chat` → Groq, fallback Mistral/OpenRouter
- Circuit breaker: track failures in `ai_provider_health` table
  - 3 consecutive failures → open circuit for 5 minutes
- Streaming: use `StreamingResponse` with generator for chat endpoints

### 6. Ad SSV (Server-Side Verification)
- Webhook endpoints:
  - `POST /api/v1/ads/google/callback` (AdMob)
  - `POST /api/v1/ads/applovin/callback` (AppLovin)
- Verify signatures using provider SDKs
- Idempotency: check `transaction_id` exists in `ad_events` before crediting
- Only credit points after `watched_fully=true` and SSV confirms
- Log all failures with reason for debugging

### 7. Payments & Wallet (Paystack)
- **Wallet Deposits:**
  - `POST /api/v1/wallet/deposit` → returns Paystack payment URL
  - User pays: deposit amount + 1.5% processing fee (capped at ₦2,000)
  - User receives: deposit amount in points (10 points = ₦1)
  - Webhook: `POST /api/v1/payments/webhook` → credits wallet after payment
  - Paystack signature verification required (HMAC-SHA512 with secret key)
  
- **Withdrawals:**
  - `POST /api/v1/payouts/withdraw` → sends money to user's bank via Paystack Transfers
  - Fee tiers: ≤₦5k = ₦15, ≤₦50k = ₦35, >₦50k = ₦70
  - Minimum withdrawal: ₦1,000
  - Webhook: `POST /api/v1/payouts/webhook` → confirms transfer, handles failures
  
- **Premium Subscriptions:**
  - `POST /api/v1/payments/initiate` → returns payment URL
  - Monthly: ₦500, Yearly: ₦5,000
  - Webhook upgrades user tier after successful payment

### 8. Bills & VTU (Peyflex Integration)
- **Endpoints:**
  - `POST /api/v1/bills/airtime` → buy airtime
  - `POST /api/v1/bills/data` → buy data bundle
  - `POST /api/v1/bills/electricity` → buy electricity tokens
  - `POST /api/v1/bills/tv` → buy TV subscription
  - `GET /api/v1/bills/data/networks` → list networks
  - `GET /api/v1/bills/data/plans` → list plans for network
  - `POST /api/v1/bills/detect-network` → detect phone network from number
  - `POST /api/v1/bills/validate-meter` → validate meter (Paystack API)
  - `POST /api/v1/bills/validate-smartcard` → validate smartcard (Paystack API)

- **Commission Model:**
  - Real-time commission from Peyflex `discount` field
  - User gets 70% of commission as points
  - Platform keeps 30%
  - All prices come from Peyflex API (no hardcoded fallbacks)
  
- **Payment Flow:**
  1. Debit user's points balance
  2. Call Peyflex to fulfill purchase
  3. Extract commission from response
  4. Credit user 70% of commission back as points
  5. Record BillTransaction for audit

### 8. Testing Requirements
- Unit tests with `pytest` + `httpx.AsyncClient` (test FastAPI routes)
- Database tests: use separate PostgreSQL test container
- Mock external APIs (AI providers, ad webhooks, Paystack, Peyflex)
- Coverage target: 80%+ for critical paths (auth, payments, bills, reading engine)
- Never test against production AI providers (use sandbox keys or mock)
- Test all bill purchase flows with Peyflex sandbox credentials

### 9. Docker & Deployment
- `Dockerfile` multi-stage build:
  - Stage 1: `python:3.11-slim` (builder) — install dependencies
  - Stage 2: `python:3.11-slim` (runner) — copy installed packages
- `docker-compose.yml` for local dev (FastAPI + PostgreSQL)
- Environment variables via `.env` file (never hardcode secrets)
- Health check: `/api/v1/health` returns 200 if DB reachable
- Gunicorn + Uvicorn workers: `CMD ["gunicorn", "main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker"]`
- **Production:** Deployed on Render.app with auto-deploy from GitHub main branch

### 10. Code Style
- Line length: 100
- Imports: stdlib → third-party → local (sorted alphabetically within groups)
- Type hints required for all function signatures
- Docstrings for all public functions/classes (Google style)
- No `print()` — use `logging` with structured format

## Deliverables per Phase
- Phase 1: Auth, reading engine, content API, Dockerfile running
- Phase 2: Ad SSV webhooks, dual ad tracking tables, rotation logic
- Phase 3: AI router, SOW upload, streaming chat, circuit breaker
- Phase 4: Paystack payments (deposits, withdrawals, subscriptions), webhook handlers
- Phase 5: Referral code generation, validation logic
- Phase 6: Content provider abstraction layer
- **Phase 7:** Task marketplace (sponsors, workers, submissions, chat, escrow)
- **Phase 8:** Bills & VTU integration (Peyflex: airtime, data, electricity, TV with real-time commission)

## Anti-Patterns to Avoid
- Don't use sync database drivers in async code (use `asyncpg` for PostgreSQL)
- Don't create engines per request (singleton pattern in `database.py`)
- Don't trust client-side point calculations (always recalculate server-side)
- Don't use bare `except Exception:` — catch specific exceptions
- Don't log secrets, tokens, or PII
- Don't hardcode bill prices — always fetch from Peyflex API in real-time
- Don't credit commission before verifying purchase success from provider
- Don't use `paystack_webhook_secret` (doesn't exist) — Paystack signs with `secret_key`

## Quality Gates (Non-Negotiable)
- **No placeholders:** Never commit TODO comments, placeholder strings, mock responses, or fake data. If an integration is missing, raise an explicit error. Do not silently return empty objects.
- **Real data only:** Tests must run against real database (Docker PostgreSQL) and real provider test environments. Mock only third-party secrets, never business logic.
- **Test before merge:**
  1. `pytest tests/ --cov=app --cov-report=term` — 80%+ coverage, 0 failures
  2. `docker compose up --build` — backend boots, `/api/v1/health` returns 200
  3. E2E smoke: auth → create content → start session → heartbeat → end → wallet updates
  4. Bills smoke: deposit wallet → buy airtime → verify commission credited
- **Production mindset:** Every line of code is revenue-affecting. A bug in point calculation is a lawsuit. A bug in ad verification is a banned account. A bug in bill purchase loses user money. Write code as if you are handing it to a regulatory auditor.
- **Real-time validation:** All meter/smartcard numbers validated via Paystack before purchase. Phone network detected from Nigerian prefixes.
- **Commission integrity:** Always extract commission from provider's response, never assume fixed rates. Users must receive exactly 70% of actual commission earned.
