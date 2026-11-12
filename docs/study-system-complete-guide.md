# PagePay Study System — Implementation Guide

This document describes the **study** implementation in `app/backend` as currently implemented (router, controller, schemas, models, repositories, services, and related config). It is intended as a source-of-truth reference for frontend integration and maintenance.

## Table of Contents
1. [Overview](#1-overview)
2. [Wiring & base path](#2-wiring--base-path)
3. [Architecture / key files](#3-architecture--key-files)
4. [Data models](#4-data-models)
5. [Configuration & environment](#5-configuration--environment)
6. [Authentication & access control](#6-authentication--access-control)
7. [Endpoints](#7-endpoints)
8. [AI behavior](#8-ai-behavior)
9. [Unlock & SP integration](#9-unlock--sp-integration)
10. [Error behavior](#10-error-behavior)
11. [Rate limiting](#11-rate-limiting)
12. [Current limitations / notes](#12-current-limitations--notes)

---

## 1. Overview

The study feature lets an authenticated user:
- Upload study material as **text** or as a **file** (`pdf`, `docx`, `txt`, `md`; text extracted server-side).
- List, retrieve, update, and delete their own materials.
- Generate AI study assets (**MCQ**, **flashcards**, **essay questions**) from a material, with `topic` and `difficulty` applied to prompts and persisted on the asset. Generated assets are stored but returned as **locked** until unlocked with Service Points (SP).
- Update asset metadata (topic) and delete assets they own.
- Unlock a generated asset by spending SP (atomic, idempotent), which returns the asset content.
- Submit an essay for AI review/feedback tied to a material they own, optionally reviewed against a **specific generated essay question** (`asset_id` + `question_index`).

Study assets are gated by SP and integrate with the wallet/unlock system (`StudyUnlockService`, `wallet_ledger`, `study_unlocks`).

---

## 2. Wiring & base path

- **Router:** `app/routers/study.py` — `APIRouter(prefix="/study", tags=["study"])`
- **Registered in:** `app/main.py` — `app.include_router(study.router, prefix="/api/v1")`
- **Effective base path:** `/api/v1/study`
- **Auth dependency:** all endpoints use `Depends(get_current_user)` from `app.services.auth_service`.
- **Rate limiting:** routes use `limiter` from `app.limiter` (keyed by user id or IP).

---

## 3. Architecture / key files

| Layer | File | Responsibility |
|---|---|---|
| Router | `app/routers/study.py` | HTTP routes, request parsing (JSON/multipart), rate limits; delegates to controller |
| Controller | `app/controllers/study_controller.py` | Use-case orchestration, ownership checks, AI prompt selection/calls, CRUD, response shaping, logging |
| Schemas | `app/schemas/study.py` | Request/response DTOs for materials, file upload context, updates, generation, essay submit/review |
| Schema | `app/schemas/study_unlock.py` | `UnlockResponse` DTO |
| Models | `app/models/study.py` | `StudyMaterial`, `StudyAsset` ORM models |
| Model (related) | `app/models/wallet.py` | `StudyUnlock`, `WalletLedger` (unlock/idempotency & SP debit audit) |
| Repository | `app/repositories/study_repository.py` | CRUD/list for `StudyMaterial`, `StudyAsset` (with update/delete support) |
| Repository helper | `app/repositories/study_asset_queries.py` | List assets for a material (ordered by id) |
| Repository (related) | `app/repositories/wallet_repository.py` | Unlock lookup/list and unlock-row cleanup for deletes |
| Service | `app/services/study_file_service.py` | Upload validation and text extraction for `pdf`/`docx`/`txt`/`md` |
| Service | `app/services/study_unlock_service.py` | Ownership check, idempotent unlock, atomic SP debit + unlock record |
| Service | `app/services/ai_service.py` | Cloudflare Workers AI call and JSON parsing |
| Config | `app/core/config.py` | `study_unlock_default_points`, etc. |

---

## 4. Data models

### 4.1 `study_materials` (`app/models/study.py` — `StudyMaterial`)
| Field | Type | Notes |
|---|---|---|
| `id` | int PK, autoincrement | |
| `user_id` | BigInteger, indexed | Owner |
| `title` | String(500) | |
| `exam_type` | String(32), nullable | Optional label |
| `education_level` | String(50), default `'primary'` | DB default `'primary'`; API may set provided value or null |
| `raw_input` | Text | Raw/source text (text upload or extracted text) |
| `parsed_structure` | Text, nullable | JSON string if populated (not set by current flows) |
| `explanation_structure` | Text, nullable | Not set by current flows |
| `content` | Text, nullable | Working text used for generation/review (kept in sync with updates) |
| `original_file_data` | LargeBinary, nullable | Stored for file uploads |
| `file_mime_type` | String(128), nullable | Stored for file uploads |
| `ai_model_used` | String(100), nullable | Not set by current flows |
| `page_count` | int, default 0 | Set for file uploads (best-effort for docx/txt) |
| `figure_count` | int, default 0 | |
| `created_at` | DateTime, default `utcnow` | |

### 4.2 `study_assets` (`app/models/study.py` — `StudyAsset`)
| Field | Type | Notes |
|---|---|---|
| `id` | int PK, autoincrement | |
| `material_id` | BigInteger, indexed | Reference to `study_materials.id` |
| `asset_type` | String(50) | `mcq`, `flashcard`, or `essay` |
| `topic` | String(200), nullable | **Persisted** from generate request (and updatable via PATCH) |
| `content_json` | Text | JSON string of AI-generated content |
| `points_to_unlock` | int, default 50 | Set from `settings.study_unlock_default_points` at generation |
| `created_at` | DateTime, default `utcnow` | |

### 4.3 Related (wallet/unlock)
- **`study_unlocks`** (`StudyUnlock`): per-user unlock record, `UNIQUE(user_id, asset_id)`; stores `asset_id`, `material_id`, `points_spent`, `created_at`. Makes unlocks idempotent.
- **`wallet_ledger`**: SP debit recorded on unlock (`currency='SP'`, `direction='debit'`, `source='study_unlock'`, idempotency key `study_unlock_sp:{user_id}:{asset_id}`).
- **`users`**: denormalized balances updated atomically on unlock (`service_credit_balance` / `points_balance` adjusted; see `StudyUnlockService`).

---

## 5. Configuration & environment

From `app/core/config.py` / environment:

| Setting / env | Default | Purpose |
|---|---:|---|
| `STUDY_UNLOCK_DEFAULT_POINTS` (`study_unlock_default_points`) | `50` | `points_to_unlock` assigned to newly generated assets |
| `CLOUDFLARE_ACCOUNT_ID` | — | Required by `ai_service` to call Cloudflare Workers AI |
| `CLOUDFLARE_API_TOKEN` | — | Bearer token for Cloudflare Workers AI |

AI service constants (`app/services/ai_service.py`): base URL `https://api.cloudflare.com/client/v4/accounts/{CLOUDFLARE_ACCOUNT_ID}/ai/run`, model `@cf/zai-org/glm-4.7-flash`, request timeout 60s, default `max_tokens=4000`.

File upload constraints (`app/services/study_file_service.py`): allowed extensions `pdf`, `docx`, `txt`, `md`; max size **10 MB**.

If Cloudflare credentials are missing, AI calls fail with **503** "AI service not configured".

---

## 6. Authentication & access control

- **All study endpoints require an authenticated user** (`current_user: User = Depends(get_current_user)`).
- **Material ownership:** materials are fetched/verified by `(material_id, user_id)`; accessing/modifying another user's material returns **404 "Material not found"**.
- **Asset ownership:** assets are resolved by id then verified via their material owner; mismatch/not found returns **404 "Asset not found"** (including update/delete/unlock paths that check ownership).
- **Essay review with asset:** when `asset_id` is provided it must belong to the same `material_id` (400 on mismatch) and be an `essay` asset with a valid `question_index`.
- Generated asset content is **not returned** by generate; it is returned only when unlocked (or in material detail for assets the user has already unlocked).

---

## 7. Endpoints

All paths below are prefixed with `/api/v1/study`. All require auth.

### 7.1 Upload material (text)
- **Method/Path:** `POST /materials`
- **Status:** `201 Created`
- **Request body** (`MaterialUploadRequest`):
  ```json
  {
    "title": "string (1..500, required)",
    "content": "string (min 1, required) — raw study material text",
    "exam_type": "string | null (max 32, optional)",
    "education_level": "string | null (max 50, optional)"
  }
  ```
- **Response** (`MaterialSummary`):
  ```json
  { "id": 123, "title": "Biology Week 1", "exam_type": "JAMB", "asset_types": [], "created_at": "<ISO datetime>" }
  ```
- **Behavior:** creates a `StudyMaterial` for `current_user` with `raw_input=content` and `content=content`.

### 7.2 Upload material (file)
- **Method/Path:** `POST /materials/upload`
- **Status:** `201 Created`
- **Content-Type:** `multipart/form-data`
- **Form fields:**
  - `file` (**required**, `UploadFile`): `.pdf`, `.docx`, `.txt`, `.md` (≤ 10 MB)
  - `title` (optional string): defaults to filename stem (or "Uploaded material")
  - `exam_type` (optional string)
  - `education_level` (optional string)
- **Response:** `MaterialSummary` (same shape as 7.1)
- **Behavior:** validates and reads file, extracts plain text, stores material with extracted text in `raw_input`/`content`, and stores `original_file_data`, `file_mime_type`, `page_count` (best-effort).
- **Errors:** `400` for unsupported/empty/oversized file or if no extractable text.

### 7.3 List materials
- **Method/Path:** `GET /materials`
- **Response:** `MaterialSummary[]` (user’s materials, `created_at` desc) with distinct `asset_types` per material.

### 7.4 Get material detail
- **Method/Path:** `GET /materials/{material_id}`
- **Response** (`MaterialDetail`):
  ```json
  {
    "id": 123,
    "title": "Biology Week 1",
    "exam_type": "JAMB",
    "education_level": "secondary",
    "content": "<text or null>",
    "parsed_structure": {},
    "assets": [
      {
        "id": 10,
        "asset_type": "mcq",
        "topic": "Cells",
        "points_to_unlock": 50,
        "unlocked": false,
        "created_at": "<ISO datetime>"
        // "content": <parsed asset JSON> included ONLY when unlocked == true
      }
    ],
    "created_at": "<ISO datetime>"
  }
  ```
- **Behavior:** ownership-checked; parses `parsed_structure` if present; per-asset `unlocked` from `study_unlocks`; includes parsed `content` only for unlocked assets. Assets ordered by id ascending.

### 7.5 Update material
- **Method/Path:** `PATCH /materials/{material_id}`
- **Request body** (`MaterialUpdateRequest`, at least one field required):
  ```json
  {
    "title": "string (1..500, optional)",
    "content": "string (min 1, optional)",
    "exam_type": "string | null (max 32, optional)",
    "education_level": "string | null (max 50, optional)"
  }
  ```
- **Response:** `MaterialSummary`
- **Behavior:** ownership-checked partial update. If `content` is provided, both `content` and `raw_input` are updated.

### 7.6 Delete material
- **Method/Path:** `DELETE /materials/{material_id}`
- **Status:** `204 No Content`
- **Behavior:** ownership-checked. Deletes related `study_unlocks` rows for the material, deletes all its assets, then deletes the material in a single transaction/commit. **No SP refund** is issued for prior unlocks.

### 7.7 Generate asset
- **Method/Path:** `POST /generate`
- **Request body** (`GenerateAssetRequest`):
  ```json
  {
    "material_id": 123,
    "asset_type": "mcq | flashcard | essay",
    "count": 5,
    "topic": "string | null (optional, max 200)",
    "difficulty": "easy | medium | hard"
  }
  ```
  - `asset_type`: required, `^(mcq|flashcard|essay)$`
  - `count`: int, default `5`, min `1`, max `20`
  - `topic`: optional; included as a focus instruction in the AI prompt and **persisted** on the asset
  - `difficulty`: default `"medium"`, `^(easy|medium|hard)$`; included as a difficulty instruction in the AI prompt
- **Response** (`GenerateAssetResponse`):
  ```json
  {
    "material_id": 123,
    "asset_id": 10,
    "asset_type": "mcq",
    "topic": "Cells",
    "points_to_unlock": 50,
    "unlocked": false,
    "message": "Asset generated. Unlock with SP to access content."
  }
  ```
- **Behavior:** verifies material ownership and non-empty content; generates via AI; stores `StudyAsset` with `topic`, `content_json`, and `points_to_unlock = settings.study_unlock_default_points`. Returns locked metadata only.

### 7.8 Update asset
- **Method/Path:** `PATCH /assets/{asset_id}`
- **Request body** (`AssetUpdateRequest`, at least one field required):
  ```json
  { "topic": "string | null (max 200)" }
  ```
- **Response:**
  ```json
  {
    "id": 10,
    "material_id": 123,
    "asset_type": "mcq",
    "topic": "Cells",
    "points_to_unlock": 50,
    "unlocked": false,
    "created_at": "<ISO datetime>"
  }
  ```
- **Behavior:** ownership-checked (via material); updates asset metadata.

### 7.9 Delete asset
- **Method/Path:** `DELETE /assets/{asset_id}`
- **Status:** `204 No Content`
- **Behavior:** ownership-checked. Deletes related `study_unlocks` rows for the asset, then deletes the asset. **No SP refund**.

### 7.10 Unlock asset
- **Method/Path:** `POST /assets/{asset_id}/unlock`
- **Request body:** none
- **Response** (`UnlockResponse`):
  ```json
  {
    "unlocked": true,
    "asset_id": 10,
    "material_id": 123,
    "points_spent": 50,
    "new_sp_balance": 950,
    "content": { /* parsed asset content_json */ },
    "method": "points" // or "already_unlocked"
  }
  ```
- **Behavior:** atomic, idempotent SP debit + unlock record (see §9). Returns parsed asset content.

### 7.11 Submit essay for AI review
- **Method/Path:** `POST /essay/submit`
- **Request body** (`EssaySubmitRequest`):
  ```json
  {
    "material_id": 123,
    "topic": "string | null (optional, max 200)",
    "essay": "string (min length 10, required)",
    "asset_id": 10,
    "question_index": 0
  }
  ```
  - `asset_id` (optional): target a specific generated essay asset
  - `question_index` (int, default `0`, >= 0): index into that asset’s `essays` array
- **Response** (`EssayReviewResponse`):
  ```json
  { "correct": true, "feedback": "Encouraging feedback", "score": 85, "suggestions": ["..."] }
  ```
- **Behavior:** verifies material ownership. If `asset_id` is provided, validates it belongs to `material_id`, is an `essay` asset, and `question_index` is in range, then reviews against that question’s `prompt`, `key_points`, and `sample_answer` (with topic derived from asset/topic when available). If `asset_id` is omitted, review is generic against the material/context. Defaults on missing AI fields: `correct=false`, `score=0`, `feedback="Keep trying!"`, `suggestions=[]`.
- **Errors:** `400` on asset/material mismatch, non-essay asset, or invalid/missing question index; `404` material/asset not found.

---

## 8. AI behavior

Implemented in `app/services/ai_service.py` and `app/controllers/study_controller.py`.

- **Provider/model:** Cloudflare Workers AI, model `@cf/zai-org/glm-4.7-flash`.
- **Call:** `POST {CLOUDFLARE_BASE_URL}/{CLOUDFLARE_MODEL}` with `Authorization: Bearer <CLOUDFLARE_API_TOKEN>` and JSON `{"messages":[{"role":"user","content":<prompt>}], "max_tokens": <n>}`.
- **Response extraction:** prefers `result.choices[0].message.content|text`, falls back to `result.response|content|text`.
- **JSON parsing:** strips markdown code fences if present; attempts `json.loads`; on failure tries to extract the first `{...}` block via regex; raises `ValueError` if still invalid (controller maps to 502).

### Generation prompts and expected AI JSON

Prompts include material content, an optional focus/topic block, and a difficulty instruction.

**MCQ** (`count`, 4 options, `correct_index` 0–3):
```json
{ "questions": [ { "question": "...", "options": ["A","B","C","D"], "correct_index": 0, "explanation": "..." } ] }
```

**Flashcards**:
```json
{ "flashcards": [ { "front": "...", "back": "..." } ] }
```

**Essay questions**:
```json
{ "essays": [ { "prompt": "...", "key_points": ["..."], "sample_answer": "..." } ] }
```

**Essay review** (uses specific question/key points/sample answer when `asset_id` provided):
```json
{ "correct": true, "score": 0, "feedback": "...", "suggestions": ["..."] }
```

The controller stores the parsed generation result as-is in `StudyAsset.content_json`.

---

## 9. Unlock & SP integration

- Generated assets default to **locked** (`unlocked=false`, no content in generate response).
- Unlock cost is `StudyAsset.points_to_unlock` (from `settings.study_unlock_default_points`, default 50).
- `StudyUnlockService.unlock_asset(user_id, asset_id)`:
  - Verifies asset exists and belongs to `user_id` (404 otherwise).
  - Idempotent fast path: existing `StudyUnlock` returns content with `method="already_unlocked"` and no new debit.
  - Atomic path: locks user row, rechecks unlock, checks SP, debits SP when `cost > 0` (updates `user.service_credit_balance`, decrements legacy `user.points_balance` floored at 0), writes `WalletLedger` SP debit with idempotency key `study_unlock_sp:{user_id}:{asset_id}`, inserts `StudyUnlock`, commits.
  - Returns `new_sp_balance` and parsed asset `content`.
- Material detail includes per-asset `unlocked` and `content` only for unlocked assets.
- Deleting a material/asset removes related unlock rows; **spent SP is not refunded**.

---

## 10. Error behavior

| Condition | Status | Detail |
|---|---:|---|
| Material not found / not owned | 404 | `"Material not found"` |
| Asset not found / not owned | 404 | `"Asset not found"` |
| User not found during unlock | 404 | `"User not found"` |
| Material has no content for generation | 400 | `"Material has no content"` |
| Unknown/invalid generation asset type | 400 | `"Unknown asset type: ..."` (schema constrains `mcq|flashcard|essay`) |
| File upload: unsupported type/mime, empty, >10 MB, or no extractable text | 400 | Descriptive message (e.g. unsupported type, too large, extraction failure) |
| Essay submit: `asset_id` not in `material_id`, not an essay asset, or bad `question_index` | 400 | Descriptive message |
| Update with no fields provided | 422 | Pydantic validation error |
| Insufficient SP to unlock | 402 | `{"message":"Insufficient service points (SP)","required_sp":<int>,"balance_sp":<int>}` |
| AI not configured (missing Cloudflare env) | 503 | `"AI service not configured"` |
| AI HTTP error / empty response / exception | 502 | `"AI service unavailable"` / `"AI returned empty response"` / `"AI service error: ..."` |
| AI response not parseable as expected JSON | 502 | `"AI returned invalid format. Try again."` |
| Request validation failures (pydantic) | 422 | Standard FastAPI validation error |
| Rate limit exceeded | 429 | Rate limit response (slowapi) |

---

## 11. Rate limiting

Per-route limits (slowapi, keyed by authenticated user or IP):

| Endpoint | Limit |
|---|---|
| `POST /materials` (text) | 30/hour |
| `POST /materials/upload` (file) | 20/hour |
| `GET /materials`, `GET /materials/{id}` | 120/minute |
| `PATCH /materials/{id}`, `DELETE /materials/{id}` | 60/minute |
| `POST /generate` | 20/hour |
| `PATCH /assets/{id}`, `DELETE /assets/{id}`, `POST /assets/{id}/unlock` | 60/minute |
| `POST /essay/submit` | 30/hour |

---

## 12. Current limitations / notes

- **AI dependency:** generation and essay review require Cloudflare Workers AI credentials; failures surface as 502/503.
- **No SP refund on delete:** deleting an unlocked asset/material removes unlock records but does not credit SP back.
- **`parsed_structure`/AI metadata:** `parsed_structure`, `explanation_structure`, `ai_model_used`, `figure_count` are not populated by current flows (file upload does store original bytes/mime/page_count for supported files).
- **Asset content shape:** depends on AI output (`questions`, `flashcards`, or `essays` arrays as produced) and is stored/returned as-is (parsed).
- **Material list N+1:** listing materials loads assets per material to compute `asset_types`.
- **No schema migration added here:** extensions rely on existing columns/tables; ensure DB schema is up to date in deployed environments.

---

*Document reflects implementation in `app/backend/app` (routers/controllers/schemas/models/repositories/services) as of this revision. For wallet/SP mechanics see `app/docs/wallet-system-complete-guide.md`.*
