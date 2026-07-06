# Phase 4: Payments & Premium Tier

## Goal
Diversify revenue beyond ads with direct user payments for premium subscriptions.

## Backend Tasks

### 1. Payment Service (`app/services/subscription.py`)
- [ ] Paystack initialization helper
- [ ] Premium tier check helper: `is_premium(user)`
- [ ] Subscription expiry checker
- [ ] Tier benefit calculator (2x points, ad-free)

### 2. Payment Router (`app/routers/payments.py`)
- [ ] `POST /api/v1/payments/initiate` → Start Paystack checkout
- [ ] `POST /api/v1/payments/paystack/webhook` → Handle payment confirmation
- [ ] `GET /api/v1/payments/history` → User's payment history
- [ ] `GET /api/v1/payments/subscription` → Current subscription status

### 3. Subscription Management
- [ ] Cron job to expire subscriptions
- [ ] Auto-revert to FREE tier when expired
- [ ] Grace period logic (3 days)

### 4. Premium Benefits Integration
- [ ] Study unlock: skip ads for premium users
- [ ] Reading points: 2x multiplier for premium
- [ ] Ad-free indicator in wallet

## Frontend Tasks

### 1. Paywall Screen (`app/subscription/pricing.tsx`)
- [ ] Two-column comparison (Free vs Premium)
- [ ] Feature list with checkmarks
- [ ] Price display with monthly/yearly toggle
- [ ] "Upgrade Now" CTA

### 2. Checkout Flow
- [ ] Paystack Web SDK integration
- [ ] `expo-web-browser` for hosted checkout
- [ ] Success callback handler
- [ ] Error handling + retry

### 3. Premium UI Indicators
- [ ] Gold badge in profile
- [ ] "Premium" pill in wallet
- [ ] Billing history screen
- [ ] Subscription management screen

### 4. Benefit Application
- [ ] Skip UnlockModal for premium users
- [ ] Show 2x multiplier in reading rewards
- [ ] Hide ad CTAs for premium users

## Database Changes
✅ Already exists:
- `payments` table with Paystack tx_ref
- `User.tier` enum (FREE | PREMIUM_MONTHLY | PREMIUM_YEARLY)
- `User.subscription_expires_at` datetime

## Configuration
Add to `.env`:
```
PAYSTACK_SECRET_KEY=sk_test_...
PAYSTACK_PUBLIC_KEY=pk_test_...
PAYSTACK_WEBHOOK_SECRET=...
```

## Pricing (Nigeria)
- **Monthly**: ₦500 (~$0.33)
- **Yearly**: ₦5,000 (~$3.30, save ₦1,000)

## Premium Benefits
1. **Ad-free study materials** (no unlock modals)
2. **2x reading points** (10 pts per 10 min vs 5 pts)
3. **Priority AI generation** (faster MCQ/flashcard creation)
4. **Gold "Premium" badge**
5. **Billing history** access

## Test Mode
Use Paystack test cards:
- Success: `4084084084084081`
- Decline: `5060666666666666666`

## Acceptance Criteria
- [ ] Free user sees paywall in study unlock flow
- [ ] Premium user bypasses unlock modals automatically
- [ ] Reading points 2x for premium (verified in wallet)
- [ ] Paystack webhook confirms payment + updates tier
- [ ] Subscription expires → auto-revert to FREE
- [ ] Billing history shows all transactions
- [ ] Play Store update: "PagePay: Read, Study, Learn & Earn (Premium)"
