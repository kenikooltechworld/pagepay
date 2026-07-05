# Production Setup Guide - Paystack Integration

## Render Backend Configuration

### 1. Environment Variables to Set

Go to your Render dashboard → PagePay Backend Service → Environment tab and add:

```bash
# Paystack API Keys (from https://dashboard.paystack.com/#/settings/developers)
PAYSTACK_PUBLIC_KEY=pk_live_xxxxxxxxxxxxxxxxxxxxx
PAYSTACK_SECRET_KEY=sk_live_xxxxxxxxxxxxxxxxxxxxx

# Backend URLs (replace with your actual domain)
PUBLIC_BASE_URL=https://pagepay.onrender.com
FRONTEND_URL=pagepay://  # Your app deep link scheme (or production domain)

# Alternative for web-based frontend:
# FRONTEND_URL=https://pagepay.com
```

**Note**: Paystack does NOT use a separate webhook secret. They sign webhooks with your `PAYSTACK_SECRET_KEY`.

---

## Paystack Dashboard Configuration

### 1. Get Live API Keys

1. Login: https://dashboard.paystack.com
2. **Switch to Live Mode** (toggle in top-right corner - important!)
3. Navigate to: Settings → API Keys & Webhooks
4. Copy:
   - **Live Public Key** (starts with `pk_live_`)
   - **Live Secret Key** (starts with `sk_live_`)

### 2. Configure Webhooks

1. Still in Settings → API Keys & Webhooks
2. Scroll to "Webhook Settings"
3. Click "Add Webhook URL"
4. Enter webhook URL:
   ```
   https://pagepay.onrender.com/api/v1/payments/webhook
   ```
5. Select events to listen for:
   - ✅ `charge.success` (for wallet deposits & subscriptions)
   - ✅ `transfer.success` (for withdrawals)
   - ✅ `transfer.failed` (for withdrawal failures)
   - ✅ `transfer.reversed` (for reversal handling)
6. Click Save

**Important**: Paystack does NOT generate a webhook secret. They sign webhooks using your **Secret Key** that you already have.

### 3. Configure Callback URLs (Optional but Recommended)

For better user experience after payment completion:

1. Navigate to: Settings → Preferences
2. Set **Callback URL**: 
   ```
   https://pagepay.onrender.com/payment-complete
   ```
   Or use your deep link:
   ```
   pagepay://payment-complete
   ```

---

## Testing Production Setup

### 1. Verify Environment Variables

SSH into Render or check logs to verify:

```bash
echo $PAYSTACK_SECRET_KEY  # Should show sk_live_...
echo $PUBLIC_BASE_URL      # Should show https://pagepay.onrender.com
echo $FRONTEND_URL         # Should show your production URL
```

### 2. Test Webhook Delivery

**Manual Test**:
```bash
curl -X POST https://pagepay.onrender.com/api/v1/payments/webhook \
  -H "Content-Type: application/json" \
  -H "X-Paystack-Signature: test" \
  -d '{"event":"charge.success","data":{"reference":"test"}}'
```

**Expected responses**:
- ❌ 401 Unauthorized (signature invalid) - Good! Signature verification working
- ✅ Check Render logs for: "Webhook signature mismatch" message

**Live Test with Paystack Dashboard**:
1. Go to: Developers → Webhooks
2. Click "Test Webhook" next to your configured URL
3. Select event: `charge.success`
4. Click "Send Test"
5. Check Render logs for webhook received
6. Should see: "Ignoring webhook event" or "Payment not found" (both are OK for test)

### 3. Test Complete Flow

**Wallet Deposit (Small Amount First!)**:
1. Open production app
2. Navigate to Wallet tab
3. Click "Fund Wallet"
4. Enter ₦100 (minimum test)
5. Complete payment with REAL card
6. Wait 5-10 seconds
7. Check wallet balance updated
8. Check Render logs:
   ```
   "Wallet deposit initiated: user_id=X, amount=10000, ref=wallet_deposit_..."
   "Wallet deposit confirmed: user_id=X amount=10000 kobo"
   ```

**Withdrawal**:
1. Link bank account first (Settings → Payout Account)
2. Verify account resolves correctly
3. Attempt small withdrawal (₦50)
4. Check bank account receives funds (may take 5-30 minutes)
5. Check Render logs:
   ```
   "User X withdrew Y kobo (fee=Z) → ref=pp_... status=pending"
   "Paystack webhook: transfer.success for ref=pp_..."
   ```

---

## Webhook URL Endpoints

Your backend exposes these webhook endpoints:

### 1. Payments Webhook (Deposits & Subscriptions)
```
POST https://pagepay.onrender.com/api/v1/payments/webhook
```

**Handles**:
- `charge.success` → Credits wallet or upgrades subscription
- Validates HMAC-SHA512 signature
- Returns 401 if signature invalid

**Configure in Paystack**: Settings → API Keys & Webhooks → Add Webhook

---

### 2. Payouts Webhook (Withdrawals)
```
POST https://pagepay.onrender.com/api/v1/payouts/webhook
```

**Handles**:
- `transfer.success` → Marks withdrawal as completed
- `transfer.failed` → Reverses wallet debit, refunds user
- `transfer.reversed` → Reverses wallet debit, refunds user
- Validates HMAC-SHA512 signature
- Returns 401 if signature invalid

**Configure in Paystack**: Settings → API Keys & Webhooks → Add Webhook

**IMPORTANT**: Add BOTH webhook URLs to Paystack dashboard!

---

## Security Checklist

- [ ] Using HTTPS URLs only (no http://)
- [ ] Live keys (not test keys) in production environment
- [ ] Webhook secret matches Paystack dashboard
- [ ] Webhook signature verification enabled
- [ ] `PAYSTACK_SECRET_KEY` set as secret env var (not public)
- [ ] `PUBLIC_BASE_URL` points to production domain
- [ ] CORS origins include production frontend domain
- [ ] Database backups enabled on Render

---

## Monitoring

### Render Logs to Watch

**Success patterns**:
```
"Wallet deposit initiated: user_id=123, amount=50000, ref=wallet_deposit_..."
"Payment confirmed and tier upgraded: user_id=123 tier=premium_monthly"
"Wallet deposit confirmed: user_id=123 amount=50000 kobo"
"User 123 withdrew 100000 kobo (fee=1500) → ref=pp_abc123 status=pending"
```

**Error patterns**:
```
"Webhook signature mismatch"  → Check PAYSTACK_WEBHOOK_SECRET
"Paystack initialization failed" → Check PAYSTACK_SECRET_KEY
"Payment provider unavailable" → Paystack API down or key invalid
"Insufficient Paystack balance" → Need to fund Paystack account
```

### Paystack Dashboard Monitoring

1. **Transactions**: Dashboard → Transactions
   - View all deposits and withdrawals
   - Check success/failure rates
   - Export for accounting

2. **Webhooks**: Developers → Webhooks → Logs
   - View webhook delivery status
   - Check for failed deliveries
   - Retry failed webhooks manually

3. **Balance**: Dashboard → Balance
   - Monitor available balance for withdrawals
   - Set up auto-settlement rules
   - Configure balance alerts

---

## Common Production Issues

### Issue: Webhooks Not Received

**Symptoms**: Payment succeeds but wallet not credited

**Debug**:
1. Check Paystack Dashboard → Webhooks → Logs
2. Look for failed delivery (4xx/5xx errors)
3. Verify webhook URL is correct
4. Test webhook endpoint manually (see above)
5. Check Render logs for incoming requests

**Fix**:
- Ensure webhook URL is HTTPS
- Verify Render service is running
- Check webhook secret matches

---

### Issue: Signature Verification Fails

**Symptoms**: Logs show "Webhook signature mismatch"

**Debug**:
1. Check Render environment variables
2. Verify `PAYSTACK_SECRET_KEY` is set correctly (no quotes, no spaces)
3. Check for extra whitespace in env var

**Fix**:
```bash
# On Render, update environment variable (no quotes, no spaces):
PAYSTACK_SECRET_KEY=sk_live_your_actual_key_here
```

---

### Issue: Withdrawals Fail - Insufficient Balance

**Symptoms**: 
- User can't withdraw
- Logs show "Insufficient Paystack balance"

**Cause**: Your Paystack balance is lower than withdrawal amount

**Fix**:
1. Check Paystack Dashboard → Balance
2. Fund Paystack account if needed
3. Or configure auto-settlement to leave buffer balance

---

### Issue: Account Verification Fails

**Symptoms**: User enters bank details but verification fails

**Debug**:
1. Check logs for "Paystack resolve_account failed"
2. Verify user entered correct bank code + account number
3. Test manually:
   ```bash
   curl -X GET "https://api.paystack.co/bank/resolve?account_number=0123456789&bank_code=058" \
     -H "Authorization: Bearer sk_live_xxxxx"
   ```

**Fix**:
- Ask user to double-check account number
- Verify bank code is correct
- Some banks may be temporarily unavailable

---

## Go-Live Checklist

Before enabling payments for real users:

- [ ] All environment variables set on Render
- [ ] Using LIVE Paystack keys (not test)
- [ ] Both webhook URLs configured in Paystack
- [ ] Webhook secret matches on both sides
- [ ] Test deposit with real card (₦100)
- [ ] Test withdrawal to real bank account (₦50)
- [ ] Monitor logs for 24 hours
- [ ] Set up alerts for errors
- [ ] Verify webhook delivery rate >95%
- [ ] Confirm user balances updating correctly
- [ ] Check Paystack dashboard shows transactions
- [ ] Database backups verified

---

## Support Contacts

- **Paystack Support**: support@paystack.com
- **Paystack Docs**: https://paystack.com/docs
- **Render Support**: Via dashboard chat
- **Backend Logs**: https://dashboard.render.com → Your Service → Logs

---

## Quick Reference

| Endpoint | Purpose | Paystack Events |
|----------|---------|----------------|
| `/api/v1/payments/webhook` | Deposits, Subscriptions | `charge.success` |
| `/api/v1/payouts/webhook` | Withdrawals | `transfer.success`, `transfer.failed`, `transfer.reversed` |

| Environment Variable | Example Value | Where to Get |
|---------------------|---------------|--------------|
| `PAYSTACK_PUBLIC_KEY` | `pk_live_xxxxx` | Paystack Dashboard → Settings → API Keys |
| `PAYSTACK_SECRET_KEY` | `sk_live_xxxxx` | Paystack Dashboard → Settings → API Keys (also used for webhook signatures) |
| `PUBLIC_BASE_URL` | `https://pagepay.onrender.com` | Your Render backend URL |
| `FRONTEND_URL` | `pagepay://` | Your app deep link or web URL |
