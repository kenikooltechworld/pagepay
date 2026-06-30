# Command: Phase 4 — Payments & Premium Tier

**Duration:** Weeks 11–13
**Agents:** Backend + Frontend
**Goal:** Validate direct revenue with Flutterwave v4. One-tap checkout, premium unlock, billing history.

---

## Backend Tasks

### Step 1: Flutterwave v4 Integration (OAuth 2.0)
- Flutterwave moved to OAuth 2.0 in 2026 — no static secret key for API calls
- `POST /api/v1/payments/initiate`:
  - Authenticated endpoint
  - Request: `{tier: "premium_monthly", amount_kobo: 50000}` (₦500)
  - Backend gets OAuth token: POST to Flutterwave `/oauth/authorize` with client_id + client_secret (stored in env)
  - Cache token in memory/Redis with expiry (1 hour)
  - Call `POST /v1/payments` with OAuth Bearer token
  - Return: `{payment_url, tx_ref, flutterwave_tx_ref}`
  - Store `Payment` record with `status=pending`
- Webhook: `POST /api/v1/payments/flutterwave/callback`:
  - Verify signature using `flutterwave-secret-hash`
  - Find payment by `flutterwave_tx_ref`
  - If `status=success`:
    - Set `payment.status = "success"`
    - Update `user.tier = PREMIUM_MONTHLY`, `subscription_expires_at = now() + 30 days`
    - Set `webhook_confirmed = true`
    - Commit
  - Return 200

### Step 2:Paystack Fallback (Feature Flagged)
- `POST /api/v1/payments/initiate` accepts `provider: "flutterwave"` or `"paystack"`
- Paystack path: use static secret key header (unchanged)
- Store `provider` column in `payments` table (already exists)
- Only enable Paystack after Flutterwave fully tested

### Step 3: Subscription Enforcement
- Middleware or dependency `require_active_premium()`:
  - Checks `user.tier` AND `subscription_expires_at > now()`
  - Returns 403 if expired or not premium
- Use on endpoints: `/api/v1/study/unlock?method=points` (free), but any future premium-only route
- Cron job (daily): `UPDATE users SET tier='free' WHERE subscription_expires_at < NOW() AND tier != 'free'`

### Step 4: App Config for Prices
- Seed `app_config` table:
  ```
  ('premium_price_kobo', '50000')   -- ₦500
  ('premium_duration_days', '30')
  ('study_unlock_points', '50')
  ```
- Endpoint: `GET /api/v1/config/public` → returns these values
- Frontend uses these for UI — no hardcoded prices

### Step 5: Security & Resilience
- Validate `amount_kobo` against config (never trust client)
- Flutterwave idempotency: `tx_ref` must be unique — generate with `uuid4`
- Webhook retry: return 200 immediately, defer DB work to background task if slow
- Test in Flutterwave sandbox for 30 days before live

### Step 6: Testing
- Mock Flutterwave responses in tests
- Test: initiate → webhook → tier upgrade
- Test: duplicate webhook (no double credit)
- Test: expired subscription reverts to free

---

## Frontend Tasks

### Step 1: Paywall Screens
- `app/(tabs)/premium.tsx` or modal on first ad-gate attempt:
  - Two-column comparison:
    - Free: "Watch Ads" (show 2-3 rewarded ads per session)
    - Premium: "₦500/month" (highlighted)
  - Premium features: ✨ Ad-free ✨ 2x points ✨ unlimited unlocks
- CTA button: "Upgrade Now" → calls `POST /api/v1/payments/initiate`
- After response: `expo-web-browser` opens `payment_url`
- Listen for `AppState` change on return → refresh user profile

### Step 2: Premium Status Indicators
- Wallet tab: gold badge "PREMIUM" if active
- Study tab: no "unlock" prompts if premium
- Points multiplier: base * 2 (backend enforces, UI shows "+100% bonus")
- Profile tab: shows expiry date

### Step 3: Billing History
- `app/(tabs)/billing.tsx` or section in profile
- Query: `GET /api/v1/payments/history`
- List: date, amount (₦500), status, provider
- Renewal reminder: show if `subscription_expires_at < now() + 7 days`

### Step 4: Payment State Handling
- Polling after browser returns: `useQuery` with 5s refetch interval for 30s
- On confirmed upgrade: show celebration animation
- On failure: show error + retry button
- On pending: show "Confirm payment in your app"

---

## Acceptance Criteria (Phase 4 Complete)
✅ Flutterwave v4 sandbox: initiate → pay → webhook → tier upgrade
✅ Paystack code path exists but is disabled by flag
✅ Premium users get ad-free study experience
✅ 2x points reflected in wallet after upgrade
✅ Billing history displays past payments
✅ Subscription auto-expires after 30 days (tested with mock time)
✅ Price configurable from backend (OTA)
✅ No hardcoded Naira amounts in frontend code
✅ All Phase 1-3 tests still pass
✅ E2E: Free user → paywall → Flutterwave sandbox → webhook → premium unlocked
✅ No TODO comments, placeholder strings, or mock data in committed code
