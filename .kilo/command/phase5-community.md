# Command: Phase 5 — Referrals & Community

**Duration:** Weeks 14–18
**Agents:** Backend + Frontend
**Goal:** Build referral program and community study notes feed. Drive organic growth and retention.

---

## Backend Tasks

### Step 1: Referral System
- `POST /api/v1/referral/generate`:
  - Creates unique referral code (6-char alphanumeric)
  - Stores `user.referral_code` if empty
  - Returns `{code, link: "https://pagepay.app/ref/ABC123"}`
- `GET /api/v1/referral/stats`:
  - Returns `{code, clicks, signups, pending_rewards, claimed_rewards}`
- On new user registration: `?ref=ABC123` → link to existing user
  - Store `referee.referred_by = ABC123`
- `POST /api/v1/referral/validate`:
  - Triggered when referee completes first verified reading session (≥2 minutes)
  - Awards: referrer gets 500 pts, referee gets 200 pts
  - Limits: max 10 referrals per day per user
  - Prevents self-referral (check `user.id != referee.id`)
- Table `referrals`:
  ```
  id, referrer_id, referee_id, code, referee_completed_first_session, 
  reward_granted, created_at
  ```

### Step 2: Cron Jobs (Add to docker-compose or separate worker)
- Hive sync: every hour, fetch new posts from Hive API, insert into `content_catalog`
- Subscription expiry: daily cleanup of expired premium users (as in Phase 4)
- Referral daily cap: reset `referrals_today_count` if date changed

### Step 3: Community Notes Feed
- `POST /api/v1/community/upload`:
  - Auth required
  - Request: `{title, content, course_code, university?}`
  - Save to `community_notes` table
  - Status: `pending` for moderation (optional in MVP)
- `GET /api/v1/community/feed`:
  - Paginated list of approved notes
  - Filters: `?course_code=CSC201&sort=popular|recent`
- `POST /api/v1/community/:id/like`:
  - Toggle like, store in `community_likes`

### Step 4: Analytics Endpoints (Basic)
- `GET /api/v1/admin/analytics/dau`:
  - Daily active users count
- `GET /api/v1/admin/analytics/retention`:
  - Cohort data (Day 1, Day 7 signups returning)
- `GET /api/v1/admin/analytics/content-performance`:
  - Top 20 articles by `reading_sessions` count
- Protect these with admin-only JWT (new `role` column or separate admin auth)

---

## Frontend Tasks

### Step 1: Referral Share Sheet
- `app/(tabs)/profile.tsx` → Referral section
- `expo-sharing` share sheet:
  - Pre-filled WhatsApp message: "Join PagePay and earn by reading! My code: ABC123"
  - Copy link button
- Progress tracker: "3/5 referrals to unlock bonus"
- Stats display: clicks, signups, earnings from referrals

### Step 2: Community Feed
- New tab or section: `app/(tabs)/community.tsx`
- `FlashList` of note cards with:
  - Title, author, course code, likes count
  - Timestamp: "2 days ago"
- Filter chips at top: All | MY_COURSES | POPULAR | RECENT
- Note detail: expands to full text
- Like button: `useMutation` calls `POST /api/v1/community/:id/like`

### Step 3: Continue Reading Carousel
- Home tab: horizontal `FlashList` of "Continue Reading" items
- Pull from backend: `GET /api/v1/reading/continue` (last 5 unfinished sessions)
- Show progress ring: "Page 3 of 12, 50 pts remaining"
- Tap resumes reader at saved scroll position (store `scroll_y` in session)

### Step 4: Streak Counter
- Home tab header: "🔥 7 day streak"
- Logic: consecutive days with ≥1 verified reading session
- Backend endpoint: `GET /api/v1/users/me/streak`
- Streak bonus: 7 days = +20% pts, 30 days = +50% pts (configure in `app_config`)

---

## Acceptance Criteria (Phase 5 Complete)
✅ Referral code generation + share sheet works
✅ Referee completes first session → both users credited
✅ Daily referral cap enforced (max 10/day)
✅ Community notes feed loads + filters
✅ Like toggle works without page refresh
✅ Continue reading carousel displays last 5 books
✅ Streak counter updates on daily reading
✅ Admin analytics endpoints return real data
✅ All Phase 1-4 tests still pass
✅ E2E: refer friend → friend registers → both read → both get bonus points
✅ No TODO comments, placeholder strings, or mock data in committed code
