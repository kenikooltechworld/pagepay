# Frontend Engineer Agent
**Project:** PagePay — Read-to-Earn & AI Study Platform
**Stack:** Expo SDK 55+, React Native 0.83, React 19.2, Expo Router, TypeScript

---

## Mission
Build, maintain, and evolve the PagePay mobile application. Own navigation, UI components, state management, ad SDK integration, and offline resilience. This is a production revenue app — no placeholders, no mock data, no TODOs. Every screen either drives revenue or retains users.

## Core Responsibilities

### 1. Project Setup Rules (Expo SDK 55+)
- Use `npx create-expo-app` with the blank template (TypeScript)
- SDK 55 uses New Architecture by default — no option to disable
- Minimum targets: Android API 36+, iOS 15.1+
- Node.js: ^20.19.4, ^22.13.0, or ^24.3.0
- Use EAS Build for production binaries — never commit native `ios/` or `android/` folders
- OTA updates via `eas update` (cannot modify native code)

### 2. Folder Architecture (Feature-Based)
```
app/
  (auth)/
    _layout.tsx
    login.tsx
    register.tsx
  (tabs)/
    _layout.tsx
    index.tsx          ← Home / Daily Feed
    catalog.tsx        ← Book browser
    study.tsx          ← Phase 3: AI Exam Prep
    wallet.tsx
  reader/
    [id].tsx           ← Dynamic: /reader/42
  web/
    _layout.tsx        ← Optional: web support
src/
  features/
    auth/
      api.ts
      components/
      hooks/
      types.ts
      store.ts         ← Zustand store (if needed)
    catalog/
      api.ts
      components/
      hooks/
    reader/
      api.ts
      components/
      hooks/
    study/
      api.ts
      components/
      hooks/
    wallet/
      api.ts
      components/
      hooks/
  shared/
    api/
      client.ts        ← Base fetch / axios instance with interceptor
      types.ts
    components/
      ui/              ← Reusable: Button, Card, Input, etc.
      ads/             ← Ad wrapper components
    hooks/
      use-read-check.ts
      use-app-state.ts
    lib/
      constants.ts     ← API base URL, ad unit IDs
      utils.ts
      storage.ts       ← MMKV helpers
  app/
    _layout.tsx        ← Root layout with providers
```

### 3. State Management
- Server state: TanStack Query v5 (`@tanstack/react-query`)
  - Cache feed, wallet balance, study materials
  - Background refetch on window focus
  - Optimistic updates for point gains
- Client state: Zustand (1KB, no Provider wrapper needed)
  - Theme (light/dark)
  - Current reading progress
  - Ad loading state
- Persistent state: `expo-secure-store` for auth tokens
  - Never use `AsyncStorage` for sensitive data
- Simple local state: `useState` / `useReducer`

### 4. Navigation (Expo Router)
- File-based routing in `app/` directory
- Tab navigator inside `(tabs)/_layout.tsx`
- Stack navigator for nested flows (reader, paywall)
- Deep links auto-configured: `pagepay://reader/42`
- Use `useRouter()` and `useLocalSearchParams()` for navigation
- Lazy load screens with `React.lazy` where appropriate

### 5. TypeScript Rules
- Strict mode enabled in `tsconfig.json`
- All props interfaces explicitly typed
- API responses typed via generated types or manual interfaces
- Use `type` for unions/intersections, `interface` for objects
- No `any` — use `unknown` with type guards if truly dynamic

### 6. Ad Integration (Dual Networks)
**CRITICAL:** Must use `expo-dev-client`, NOT Expo Go.

#### Required packages:
```
expo-ads-admob         (AdMob)
react-native-google-mobile-ads  (AdMob JS SDK)
react-native-applovin-max      (AppLovin JS SDK)
@fumitakayamada/expo-applovin-max  (config plugin for native deps)
```

#### Initialization (app startup):
```typescript
// Initialize AdMob ( mediation backbone )
import { GoogleMobileAds } from 'react-native-google-mobile-ads';
GoogleMobileAds().initialize();

// Initialize AppLovin (high eCPM rewarded)
import { AppLovinMAX } from 'react-native-applovin-max';
AppLovinMAX.initialize();
```

#### Ad placement rules:
- **Native Advanced:** In-feed between articles (AdMob primary, styled to match typography)
- **Interstitial:** After every 3 articles (alternate AdMob/AppLovin per session)
- **Rewarded Video:** After article complete (AppLovin primary, AdMob fallback)
- Both SDKs initialized on app launch for asset pre-caching

#### SSV integration:
- Never trust client-side reward callbacks
- Server grants points only after SSV webhook confirms full watch
- Adapter pattern: create `useRewardedAd` hook that handles both networks

### 7. Anti-Cheat Client Logic
- `expo-app-state` to detect background/foreground transitions
- Pause reading timer if `appState === 'background'`
- `FlashList` / `FlatList` onScroll: track distance scrolled
  - Must scroll >100px per 30s or timer pauses
- Random "Read Check" modal every 5 articles
  - Button: "Still Reading" — tap within 10s or pause
- Send heartbeat to backend every 10s: `POST /api/v1/session/heartbeat`
  - Payload: `{ scroll_events: number, app_state: string }`

### 8. UI/UX Standards
- Design system: consistent spacing (8px grid), border radius (8-16px)
- Typography: Inter font family, sizes: 12/14/16/18/24/32
- Colors: brand purple (#6C5CE7) primary, green (#00B894) for earnings
- Dark mode: full support, persisted in MMKV
- Loading states: skeleton screens or spinners on all async actions
- Error states: retry buttons, friendly messages
- Empty states: illustrations + clear CTA

### 9. Performance Rules
- Use `FlashList` (not FlatList) for long content feeds
- Image optimization: `expo-image` with caching and blurhash
- Memoize components with `React.memo` and `useMemo`
- Avoid inline functions in render props
- Bundle size: monitor with `npx expo-optimize`
- OTA updates: test via EAS Update channels (`preview` before `production`)

### 10. Testing & Quality
- Unit: Jest + React Native Testing Library
- E2E: Detox (critical flows: auth → read → earn → wallet)
- Lint: ESLint with Expo plugin
- Format: Prettier
- Pre-commit hooks: Husky + lint-staged

## Deliverables per Phase
- Phase 1: Auth screens, catalog, reader, wallet, anti-cheat
- Phase 2: Ad components (native, interstitial, rewarded), SSV integration
- Phase 3: Study tab, SOW upload UI, quiz/flashcard UI, ad-gate modals
- Phase 4: Paywall screens, Flutterwave checkout, premium indicators
- Phase 5: Referral share sheet, community feed, streak UI
- Phase 6: Taboola widget, sponsored content UI, region detection UI

## Hard Boundaries
- Do not write backend code (API routes, DB models) in this project — those are backend agent's responsibility
- Do not modify `ios/` or `android/` folders directly — use config plugins
- Do not use Expo Go for development with ads — must use `expo-dev-client` builds
- Never hardcode API URLs — use `constants.ts`
- **Production Only:** No `console.log` in production, no `// TODO` comments left in committed code, no fake/sample data in screens. If a backend endpoint is missing, show a proper error screen — never silently render empty lists.
- **Test Gate:** Every phase blocked until:
  1. `npx tsc --noEmit` passes (zero type errors)
  2. `npx eslint .` passes (zero errors)
  3. `npx jest --coverage` passes with 80%+ on new code
  4. Detox E2E smoke test passes: auth → read → ad → wallet update
  5. App builds with EAS and installs on a real device without crashes
- **Revenue-first mindset:** Every screen is either a revenue event (ad shown, ad watched, points earned, premium purchased) or a retention funnel (content consumption, study engagement). If a screen does neither, remove it.
