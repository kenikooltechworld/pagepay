# Command: Phase 6 — Licensed Content & Scale

**Duration:** Weeks 19+
**Agents:** Backend + Frontend
**Goal:** Replace placeholder content with revenue-share APIs, add regional variants, and scale infrastructure.

---

## Backend Tasks

### Step 1: Content Provider Abstraction
- `app/content/providers/base.py` — abstract base class:
  ```
  async def get_article(id: str) -> Article
  async def get_feed(category: str, page: int) -> list[Article]
  async def search(query: str) -> list[Article]
  ```
- `app/content/providers/gutendex.py` — implement base (already used, refine)
- `app/content/providers/gnews.py` — implement base
- `app/content/providers/taboola.py` — implement base (requires approval)
- `app/content/providers/hive.py` — implement base
- `app/content/service.py` — unified `ContentService`:
  - `get_feed(user_id)` → pulls from active providers per `content_sources` config
  - Rotation: round-robin or weighted by fill/CPM

### Step 2: Feature Flags for Content Sources
- `app_config` entries:
  - `content_sources` → JSON array of active sources
  - Example: `["gutendex", "gnews", "hive"]`
- Admin endpoint: `POST /api/v1/admin/config/set` (key, value)
- Frontend fetches active sources and adjusts catalog tabs

### Step 3: Taboola/Outbrain Integration (Post-Approval)
- `taboola.py` provider:
  - Fetch feed from Taboola API (requires publisher ID + API key)
  - Transform to unified `Article` format
  - Mark `is_sponsored=true`, `revenue_share=true`
- Revenue reconciliation:
  - Daily cron: fetch earnings report from Taboola
  - Import into `ad_impressions` with `provider = "taboola"`
  - Match to user sessions for accounting

### Step 4: Regional Content Variants
- Detect region: `expo-localization` on frontend → send `Accept-Language` header
- `content_sources` can have region override:
  - Nigeria: Naija news (custom RSS), WAEC/NECO past questions (if API found)
  - Kenya: local news, KCSE content
- `GET /api/v1/content/feed/:user_id?region=NG`

### Step 5: Scaling Improvements
- Database: add read replicas for `content_catalog` (high read, low write)
- Cache: Redis for content feed (5-min TTL) to reduce DB load
- CDN: serve Gutendex cover images via Cloudflare R2 / S3-compatible
- Rate limiting: per-user, per-endpoint with Redis-backed counters

---

## Frontend Tasks

### Step 1: Taboola Widget
- `src/shared/components/ads/TaboolaWidget.tsx`
- Render Taboola feed items styled as "Sponsored Reading"
- Clear "Sponsored" label per requirements
- Track clicks via backend

### Step 2: Region Detection
- `expo-localization` to get `locale` and `country`
- Send region in API headers
- Show localized content tabs: "For You" (general) + "Naija News" (if NG)

### Step 3: Polish & Performance
- Lazy load all study screens
- Prefetch next article on scroll
- Optimize images with `expo-image` cache strategy
- Run bundle size audit, target <3MB initial JS

---

## Acceptance Criteria (Phase 6 Complete)
✅ Content provider abstraction allows adding new source without code deploy (config-driven)
✅ Taboola feed integrated and monetizing if approved
✅ Regional content switches based on detected locale
✅ Redis cache reduces DB load by >80% on reads
✅ CDN images load in <200ms
✅ App ready for 10,000+ DAU without infrastructure changes
✅ All Phase 1-5 tests still pass
✅ E2E: Regional user → localized feed → Taboola sponsored content → ad impression logged in DB
✅ No TODO comments, placeholder strings, or mock data in committed code
