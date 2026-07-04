# Payment/Subscription Management API Reference

**Base URL**: `http://localhost:8000/api/v1/admin/payments`  
**Authentication**: Bearer JWT (via admin_session cookie or Authorization header)  
**Module**: `backend/app/routers/admin_payments.py`

---

## Endpoints

### 1. List All Premium Subscriptions

**Endpoint**: `GET /subscriptions`

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `status_filter` | string | No | Filter by status: `success`, `failed`, `pending` |
| `page` | integer | Yes (default: 1) | Page number (1-indexed) |
| `limit` | integer | Yes (default: 50) | Items per page (1-200) |

**Permissions Required**: `finance.view`

**Response** (200 OK):
```json
{
  "items": [
    {
      "id": 1,
      "user_id": 42,
      "user_email": "user@example.com",
      "tier": "pro",
      "amount_kobo": 50000,
      "amount_ngn": 500.00,
      "provider": "paystack",
      "provider_tx_ref": "pay_xxxxx",
      "status": "success",
      "webhook_confirmed": true,
      "created_at": "2026-07-03T10:30:00Z",
      "confirmed_at": "2026-07-03T10:35:00Z"
    }
  ],
  "total": 142,
  "page": 1,
  "limit": 50
}
```

**Example**:
```bash
curl "http://localhost:8000/api/v1/admin/payments/subscriptions?page=1&limit=20"
```

---

### 2. Get Subscription Details

**Endpoint**: `GET /subscriptions/{payment_id}`

**Path Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `payment_id` | integer | Yes | Payment ID |

**Permissions Required**: `finance.view`

**Response** (200 OK):
```json
{
  "id": 1,
  "user_id": 42,
  "user_email": "user@example.com",
  "user_tier_current": "pro",
  "subscription_expires_at": "2026-10-03T10:35:00Z",
  "tier": "pro",
  "amount_kobo": 50000,
  "amount_ngn": 500.00,
  "provider": "paystack",
  "provider_tx_ref": "pay_xxxxx",
  "status": "success",
  "webhook_confirmed": true,
  "created_at": "2026-07-03T10:30:00Z",
  "confirmed_at": "2026-07-03T10:35:00Z"
}
```

**Errors**:
- 404: Payment not found
- 401: Unauthorized

**Example**:
```bash
curl "http://localhost:8000/api/v1/admin/payments/subscriptions/1"
```

---

### 3. Refund Payment

**Endpoint**: `POST /subscriptions/{payment_id}/refund`

**Path Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `payment_id` | integer | Yes | Payment ID to refund |

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `reason` | string | Yes | Reason for refund (e.g., "customer_request", "duplicate", "error") |

**Permissions Required**: `finance.approve` (higher privilege)

**Response** (200 OK):
```json
{
  "success": true,
  "message": "Payment refunded successfully",
  "refund_reference": "PAYSTACK_REFUND_REF_xxxxx",
  "amount_refunded_kobo": 50000
}
```

**Errors**:
- 400: Cannot refund failed payment
- 400: Cannot refund pending payment (must wait for confirmation)
- 400: Payment already refunded
- 400: Paystack refund failed (with Paystack error details)
- 404: Payment not found
- 401: Unauthorized (requires finance.approve)

**Side Effects**:
- Calls Paystack API to process refund
- Sets user `tier` to "free"
- Sets user `subscription_expires_at` to NULL
- Creates audit log entry

**Example**:
```bash
curl -X POST "http://localhost:8000/api/v1/admin/payments/subscriptions/1/refund?reason=customer_request"
```

---

### 4. List Failed Payments

**Endpoint**: `GET /failed`

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `page` | integer | Yes (default: 1) | Page number (1-indexed) |
| `limit` | integer | Yes (default: 50) | Items per page (1-200) |

**Permissions Required**: `finance.view`

**Response** (200 OK):
```json
{
  "items": [
    {
      "id": 2,
      "user_id": 43,
      "user_email": "failed_user@example.com",
      "tier": "pro",
      "amount_kobo": 50000,
      "amount_ngn": 500.00,
      "provider": "paystack",
      "provider_tx_ref": "pay_yyyyy",
      "created_at": "2026-07-02T15:20:00Z"
    }
  ],
  "total": 8,
  "page": 1,
  "limit": 50
}
```

**Use Cases**:
- Monitor payment failures
- Contact users about failed transactions
- Retry payment collection

**Example**:
```bash
curl "http://localhost:8000/api/v1/admin/payments/failed?page=1"
```

---

### 5. List Active Premium Users

**Endpoint**: `GET /subscriptions/active`

**Query Parameters**:
| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `page` | integer | Yes (default: 1) | Page number (1-indexed) |
| `limit` | integer | Yes (default: 50) | Items per page (1-200) |

**Permissions Required**: `finance.view`

**Response** (200 OK):
```json
{
  "items": [
    {
      "id": 42,
      "email": "user@example.com",
      "tier": "pro",
      "subscription_expires_at": "2026-10-03T10:35:00Z",
      "days_remaining": 92
    },
    {
      "id": 99,
      "email": "premium@example.com",
      "tier": "premium_plus",
      "subscription_expires_at": "2026-09-15T14:22:00Z",
      "days_remaining": 74
    }
  ],
  "total": 156,
  "page": 1,
  "limit": 50
}
```

**Use Cases**:
- View all active subscriptions
- Monitor subscription expiry
- Plan churn prevention campaigns
- Revenue dashboards

**Example**:
```bash
curl "http://localhost:8000/api/v1/admin/payments/subscriptions/active?page=1&limit=25"
```

---

## Authentication

All endpoints require authentication. Choose one:

### Option 1: Using Cookie (Recommended)
After logging in, the session cookie is automatically sent:
```bash
curl -b "admin_session=TOKEN" "http://localhost:8000/api/v1/admin/payments/subscriptions"
```

### Option 2: Using Authorization Header
```bash
curl -H "Authorization: Bearer TOKEN" "http://localhost:8000/api/v1/admin/payments/subscriptions"
```

### Get Admin Token
```bash
curl -X POST "http://localhost:8000/api/v1/admin/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@pagepay.dev",
    "password": "your_password"
  }'
```

---

## Error Handling

### Common HTTP Status Codes

| Status | Meaning | Example |
|--------|---------|---------|
| 200 | Success | Payment refunded |
| 400 | Bad request | Invalid payment ID, cannot refund failed payment |
| 401 | Unauthorized | Missing/invalid token |
| 403 | Forbidden | User lacks required permission |
| 404 | Not found | Payment ID doesn't exist |
| 429 | Rate limited | Too many requests |
| 500 | Server error | Database error, Paystack service down |

### Error Response Format
```json
{
  "detail": "string explaining the error"
}
```

---

## Permissions Matrix

| Endpoint | Method | Permission | Role |
|----------|--------|-----------|------|
| `/subscriptions` | GET | finance.view | finance_team |
| `/subscriptions/{id}` | GET | finance.view | finance_team |
| `/subscriptions/{id}/refund` | POST | finance.approve | finance_admin |
| `/failed` | GET | finance.view | finance_team |
| `/subscriptions/active` | GET | finance.view | finance_team |

**Note**: Only admins with `finance.approve` permission can refund payments.

---

## Integration with Admin Panel

### Frontend Page: `admin/src/features/payments/PaymentPage.tsx`
This page displays payment/subscription data fetched from these endpoints.

**Features**:
- List all subscriptions with pagination
- Filter by status
- View payment details
- Refund payments (with confirmation)
- Monitor failed transactions
- Track active premium users

---

## Data Model Reference

### Payment Model
```python
class Payment(Base):
    __tablename__ = "payments"
    
    id: int                        # Primary key
    user_id: int                   # FK to User
    tier: str                      # "free", "pro", "premium_plus"
    amount_kobo: int               # Amount in kobo (1 NGN = 100 kobo)
    provider: str                  # "paystack"
    provider_tx_ref: str           # Paystack transaction reference
    status: str                    # "success", "failed", "pending"
    webhook_confirmed: bool        # Whether Paystack webhook confirmed
    created_at: datetime           # When payment was initiated
    confirmed_at: datetime         # When payment was confirmed
```

---

## Notes

1. **Amounts are in Kobo**: 1 NGN = 100 kobo. Divide by 100 to get NGN.
2. **All timestamps are UTC**: Use `.isoformat()` format.
3. **Paystack Integration**: Refunds are processed via live Paystack API (not mocked).
4. **Audit Logging**: All admin actions (refunds, etc.) are logged to `AdminAuditLog`.
5. **Idempotency**: Attempting to refund an already-refunded payment returns 400 error.

---

## Testing

### Quick Test Scripts

**Test 1: List subscriptions**
```bash
curl "http://localhost:8000/api/v1/admin/payments/subscriptions?page=1&limit=5"
```

**Test 2: Get payment details**
```bash
curl "http://localhost:8000/api/v1/admin/payments/subscriptions/1"
```

**Test 3: List active subscriptions**
```bash
curl "http://localhost:8000/api/v1/admin/payments/subscriptions/active?page=1"
```

**Test 4: List failed payments**
```bash
curl "http://localhost:8000/api/v1/admin/payments/failed"
```

**Test 5: Refund a payment (admin only)**
```bash
curl -X POST "http://localhost:8000/api/v1/admin/payments/subscriptions/1/refund?reason=customer_request"
```

---

**File**: `backend/app/routers/admin_payments.py` (291 lines)  
**Last Updated**: July 3, 2026  
**Status**: Production Ready ✅
