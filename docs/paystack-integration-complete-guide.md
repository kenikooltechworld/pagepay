# PagePay Paystack Integration (CB wallet deposits) — app/backend

## Overview
- Funds **cashable balance (CB, kobo)** via Paystack. (SP is earned/purchased separately and never funded by CB deposits unless converted via `/wallet/cb/convert-to-sp`.)
- Flow: client calls deposit init → Paystack checkout (`authorization_url`) → Paystack sends `charge.success` to the **paystack-router Worker** (one dashboard webhook URL) → router forwards `pp_*` refs to backend webhook → backend **re-verifies `X-Paystack-Signature` (HMAC-SHA512, raw body, `PAYSTACK_SECRET_KEY`)** and credits CB **idempotently** by reference via the unified wallet ledger.

## Components (file-by-file)
- `app/core/config.py`: `paystack_secret_key`, `paystack_public_key`, `paystack_base_url`, `paystack_http_timeout_seconds`, `paystack_callback_path` (+ wallet/bonus/referral vars). `Settings(extra="ignore")`.
- `app/services/paystack_service.py`: `initialize_transaction` (`pp_` refs created by controller) + `verify_webhook_signature(raw, X-Paystack-Signature)` (constant-time compare). Detailed info/error logs (no secret values logged).
- `app/models/payment.py`: `Payment` (`purpose=wallet_deposit_cb`, `amount_kobo` charged, `credit_amount_kobo` CB credited, `provider_tx_ref` unique reference, `status`, `webhook_confirmed`, `payment_metadata`). Registered in `app/models/__init__.py`; `app/main.py` imports it for `create_all`.
- `app/controllers/payment_controller.py`: `init_wallet_deposit` (builds `pp_wallet_{user_id}_{uuid16}`, Paystack init, persists pending `Payment`, returns `authorization_url`); `handle_webhook` (raw-body verify → parse → `charge.success` → amount check → idempotent CB credit `source=wallet_deposit` ref `paystack` → marks payment success). Verbose logs at each decision.
- `app/services/wallet_service.py`: `credit_wallet_deposit` → `_credit_cb` with `idempotency_key=wallet_deposit:{reference}` (ledger + `cashable_balance` atomic).
- `app/routers/payments.py`: `POST /api/v1/payments/paystack/deposit` (auth, init), aliases `POST /api/v1/payments/paystack/webhook` and `POST /api/v1/payments/webhook`.
- `app/routers/payouts.py`: **`POST /api/v1/payouts/webhook`** — alias matching the deployed `app/paystack-router` `pp_` route target (`https://pagepay.onrender.com/api/v1/payouts/webhook`).
- `app/routers/wallet.py`: `POST /api/v1/wallet/deposit` (auth, init) + `POST /api/v1/wallet/deposit/webhook` alias.
- `app/core/logging_middleware.py` + `app/main.py`: request/response logging for **all** HTTP endpoints (method/path/query/client/ua, bodies, status, duration_ms). **Redacts** passwords, pins, tokens, secrets, api keys, grant secrets, firebase key, etc. Endpoint-level info/error logs added across wallet/study/payments/auth actions; Paystack uses detailed decision logs. Logs emit to stdout (Docker/Render).

## Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/v1/wallet/deposit` | bearer | Init Paystack CB deposit (`amount_kobo>=100`), returns `authorization_url`, `reference` (`pp_wallet_...`). |
| POST | `/api/v1/payments/paystack/deposit` | bearer | Same init (alt path). |
| POST | `/api/v1/payouts/webhook` | signature | **Primary** Paystack webhook target (paystack-router). |
| POST | `/api/v1/wallet/deposit/webhook` | signature | Alias. |
| POST | `/api/v1/payments/paystack/webhook` | signature | Alias. |

## Env / deploy
- **Backend (Render/local `.env`)**: `PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY` (use `sk_test_`/`pk_test_` first), `PAYSTACK_BASE_URL=https://api.paystack.co`, `PUBLIC_BASE_URL=https://pagepay.onrender.com` (redirect `callback_url` base), `FRONTEND_URL`, `DATABASE_URL` (Neon). `.env` is gitignored; set secrets in Render dashboard.
- **paystack-router Worker** (`app/paystack-router/src/index.ts`): `pp_` → `https://pagepay.onrender.com/api/v1/payouts/webhook` (deployed to `https://paystack-webhook-router.kenikool.workers.dev`). Worker secret `PAYSTACK_SECRET_KEY` must match the Paystack account/mode. Dashboard webhook URL = the Worker URL (one per account).
- **Deploy backend** to Render (Docker, `app.main:socket_app`, `rootDir app/backend`) and verify `/api/v1/health`, `/api/v1/health/db`.

## Idempotency & safety
- `Payment.provider_tx_ref` unique; `webhook_confirmed`/`status` guard duplicates. CB credit uses `idempotency_key=wallet_deposit:{reference}` in `wallet_ledger` (unique) — duplicate/replayed `charge.success` does not double-credit.
- Backend re-verifies the forwarded signature (defense in depth) and rejects amount mismatches. CB only (kobo integers).

## Extensibility (not in this slice)
- **SP-pack purchase (paid):** on verified charge for an SP-pack ref/purpose, credit SP via `WalletService` `sp_purchase` (idempotent) — never CB. (Out of scope now; wallet has the SP credit path.)
- Non-`charge.success` events and refunds/chargebacks not fully handled beyond logging/ignore.

## Troubleshooting (logs)
- Search Render/Docker logs for: `endpoint.payments.*`, `endpoint.wallet.deposit`, `endpoint.payouts.webhook`, `paystack.initialize *`, `paystack.webhook *` (received/sig/event/ref/credit/applied/duplicate/amount_mismatch/unknown_reference), and `REQ/RES` lines from `RequestLogMiddleware` (includes redacted bodies, status, duration). Secrets/tokens/pins/passwords are redacted as `***REDACTED***`.
