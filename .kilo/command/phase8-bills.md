# Command: Phase 8 — Bills Payment & VTU (Earn 70% Commission)

**Duration:** Weeks 24–28
**Agents:** Backend + Frontend
**Goal:** Integrate Peyflex bills API for airtime, data, electricity, TV subscriptions. Users pay bills and earn 70% of provider commission in real-time.

---

## Overview
- **Provider**: Peyflex API (https://api.peyflex.com)
- **Services**: Airtime (MTN/Airtel/GLO/9mobile), Data bundles, Electricity (AEDC/EKEDC/IKEDC/etc), TV (DSTV/GOtv/Startimes)
- **Commission Model**: User earns 70% of provider commission, platform keeps 30%
- **Pricing**: All prices fetched from Peyflex API in real-time (no hardcoded values)
- **Payment**: Deducted from user's points balance (100 points = ₦1)
- **Validation**: Phone numbers, meter numbers, smartcard numbers validated before purchase

---

## Backend Tasks

### Step 1: Peyflex Service Integration
- Create `app/services/peyflex.py` with HTTP client
- Environment variables:
  ```
  PEYFLEX_API_KEY
  PEYFLEX_SECRET_KEY
  PEYFLEX_BASE_URL=https://api.peyflex.com/v1
  ```
- Authentication: Bearer token from Peyflex dashboard
- Core methods:
  - `get_airtime_networks()` → list of networks
  - `get_data_plans(network_id)` → data bundles with prices + commission
  - `get_electricity_providers()` → list of discos
  - `get_tv_providers()` → DSTV, GOtv, Startimes
  - `validate_meter(meter_number, disco)` → customer name + address
  - `validate_smartcard(iuc_number, provider)` → customer name + package
  - `purchase_airtime(phone, network, amount)` → transaction result
  - `purchase_data(phone, network, plan_id)` → transaction result
  - `purchase_electricity(meter_number, disco, amount)` → token
  - `purchase_tv(iuc_number, provider, plan_id)` → subscription confirmation

### Step 2: Bill Transaction Schema
- Table `bill_transactions` (already exists in models):
  ```
  id, user_id, service (airtime|data|electricity|tv), provider (peyflex),
  phone, meter_number, smartcard_number,
  amount_naira INTEGER (kobo), commission_naira INTEGER (kobo), points_earned INTEGER,
  reference VARCHAR UNIQUE, status (success|failed|pending),
  external_ref (Peyflex transaction ID), error_message TEXT,
  created_at
  ```
- Points calculation:
  - `commission_naira` comes from Peyflex API response
  - `points_earned = commission_naira * 0.70` (user gets 70%)
  - Platform keeps 30% of commission

### Step 3: Airtime Endpoints
- `GET /api/v1/bills/airtime/networks`:
  - Returns: `[{id, name: "MTN Nigeria", icon_url}]`
- `POST /api/v1/bills/detect-network`:
  - Request: `{phone: "08012345678"}`
  - Local prefix matching (instant, no API call):
    - MTN: 0803, 0806, 0810, 0813, 0814, 0816, 0903, 0906, 0913, 0916
    - Airtel: 0802, 0808, 0812, 0902, 0907, 0912
    - GLO: 0805, 0807, 0811, 0815, 0905, 0915
    - 9mobile: 0809, 0817, 0818, 0908, 0909
  - Returns: `{network: "mtn", display_name: "MTN Nigeria"}`
- `POST /api/v1/bills/airtime/buy`:
  - Request: `{phone, network, amount_kobo}`
  - Validations:
    - Phone: 11 digits, Nigerian format
    - Amount: min ₦50 (5,000 kobo), max ₦5,000
    - Balance check: `user.points_balance >= amount_kobo`
  - Call Peyflex API to purchase
  - Deduct points from wallet
  - Create `BillTransaction` record
  - Credit commission points (70%) to wallet
  - Return: `{success, points_earned, new_balance, transaction_ref}`

### Step 4: Data Bundle Endpoints
- `GET /api/v1/bills/data/networks`:
  - Same as airtime networks
- `GET /api/v1/bills/data/plans?network=mtn_gifting_data`:
  - Fetch from Peyflex: list of data plans with prices + commission
  - Returns: `[{id, name: "1GB - 30 Days", price_kobo, commission_kobo}]`
- `POST /api/v1/bills/data/buy`:
  - Request: `{phone, network, plan_id}`
  - Phone validation (11 digits)
  - Fetch plan price from Peyflex
  - Deduct from wallet, purchase via API
  - Credit 70% of commission
  - Return transaction result

### Step 5: Electricity Endpoints
- `GET /api/v1/bills/electricity/plans`:
  - Returns: `[{id: "aedc_prepaid", name: "AEDC - Prepaid"}, ...]`
- `POST /api/v1/bills/validate-meter`:
  - Request: `{meter_number, disco: "aedc_prepaid"}`
  - Calls Paystack meter validation API (Peyflex doesn't provide this)
  - Returns: `{valid: true, customer_name, address}`
- `POST /api/v1/bills/electricity/buy`:
  - Request: `{meter_number, disco, amount_kobo}`
  - Validations:
    - Meter: 10-13 digits
    - Amount: min ₦1,000 (100,000 kobo)
    - Must validate meter first (enforce in UI)
  - Purchase via Peyflex
  - Peyflex returns electricity token in response
  - Credit 70% commission
  - Return: `{success, token, points_earned, transaction_ref}`

### Step 6: TV Subscription Endpoints
- `GET /api/v1/bills/tv/providers`:
  - Returns: `[{id: "dstv", name: "DSTV"}, {id: "gotv", name: "GOtv"}, ...]`
- `GET /api/v1/bills/tv/plans?provider=dstv`:
  - Fetch from Peyflex: DSTV packages (Compact, Premium, etc) with prices + commission
- `POST /api/v1/bills/validate-smartcard`:
  - Request: `{iuc_number, provider}`
  - Calls Paystack smartcard validation API
  - Returns: `{valid: true, customer_name, current_package}`
- `POST /api/v1/bills/tv/buy`:
  - Request: `{iuc_number, provider, plan_id}`
  - Validations:
    - IUC: 10+ digits
    - Must validate smartcard first
  - Purchase via Peyflex
  - Credit 70% commission
  - Return transaction result

### Step 7: Transaction History
- `GET /api/v1/bills/history`:
  - List user's bill transactions (paginated)
  - Include: service type, amount, commission earned, status, date
  - Filters: service type, date range, status

---

## Frontend Tasks

### Step 1: Buy Airtime Screen
- `app/buy-airtime.tsx`:
  - Phone number input (auto-detect network on blur)
  - Network selector (MTN/Airtel/GLO/9mobile) with icons
  - Quick amount buttons: ₦50, ₦100, ₦200, ₦500, ₦1000
  - Custom amount input field
  - Commission preview: "Earn ₦X back" (calculate from typical 2-5% commission)
  - Balance check before submit
  - Submit → loading → success modal with points earned
  - Validation errors: invalid phone, insufficient balance

### Step 2: Buy Data Screen
- `app/buy-data.tsx`:
  - Phone number input + network detection
  - Data plan selector: dropdown/list of plans with prices
  - Show commission per plan: "Buy 1GB for ₦300, earn ₦21 back"
  - Similar validation as airtime

### Step 3: Buy Electricity Screen
- `app/buy-electricity.tsx`:
  - Meter number input (validate format: 10-13 digits)
  - Disco selector dropdown
  - "Validate Meter" button → calls API, shows customer name
  - Amount input (min ₦1,000)
  - Commission preview
  - Submit → loading → success modal showing token
  - Display token prominently with copy button
  - Validation: meter must be validated before purchase

### Step 4: Buy TV Subscription Screen
- `app/buy-tv.tsx`:
  - Smartcard/IUC number input
  - Provider selector (DSTV/GOtv/Startimes)
  - "Validate Card" button → shows customer name + current package
  - Plan selector: list of packages with prices
  - Commission preview per package
  - Submit → success modal
  - Validation: smartcard must be validated before purchase

### Step 5: Bills Hub (Entry Point)
- Add "Bills" section to wallet tab or create separate tab
- Four cards/buttons:
  - Buy Airtime
  - Buy Data
  - Buy Electricity (Recharge)
  - Pay for TV
- Show recent bill transactions (last 5)
- "View All Transactions" → history screen

### Step 6: Transaction History
- `app/(tabs)/wallet.tsx` → include bill transactions
- Filter: Earned from Ads | Earned from Reading | Earned from Bills
- Each bill transaction shows:
  - Service type icon
  - Amount paid
  - Commission earned (highlighted in green)
  - Status badge
  - Timestamp

### Step 7: Validation UX
- Phone number: strip spaces/dashes automatically, show formatted preview
- Real-time validation: show green checkmark when valid
- Network detection: instant feedback as user types
- Meter/smartcard validation: loading spinner → success (customer name) or error
- Disable submit button until all validations pass

---

## Acceptance Criteria (Phase 8 Complete)
✅ User can buy airtime for any Nigerian network (MTN/Airtel/GLO/9mobile)
✅ User can buy data bundles with real-time pricing from Peyflex
✅ User can recharge electricity (prepaid) and receive token
✅ User can pay for TV subscription (DSTV/GOtv/Startimes)
✅ Phone network auto-detected from prefix (instant, no API call)
✅ Meter number validated via Paystack API (shows customer name)
✅ Smartcard validated via Paystack API (shows customer name)
✅ Commission calculated correctly: user gets 70%, platform keeps 30%
✅ Points deducted from wallet, commission credited instantly
✅ Transaction history shows all bills with earned commission
✅ All validations prevent invalid purchases (wrong format, insufficient balance)
✅ Error handling: Peyflex API failures show user-friendly messages
✅ All Phase 1-7 tests still pass
✅ E2E: User funds wallet → buys airtime → earns commission → balance updated correctly
✅ No TODO comments, placeholder strings, or mock data in committed code

---

## Implementation Notes
1. **Commission varies by service**: Peyflex returns commission per transaction; don't hardcode rates
2. **Validation is mandatory**: Always validate meter/smartcard before purchase to prevent failed transactions
3. **Error messages**: Peyflex errors should be user-friendly, not raw API responses
4. **Testing**: Use Peyflex sandbox/test mode during development
5. **Rate limiting**: Implement per-user limits to prevent abuse (e.g., max 20 purchases/day)
6. **Receipts**: Generate PDF/image receipt for each successful purchase (Phase 9 feature)
