# PagePay Wallet System (SP + CB) — Complete Implementation Guide

This document is the single source of truth for the wallet system in `app/backend` (file-by-file). It covers balances, the auditable ledger, SP/CB flows, CB→SP conversion, study-asset unlock gating, endpoints, config, and verification. **Paystack is intentionally deferred** until the wallet is confirmed 100% working.

## Table of Contents
1. [Model & decisions](#1-model--decisions)
2. [Project structure (wallet/study-unlock files)](#2-project-structure)
3. [Environment variables](#3-environment-variables)
4. [Configuration](#4-configuration-coreconfigpy)
5. [Database models](#5-database-models)
6. [Schemas](#6-schemas)
7. [Repository](#7-repository)
8. [Services & atomicity](#8-services--atomicity)
9. [Controllers](#9-controllers)
10. [Routers / endpoints](#10-routers--endpoints)
11. [Study integration (unlock gating)](#11-study-integration-unlock-gating)
12. [Wiring (main, exports)](#12-wiring)
13. [Alembic migration](#13-alembic-migration)
14. [Security notes](#14-security-notes)
15. [End-to-end verification](#15-end-to-end-verification)
16. [Paystack handoff (next phase)](#16-paystack-handoff-next-phase)

---

## 1. Model & decisions

| Concept | Meaning | Storage |
|---|---|---|
| **SP** (service points) | Non-cashable points. Earned from **ads** and **SP purchases** (Paystack later / grant path now). **Spent to unlock** study assets (MCQ, flashcard, essay). | `users.service_credit_balance` (integer points, denormalized) + `wallet_ledger` rows (`currency='SP'`). |
| **CB** (cashable balance) | Cashable wallet balance. Funded by **deposits** (Paystack later) separately from SP. Never spent on study unlocks. | `users.cashable_balance` (**kobo**, integer, denormalized) + `wallet_ledger` rows (`currency='CB'`). |
| **Legacy** | `users.points_balance` mirrored (non-authoritative) for compatibility. | `users.points_balance`. |

**Acquisition (confirmed):**
- Users **earn SP** from ads and purchases; they can buy SP and can fund their wallet separately. **SP purchases credit SP balance; deposit funds credit CB.**
- **CB→SP conversion** is supported (rate-configurable). Direct “SP pack” purchase credit is also supported via the same SP-credit path (Paystack will trigger it later).

**Unlock:** each `StudyAsset.points_to_unlock` (default 50). Unlock is **per asset, per user, idempotent** (`study_unlocks` unique `(user_id, asset_id)`), debits SP atomically, and returns/gates content.

---

## 2. Project structure

```
app/backend/app/
  core/config.py                      # sp_per_naira, study_unlock_default_points, wallet_grant_secret
  models/wallet.py                    # WalletLedger, StudyUnlock
  models/__init__.py                  # exports WalletLedger, StudyUnlock
  schemas/wallet.py                   # balance/ledger/earn/convert/grant DTOs
  schemas/study_unlock.py             # UnlockResponse
  schemas/__init__.py                 # exports wallet + unlock schemas
  repositories/wallet_repository.py   # ledger lookup/list, get_unlock
  repositories/study_asset_queries.py # list assets for material (gating)
  services/wallet_service.py          # atomic SP/CB credit/debit, conversion, balance/history
  services/study_unlock_service.py    # ownership + idempotent unlock + SP debit
  controllers/wallet_controller.py    # wallet orchestration + grant-secret guard
  controllers/study_controller.py     # generate returns locked; material lists assets+unlocked; unlock
  routers/wallet.py                   # /api/v1/wallet/*
  routers/study.py                    # + POST /api/v1/study/assets/{asset_id}/unlock
  routers/__init__.py                 # exports wallet
  main.py                             # registers wallet model + wallet router
alembic/versions/0a1b2c3d4e5f_add_wallet_ledger_and_study_unlocks.py
app/docs/wallet-system-complete-guide.md
```

---

## 3. Environment variables

Add to `app/backend/.env` (and `.env.example`):

```env
# --- Wallet (SP/CB, pre-Paystack) ---
SP_PER_NAIRA=10                      # conversion rate: 10 SP per ₦1
STUDY_UNLOCK_DEFAULT_POINTS=50       # default asset unlock cost (assets carry points_to_unlock)
WALLET_GRANT_SECRET=change-me        # guards POST /api/v1/wallet/*/grant (pre-Paystack/dev); unset => grants disabled
```

- **Rate:** `SP = floor(cb_kobo * SP_PER_NAIRA / 100)` (CB is kobo; 10,000 kobo = ₦100 → 1,000 SP at rate 10).
- `WALLET_GRANT_SECRET` must be set for grant endpoints to work and must **never** be exposed to clients.

---

## 4. Configuration (`core/config.py`)

Settings (Pydantic, `extra="ignore"`): `sp_per_naira: int = 10`, `study_unlock_default_points: int = 50`, `wallet_grant_secret: str | None = None`.

---

## 5. Database models

### `app/models/wallet.py`
- **`WalletLedger`** (`wallet_ledger`): `id`, `user_id`, `currency` (`SP`|`CB`), `direction` (`credit`|`debit`), `amount` (>0, integer; SP=points, CB=kobo), `balance_after`, `source`, `reference_type`, `reference_id`, `idempotency_key` (**unique**, nullable), `metadata_json`, `created_at`. Indexed on user/currency/source/created_at/idempotency_key.
- **`StudyUnlock`** (`study_unlocks`): `id`, `user_id`, `asset_id`, `material_id`, `points_spent`, `created_at`, `UNIQUE(user_id, asset_id)=uq_study_unlock_user_asset`.

### Existing (`app/models/user.py`)
`service_credit_balance` (SP), `cashable_balance` (CB), `points_balance` (legacy) already present; wallet updates them.

---

## 6. Schemas

- `schemas/wallet.py`: `WalletBalanceResponse` (SP, CB kobo, legacy, rate, default unlock cost), `LedgerEntry`/`LedgerListResponse` (cursor=`next_cursor` id), `AdRewardClaimRequest{claim_id, amount_sp}`, `ConvertCbToSpRequest{amount_cb_kobo>=100}`, `GrantCbRequest{amount_cb_kobo, reference, grant_secret}`, `GrantSpPurchaseRequest{amount_sp, reference, grant_secret}`.
- `schemas/study_unlock.py`: `UnlockResponse{unlocked, asset_id, material_id, points_spent, new_sp_balance, content?, method}`.
- `schemas/study.py` (updated): `GenerateAssetResponse` now returns **locked** asset metadata (`asset_id`, `points_to_unlock`, `unlocked=false`, no `assets` payload); `MaterialSummary.asset_types[]`; `MaterialDetail.assets[]` with per-asset `unlocked` and `content` only when unlocked.

---

## 7. Repository (`repositories/wallet_repository.py`)

`ledger_by_idempotency(key)`, `list_ledger(user_id, currency?, limit, cursor)`, `get_unlock(user_id, asset_id)`. Study listing helper: `repositories/study_asset_queries.list_assets_for_material`.

---

## 8. Services & atomicity

### `services/wallet_service.py` (core)
- **Locking:** `_locked_user` uses `SELECT ... FOR UPDATE` on `users` for mutations.
- **Ledger = audit truth; denormalized balances updated with each row.**
- **Idempotency:** optional `idempotency_key` (unique). For keyed ops (ad reward, grants) an existing key returns the prior result with `applied=false` (no double credit). Study unlock uses `idempotency_key=f"study_unlock_sp:{user_id}:{asset_id}"` on the SP debit and the `study_unlocks` unique row.
- **Methods:** `get_balance`, `list_transactions(cursor/limit)`, `_credit_sp/_debit_sp/_credit_cb/_debit_cb` (atomic), `claim_ad_reward` (idempotent by `claim_id`), `grant_cb` (idempotent by `reference`, `source=deposit_grant`), `grant_sp_purchase` (idempotent, `source=sp_purchase`), `convert_cb_to_sp` (**single atomic transaction**: lock user, validate CB, debit CB + credit SP + 2 ledger rows + commit).
- **Conversion:** `cb_kobo_to_sp = floor(amount_cb_kobo * sp_per_naira / 100)`.
- **Errors:** insufficient SP/CB → **402** with `required/balance` detail; not found → 404; bad input → 400.

### `services/study_unlock_service.py`
Loads asset + verifies material ownership → if unlocked returns content (`method=already_unlocked`, idempotent) → debits SP (`source=study_unlock`) → inserts `StudyUnlock` → returns content + new SP balance. (Unlock record insert + debit are sequenced; debit is idempotent-keyed to prevent double spend on retry paths.)

---

## 9. Controllers

- `wallet_controller.py`: guards grants via `wallet_grant_secret` (403 if missing/invalid), delegates to `WalletService`.
- `study_controller.py`: `generate_asset` now **persists asset and returns locked metadata** (no content leak); `get_material` returns `assets[]` with `unlocked` and content only when unlocked; `unlock_asset` delegates to `StudyUnlockService`.

---

## 10. Routers / endpoints

All under `/api/v1`, bearer-authenticated (`get_current_user`).

### Wallet (`/wallet`, tag `wallet`)
| Method | Path | Purpose |
|---|---|---|
| GET | `/wallet/balance` | SP, CB (kobo), legacy mirror, rate, default unlock cost. |
| GET | `/wallet/transactions?currency=SP\|CB&limit=&cursor=` | Paginated ledger (desc), `next_cursor`. |
| POST | `/wallet/sp/ad-reward` | Body `{claim_id, amount_sp}`. Idempotent SP credit (`source=ad_reward`). |
| POST | `/wallet/cb/convert-to-sp` | Body `{amount_cb_kobo}`. Atomic CB→SP at `sp_per_naira`. |
| POST | `/wallet/cb/grant` | **Guarded** (`wallet_grant_secret`). Pre-Paystack/dev CB credit (`source=deposit_grant`, idempotent `reference`). |
| POST | `/wallet/sp/grant-purchase` | **Guarded**. Pre-Paystack/dev SP purchase credit (`source=sp_purchase`, idempotent `reference`). Paystack will reuse this credit path. |

### Study (`/study`)
| Method | Path | Purpose |
|---|---|---|
| POST | `/study/generate` | Generates asset, returns **locked** metadata (no content) + `points_to_unlock`. |
| GET | `/study/materials/{id}` | Includes `assets[]` with `unlocked`; `content` only if unlocked. |
| POST | `/study/assets/{asset_id}/unlock` | Spends SP (`points_to_unlock`), idempotent; returns `content` + `new_sp_balance`. 402 insufficient SP, 404 not owned/found. |

---

## 11. Study integration (unlock gating)

- **Generation no longer leaks content:** response is `{material_id, asset_id, asset_type, points_to_unlock, unlocked:false}`.
- **Material detail** lists assets with per-user `unlocked`; full `content` only when an unlock row exists.
- **Unlock** enforces ownership (asset’s material belongs to user), idempotency, and atomic SP debit. Essay AI review remains available (it operates on submitted text/material context), not on locked generated asset content.

---

## 12. Wiring

- `main.py`: imports `app.models.wallet` (registers tables), includes `wallet.router` (`/api/v1`). `create_all` wrapped to tolerate multi-worker race duplicate-type errors (dev convenience); Alembic is the migration source of truth.
- `models/__init__.py`, `routers/__init__.py`, `schemas/__init__.py` export wallet/unlock symbols.

---

## 13. Alembic migration

- `alembic/versions/0a1b2c3d4e5f_add_wallet_ledger_and_study_unlocks.py` (`Revises: 0565d20229a6`) creates `wallet_ledger` + `study_unlocks` (idempotent `has_table` checks). Apply in Docker when needed:
  ```powershell
  docker exec backend-api-1 alembic upgrade head
  ```
  (Tables may already exist via `create_all`; migration is safe/idempotent.)

---

## 14. Security notes

- Grant endpoints are **server-secret guarded** and require auth; disable by unsetting `WALLET_GRANT_SECRET`. Remove/lock down before production exposure; **Paystack webhook verification** will replace open grants for real funding.
- CB never decreases for study unlocks; SP debits are balance-checked under row lock. Ledger `idempotency_key` prevents double credit/spend on retries.
- `.env` is gitignored (see `app/.gitignore`); rotate any secrets ever committed.

---

## 15. End-to-end verification (Docker + Neon, test user 53)

Rebuild: `docker compose -f "C:\Users\kenik\OneDrive\Desktop\pg\app\backend\docker-compose.yml" up -d --build`.

Verified results:
- `GET /wallet/balance` → SP/CB/rate OK (`sp_per_naira=10`).
- `POST /wallet/sp/ad-reward` `{claim_id,amount_sp}` → `applied:true`; repeat same `claim_id` → `applied:false`, same ledger/balance (idempotent).
- `POST /wallet/cb/grant` (secret) → CB credited (kobo); repeat same `reference` → `applied:false`.
- `POST /wallet/cb/convert-to-sp` `{amount_cb_kobo:10000}` → `credited_sp:1000`, CB debited, SP credited (atomic).
- `POST /wallet/sp/grant-purchase` → SP credited (pre-Paystack purchase path).
- `GET /wallet/transactions` → auditable rows with `balance_after`/source/reference.
- `POST /study/generate` behavior changed to **locked** metadata; `GET /study/materials/{id}` shows `assets[].unlocked/content` gated.
- `POST /study/assets/{id}/unlock` → SP debited (50), content returned, `method=points`; repeat → `already_unlocked`, no extra debit; expensive asset → **402** insufficient SP with `required_sp/balance_sp`.
- CB/SP separation preserved (unlocks affect SP/legacy mirror only; CB unchanged).

---

## 16. Paystack handoff (next phase)

1. **Initialize/verify/webhook** (Paystack) → on confirmed deposit call `WalletService._credit_cb` / `grant_cb`-equivalent with Paystack `reference` as idempotency key (`source=wallet_deposit`) — **credits CB (kobo)**.
2. **Buy SP with money** (chosen flow): fund CB then `POST /wallet/cb/convert-to-sp`, OR sell SP packs where verified payment credits SP via `grant_sp_purchase`-equivalent (`source=sp_purchase`) — **never mix into CB**.
3. Reuse the same ledger/idempotency primitives; keep conversion rate in config and amounts in kobo/SP integers.
