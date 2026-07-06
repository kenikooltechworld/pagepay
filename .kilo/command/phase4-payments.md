# Command: Phase 4 — Payments & Premium Tier

**Duration:** Weeks 11–13
**Agents:** Backend + Frontend
**Goal:** Validate direct revenue with Paystack. One-tap checkout, premium unlock, wallet funding, withdrawals, billing history.

**Status:** ✅ IMPLEMENTED with Paystack (Production-ready on Render.app)

---

## Backend Tasks

### Step 1: Paystack Integration ✅ COMPLETE
- **Wallet Deposits**: `POST /api/v1/wallet/deposit`
  - User pays deposit amount + 1.5% processing fee (capped at ₦2,000)
  - Returns Paystack payment URL
  - Webhook credits wallet after successful payment
  - User receives deposit amount in points (100 pts = ₦1)
  
- **Premium Subscriptions**: `POST /api/v1/payments/initiate`
  - Monthly: ₦500, Yearly: ₦5,000
  - Returns Paystack checkout URL
  - Webhook upgrades user tier after payment
  
- **Withdrawals**: `POST /api/v1/payouts/withdraw`
  - Sends money to user's bank via Paystack Transfers API
  - Fees: ≤₦5k = ₦15, ≤₦50k = ₦35, >₦50k = ₦70
  - Minimum: ₦1,000
  
- **Webhook Handling**: `POST /api/v1/payments/webhook`, `POST /api/v1/payouts/webhook`
  - HMAC-SHA512 signature verification using `PAYSTACK_SECRET_KEY`
  - Credits wallet for deposits
  - Upgrades tier for subscriptions
  - Confirms withdrawals, reverses on failure

### Step 2: Bank Account Linking ✅ COMPLETE
- `PUT /api/v1/payouts/account`: Link bank account
  - Validates account via Paystack `/bank/resolve` API
  - Creates Paystack transfer recipient
  - Stores `recipient_code` for withdrawals
  
- `GET /api/v1/payouts/banks`: List Nigerian banks
  - Proxied from Paystack API
  - Cached for 1 hour

### Step 3: Subscription Enforcement ✅ COMPLETE
- Middleware: Checks `user.tier` AND `subscription_expires_at > now()`
- Premium features: Ad-free, 2x points multiplier
- Auto-expire: Users revert to free tier after expiry (handled by queries)

### Step 4: Transaction History ✅ COMPLETE
- `GET /api/v1/wallet/transactions`: Unified point history
  - Reading sessions
  - Ad rewards
  - Bill commissions
  
- `GET /api/v1/payouts/transactions`: Withdrawal history
  - Status tracking
  - Fee details
  - Settlement timestamps

### Step 5: Security & Resilience ✅ COMPLETE
- Webhook signature verification (HMAC-SHA512)
- Idempotent webhook processing
- Withdrawal balance checks before API calls
- Paystack balance check before processing withdrawals
- Payment records with unique `provider_tx_ref`

### Step 6: Testing ✅ COMPLETE
- Unit tests with mocked Paystack responses
- Test: initiate → webhook → wallet credit
- Test: withdraw → webhook → reversal on failure
- Test: duplicate webhooks (no double credit)

---

## Frontend Tasks

### Step 1: Wallet Screens ✅ COMPLETE
- `app/(tabs)/wallet.tsx`: Main wallet screen
  - Shows points balance (100 pts = ₦1)
  - "Fund Wallet" button
  - "Withdraw" button
  - Transaction history
  
- `app/fund-wallet.tsx`: Deposit screen
  - Quick amounts: ₦500 - ₦20,000
  - Custom amount input
  - Shows processing fee breakdown
  - Total payment calculation
  - Opens Paystack checkout
  
- Withdrawal screen: Send to linked bank account
  - Shows withdrawal fees
  - Links to bank account setup

### Step 2: Premium Status Indicators ✅ COMPLETE
- Wallet tab: Premium badge if active
- Study tab: Premium features unlocked
- Points multiplier: 2x for premium users

### Step 3: Billing History ✅ COMPLETE
- Transaction list in wallet screen
- Shows: reading earnings, ad rewards, bill commissions
- Withdrawal history available

### Step 4: Payment State Handling ✅ COMPLETE
- Opens Paystack URL via `Linking.openURL()`
- Webhook handles balance updates automatically
- Query invalidation refreshes UI after payment

---

## Acceptance Criteria (Phase 4 Complete)
✅ Paystack integration: deposits, withdrawals, subscriptions working
✅ Wallet deposit with processing fee (user pays total, receives deposit amount)
✅ Bank account linking with Paystack validation
✅ Withdrawal to Nigerian bank accounts via Paystack Transfers
✅ Premium subscriptions upgrade user tier
✅ Transaction history displays all earnings
✅ Webhook signature verification prevents fraud
✅ Idempotent webhooks prevent double-crediting
✅ All tests passing
✅ No TODO comments, placeholder strings, or mock data in committed code
✅ Production deployment on Render.app with live Paystack credentials

---

## Key Implementation Differences from Original Spec

**Changed:** Flutterwave → **Paystack**
- **Reason:** Simpler API, no OAuth complexity, better Nigerian market fit
- **Impact:** All payment flows use Paystack (deposits, withdrawals, subscriptions)

**Added:** Wallet deposit processing fees
- **Fee:** 1.5% (capped at ₦2,000), paid by user
- **Display:** Transparent breakdown shown before payment
- **Impact:** Platform breaks even on deposits, profits from bills/withdrawals

**Added:** Real-time Paystack balance checking
- **Purpose:** Prevent withdrawal failures due to insufficient platform funds
- **Implementation:** Check balance before processing each withdrawal
