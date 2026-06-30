# Command: Phase 2 — Ad Monetization Foundation

**Duration:** Weeks 4–6
**Agents:** Backend + Frontend + DevOps
**Goal:** Attach real revenue via dual ad network (AdMob + AppLovin MAX) with server-side verification.

---

## Shared Pre-Work
1. Get AdMob account: create app in Firebase Console, get App ID + test ad unit IDs
2. Get AppLovin account: generate SDK key + test ad unit IDs
3. branch `FEATURE_BRANCH=phase-2`

---

## Backend Tasks

### Step 1: Ad Infrastructure Tables
- New columns in `ContentCatalog`: `is_sponsored BOOLEAN DEFAULT FALSE`
- New table `ad_placements`:
  ```
  id, location (e.g., 'in_feed', 'interstitial', 'rewarded'), 
  ad_type, priority, primary_provider, fallback_provider, ad_unit_id
  ```
- New table `ad_impressions`:
  ```
  id, user_id, session_id, ad_type, ad_unit, provider, 
  impression_revenue_usd (INT in micros), watched_fully, 
  reward_granted, transaction_id (UNIQUE), webhook_payload (JSON), created_at
  ```
- New table `app_config`:
  ```
  key (PK), value, updated_at
  -- Store ad unit IDs, point rates, prices here for OTA changes
  ```
- New table `ai_provider_health`:
  ```
  provider_name (PK), consecutive_failures, last_failure_at, 
  circuit_open_until
  ```

### Step 2: SSV Webhook Endpoints
- `POST /api/v1/ads/google/callback` (AdMob):
  - Verify request signature using `google-play-billing` helper or manual HMAC
  - Parse payload: `transaction_id`, `user_id` (from custom data), `reward_amount`
  - Check `transaction_id` unique constraint
  - If not exists and `reward_amount > 0`:
    - Find active reading session for user
    - Credit points to `User.points_balance`
    - Set `ad_event.reward_granted = true`
  - Return 200 OK immediately (AdMob retries on failure)
- `POST /api/v1/ads/applovin/callback` (AppLovin):
  - Verify using AppLovin webhook secret
  - Parse: `transaction_id`, `user_id`, `currency`, `revenue`
  - Same idempotency + point credit logic as AdMob

### Step 3: Content Feed Rotation
- `GET /api/v1/content/feed/:user_id`:
  - Query `content_catalog` with `is_sponsored` rotation
  - Every 4th item in feed: sponsored entry (marked `is_sponsored=true`)
  - Sponsored entries use `ad_placements` to determine which ad network content belongs to
  - Track `user_id` + `session_id` to avoid showing same sponsored content twice
- `ad_placements` seed data:
  ```
  INSERT INTO ad_placements (location, ad_type, priority, primary_provider, fallback_provider)
  VALUES ('in_feed', 'native', 1, 'admob', 'applovin'),
         ('interstitial', 'interstitial', 1, 'admob', 'applovin'),
         ('rewarded', 'rewarded', 1, 'applovin', 'admob');
  ```

### Step 4: Ad Event Logging (Client-Side)
- Client calls `POST /api/v1/ads/impression` on ad load:
  - Payload: `{ad_type, provider, ad_unit, session_id}`
  - Server creates `AdEvent` record (no points yet)
- Client calls `POST /api/v1/ads/reward-claim` on reward callback:
  - Payload: `{ad_event_id, transaction_id, provider}`
  - Server verifies against SSV → credits points

### Step 5: Testing
- Unit tests:
  - SSV webhook idempotency (duplicate transaction_id → no double credit)
  - Ad placement rotation logic
  - Point credit calculation
- Integration: mock AdMob/AppLovin webhook calls with test transaction IDs
- Run migrations + tests in Docker
- Verify: `docker compose up` + `pytest`

---

## Frontend Tasks

### Step 1: Install Native Ad Dependencies
```bash
npx expo install expo-ads-admob
npm install react-native-google-mobile-ads react-native-applovin-max
npm install --save-dev @fumitakayamada/expo-applovin-max
npx expo prebuild --clean
npx expo run:android  # or expo run:ios
```

**CRITICAL:** Do not use Expo Go. Must build dev-client binary for testing ads.

### Step 2: App Initialization
- `app/_layout.tsx`:
  - Initialize AdMob: `GoogleMobileAds().initialize()`
  - Initialize AppLovin: `AppLovinMAX.initialize()`
  - Set user consent if needed (GDPR/CCPA)
- Create `src/shared/lib/ads.ts`:
  - Constants: AdMob App ID, AppLovin SDK key
  - Ad unit IDs from `app_config` (fetch from backend `/api/v1/config/ads`)
  - Wrapper functions: `loadNativeAd()`, `loadInterstitial()`, `loadRewarded()`

### Step 3: Native Ad Component (In-Feed)
- `src/shared/components/ads/NativeAdBanner.tsx`:
  - Drop-in replacement for sponsored content card
  - Renders AdMob Native Advanced or AppLovin Native
  - Styles match app typography (font, color, border-radius)
  - Fetches ad from backend `/api/v1/ads/native?placement=in_feed`
  - Impression tracking: calls `/api/v1/ads/impression` on mount
- Integration in reader: inject every 4th item in FlatList

### Step 4: Interstitial Ad
- Trigger: after every 3 articles (track in Zustand or ReadingSession API)
- `loadInterstitial()` on app startup
- On trigger: show ad, call `/api/v1/ads/impression`
- Back required? Show skip button after 5s
- On close: auto-navigate to next article or home

### Step 5: Rewarded Video Ad (Double Earn)
- After article complete: show modal
  - "Earned 10 pts! Watch 30s video to double to 20 pts?"
- Load AppLovin rewarded (primary) → AdMob rewarded (fallback)
- On complete: call backend SSV endpoint
- Update wallet with bonus points
- Handle "skipped" case: no bonus, still keep base reward

### Step 6: Ad Failure Handling
- If ad fails to load:
  - Log to `AdEvent` with `provider = "none"`
  - Free tier: auto-grant base reward points (server decides, client requests)
  - Show debug message in dev builds only

### Step 7: Test Ads → Production Ads
- Week 1-2: Use ONLY test ad unit IDs (AdMob: `ca-app-pub-3940256099942544/...`)
- Week 3: Switch to production IDs via `app_config` API
- Verify SSV in staging environment before production

### Step 8: Build + Ship
- Production build: `eas build --platform android --profile production`
- Upload same build to Play Store
- Update listing: "PagePay: Read, Watch & Earn"

---

## DevOps Tasks

### Step 1: Backend Deploy
- Push Docker image to registry (Railway/Render auto-deploys)
- Run `alembic upgrade head` on production DB
- Verify health endpoint

### Step 2: Webhook Exposure
- Ensure backend webhook endpoints are publicly accessible
- Register webhook URLs in AdMob and AppLovin dashboards
- Test with curl send of sample payloads

---

## Acceptance Criteria (Phase 2 Complete)
✅ Native ads render in-feed with correct styling
✅ Interstitial shows after 3 articles
✅ Rewarded video plays after article complete
✅ SSV endpoints credit points (tested with real test ads)
✅ Dual network fallback works (disable one to confirm other serves)
✅ Ad impression events logged in DB
✅ App builds and runs with real ad SDKs (not Expo Go)
✅ Live on Play Store with monetization active
✅ Backend: all Phase 1 tests still pass
✅ E2E: Read article → interstitial → rewarded video → double points in wallet
✅ No TODO comments, placeholder strings, or mock data in committed code
