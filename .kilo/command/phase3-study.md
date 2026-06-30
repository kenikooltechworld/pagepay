# Command: Phase 3 — Student AI Exam Prep

**Duration:** Weeks 7–10
**Agents:** Backend + Frontend + AI
**Goal:** Ship the AI study tab: SOW upload → structured outline → MCQs/flashcards/essays → ad-gated answers.

---

## Backend Tasks

### Step 1: AI Router Refactor
- Create `app/ai/router.py` with all provider call functions
- Each provider client:
  - `client.py` (fastapi-like): `call_gemini(prompt, model, max_tokens)`
  - `client.py` (openai-compatible): `call_groq(prompt, model, max_tokens)`
  - Use official SDKs or direct HTTP (`httpx`)
- Create `app/ai/prompts.py`:
  - System prompts for: `SOW_PARSER`, `MCQ_GENERATOR`, `FLASHCARD_GENERATOR`, `CHAT_TUTOR`
  - All prompt templates stored as constants (versioned)
- `POST /api/v1/ai/route`:
  - Request: `{"prompt": "...", "task_type": "heavy|fast|chat", "max_tokens": int}`
  - Returns: `{"response": "...", "provider": "gemini", "model": "..."}`
- Circuit breaker table + helper functions in `app/ai/circuit_breaker.py`

### Step 2: SOW Upload Endpoint
- `POST /api/v1/study/sow/upload`:
  - Accept: `multipart/form-data` (image) OR `application/json` (text)
  - If image:
    1. Save to `/tmp/sow_upload.jpg`
    2. Send to Gemini Vision (`gemini-2.5-flash` multimodal) for OCR
    3. Extract text
  - If text: use directly
  - Send extracted text to `SOW_PARSER` prompt via router
  - Save: `StudyMaterial(user_id, raw_input=original, parsed_structure=JSON)`
  - Return: `{material_id, parsed_structure: {topics: [{name, subtopics, key_concepts}]}}`

### Step 3: Asset Generation
- `POST /api/v1/study/generate`:
  - Request: `{material_id, asset_type: "mcq|flashcard|essay", count: 5}`
  - Router → appropriate prompt for asset type
  - MCQ prompt expects JSON: `{"questions": [{"question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "..."}]}`
  - Flashcard prompt expects: `{"cards": [{"front": "...", "back": "..."}]}`
  - Essay prompt expects: `{"questions": ["..."]}`
  - Save asset data in `quiz_sessions` or new `study_assets` table
  - Return: `{assets: [...]}`
- `POST /api/v1/study/chat` (streaming):
  - Request: `{material_id, message: "..."}`
  - Include material context in prompt
  - Use `StreamingResponse` with generator
  - Yield token-by-token to frontend

### Step 4: Ad-Gated Access
- `POST /api/v1/study/unlock`:
  - Request: `{asset_id, method: "ad|points"}`
  - If method="points": check `User.points_balance >= 50`, deduct, unlock
  - If method="ad": return `{"ad_unit_id": "..."}` → client plays ad → calls back
  - Return: `{unlocked: true, answer/explanation: "..."}`
- Track `points_spent` in new `study_transactions` table

### Step 5: Database Tables
- `study_materials`: already exists (create in Phase 1)
- `quiz_sessions`: already exists (create in Phase 1)
- New `study_assets`: `id, material_id, asset_type, content_json, points_to_unlock, created_at`
- New `study_transactions`: `id, user_id, asset_id, method, points_spent, reward_granted, created_at`

---

## Frontend Tasks

### Step 1: Study Tab Setup
- `app/(tabs)/study.tsx`:
  - Show two sections: "Upload SOW" card + "My Materials" list
  - Empty state: "Upload your scheme of work to get started"
- Zustand store `useStudyStore()`:
  - `materials: StudyMaterial[]`
  - `uploading: boolean`
  - Fetch on tab focus via TanStack Query

### Step 2: SOW Upload UI
- Two buttons: "Camera" + "Upload File"
- `expo-image-picker` for camera/gallery
- `expo-document-picker` for PDF/text
- On select: show progress indicator (Skia ring)
- Send to `POST /api/v1/study/sow/upload`
- On success: show parsed preview (expandable topics)
- Save `material_id` to list

### Step 3: Asset Browser
- Material detail screen: expandable accordion
  - MCQ section: `FlashList` of question cards
    - Tap to select answer → instant feedback (correct/incorrect)
    - "Answer locked" state: show ad/paywall prompt
  - Flashcard section: Reanimated tap-to-flip card
  - Essay section: list of prompts + AI outline
- Unlock UI:
  - `useRewardedAd` hook loads AppLovin rewarded
  - After ad → calls `POST /api/v1/study/unlock` with `method: "ad"`
  - On points: deducts via API, shows result

### Step 4: Chat Interface
- Chat screen per material
- FlatList of messages (user + AI)
- Streaming text: update state on each token
- Input bar at bottom + send button
- Loading shimmer while generating

### Step 5: Points Integration
- Quiz score ≥ 80%: bonus 20 pts (backend handles, but show UI notification)
- Ad-gate: "50 pts to unlock" button prominent

---

## AI Architect Tasks

### Step 1: Create Prompt Templates
File: `backend/app/ai/prompts.py`
```python
SOW_PARSER = """You are an academic curriculum parser...
Input: {raw_text}
Output strict JSON:
{{
  "topics": [
    {{"name": "Topic 1", "subtopics": ["Sub A", "Sub B"], "key_concepts": ["concept1"]}}
  ]
}}
Rules: No markdown. No backticks. Valid JSON only."""

MCQ_GENERATOR = """Generate {count} MCQs from: {context}
Output strict JSON:
{{
  "questions": [
    {{"question": "...", "options": ["A", "B", "C", "D"], "correct_index": 0, "explanation": "..."}}
  ]
}}"""

FLASHCARD_GENERATOR = """Generate {count} flashcards from: {context}
Output strict JSON:
{{"cards": [{{"front": "...", "back": "..."}}]}}"""
```

### Step 2: Implement Provider Clients
- `providers/gemini.py`: HTTP POST to `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent`
  - Auth: `?key={API_KEY}`
  - Request: `{"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"maxOutputTokens": 4000, "temperature": 0.3}}`
- `providers/groq.py`: OpenAI-compatible client to `https://api.groq.com/openai/v1/chat/completions`
  - Auth: `Authorization: Bearer {API_KEY}`
  - Model: `llama-3.3-70b-versatile`
- `providers/openrouter.py`: OpenAI-compatible client to `https://openrouter.ai/api/v1/chat/completions`

### Step 3: Circuit Breaker
- `app/ai/circuit_breaker.py`:
  - `mark_failed(provider_name)`
  - `mark_success(provider_name)`
  - `get_circuit_open() → list[str]` (providers currently open)
  - DB: `ai_provider_health` table with SQLAlchemy 2.0 async

---

## Acceptance Criteria (Phase 3 Complete)
✅ Upload SOW (image or text) → AI parses to structured outline
✅ Generate MCQs: 5 questions per topic, valid JSON, correct answers
✅ Generate flashcards: tap-to-flip UI works
✅ Generate essay prompts: list displays correctly
✅ "Unlock answer" via rewarded ad works (SSV → points credit)
✅ "Unlock answer" via 50 pts works (balance deducted)
✅ Streaming chat responds token-by-token
✅ AI fails over to secondary provider on rate limit
✅ Chat UI shows loading, streaming, and error states
✅ Live on Play Store update
✅ Backend + frontend: all previous phase tests still pass
✅ E2E: Upload syllabus → generate quiz → answer → earn points → premium gating works
✅ No TODO comments, placeholder strings, or mock data in committed code
