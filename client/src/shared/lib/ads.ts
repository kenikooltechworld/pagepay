/**
 * Ad SDK configuration + loader helpers.
 *
 * This is the single source of truth on the client for which ad
 * network we use (AdMob only — AppLovin MAX is stubbed until we
 * have unit IDs and the SDK is wired) and how to fetch the live
 * config from the backend.
 *
 * The split:
 *   - `getAdsConfig()` is a TanStack-Query-friendly fetch of
 *     `/api/v1/config/ads?env=<env>`. The result is cached in
 *     QueryClient for 1h — the server response is tiny (a flat
 *     dict of unit IDs) and the call is unauthenticated, so
 *     making it on every app cold start is fine.
 *   - `PLATFORM_ENV` reads `app.config.js` → `expoConfig.extra.adsEnv`
 *     to decide whether to ask the server for prod or dev IDs.
 *     The dev branch returns Google's documented test unit IDs
 *     (so dev builds never burn real impressions against the
 *     production account); the prod branch returns the PagePay
 *     IDs the ops team seeded in `app_config`.
 *   - `getAdUnitId(slot, platform)` resolves one slot to its
 *     unit ID. Returns an empty string for unknown slots — the
 *     caller treats empty as "this slot is disabled" and falls
 *     back to the MockAdModal (the in-app ad simulation that
 *     has been running since Phase 1).
 *
 * Why not use `react-native-google-mobile-ads` directly here:
 * that module is a native dependency, requires `expo prebuild`,
 * and only loads inside an EAS/dev-client build. We keep the
 * loader surface (`getAdUnitId`, `getAdsConfig`) in plain TS so
 * the rest of the client can import and call it before the
 * native module lands — same pattern as the existing
 * `src/shared/lib/*` files. When the native SDK is installed,
 * `loadBannerAd()` / `loadNativeAd()` / `loadRewardedAd()` will
 * be filled in behind the same API and the call sites stay put.
 */

import Constants from 'expo-constants';
import { apiFetch } from '@/src/shared/api/client';


/** Which ad environment the client should fetch. Driven by
 *  `app.config.js` → `expoConfig.extra.adsEnv`. Defaults to
 *  `dev` so a fresh dev build never accidentally serves prod
 *  unit IDs. CI sets this to `prod` before the staging build. */
export const PLATFORM_ENV: 'dev' | 'prod' =
  (Constants.expoConfig?.extra?.adsEnv as 'dev' | 'prod' | undefined) ?? 'dev';


/** Slot + platform → unit id mapping. The server returns this
 *  flat; we re-declare the slot names here so callers can fail
 *  fast at type-check time on a typo. */
export type AdSlot =
  | 'in_feed_android'
  | 'in_feed_ios'
  | 'interstitial_android'
  | 'interstitial_ios'
  | 'rewarded_android'
  | 'rewarded_ios'
  | 'banner_android'
  | 'banner_ios';

export type AdPlatform = 'android' | 'ios';


export type AdsConfig = {
  /** AdMob App ID for the Android app (the value placed in
   *  AndroidManifest.xml via app.config.js). */
  android_app_id: string;
  /** AdMob App ID for the iOS app (the value placed in
   *  Info.plist via app.config.js). */
  ios_app_id: string;
} & Record<AdSlot, string>;


/** Query key for the ads-config cache. Centralized so the
 *  catalog/wallet/etc. all invalidate the same key when ops
 *  rotates a unit ID. */
export const ADS_CONFIG_QUERY_KEY = ['ads', 'config', PLATFORM_ENV] as const;


/** Fetch the current ad config from the backend. Returns an
 *  empty-string-filled object on network failure so the rest
 *  of the client never has to special-case a missing config —
 *  every slot degrades to "disabled" and the MockAdModal
 *  takes over.
 *
 *  The endpoint is unauthenticated per the backend spec; the
 *  server only returns the value for the requested `env` so a
 *  dev build can never accidentally read prod unit IDs. */
export async function fetchAdsConfig(): Promise<AdsConfig> {
  const url = `/api/v1/config/ads?env=${encodeURIComponent(PLATFORM_ENV)}`;
  try {
    const res = await apiFetch(url);
    if (!res.ok) {
      // Surface as a thrown error so the caller's `useQuery`
      // surfaces the failure in the network inspector. The
      // empty default below is what `useQuery`'s `placeholderData`
      // will use while loading.
      throw new Error(`Failed to fetch ads config: HTTP ${res.status}`);
    }
    return (await res.json()) as AdsConfig;
  } catch (err) {
    // Network failure or HTTP error — return an empty config so
    // the rest of the app keeps working (the MockAdModal is the
    // fallback for every disabled slot).
    if (__DEV__) {
      console.warn('[ads] fetchAdsConfig failed, falling back to empty config', err);
    }
    return {
      android_app_id: '',
      ios_app_id: '',
      in_feed_android: '',
      in_feed_ios: '',
      interstitial_android: '',
      interstitial_ios: '',
      rewarded_android: '',
      rewarded_ios: '',
      banner_android: '',
      banner_ios: '',
    };
  }
}


/** Resolve one slot to its unit ID for the current platform.
 *  Returns `''` (the disabled sentinel) for unknown platforms
 *  or slots the server didn't return. */
export function getAdUnitId(
  slot: 'in_feed' | 'interstitial' | 'rewarded' | 'banner',
  platform: AdPlatform,
  config: AdsConfig | undefined,
): string {
  if (!config) return '';
  const key: AdSlot = `${slot}_${platform}` as AdSlot;
  return config[key] ?? '';
}


/** Log an impression to the backend. Called the moment the
 *  ad SDK reports the slot finished loading (i.e. before
 *  the user has watched the ad and earned a reward).
 *  `sessionId` is optional because banner ads can fire on
 *  screens that don't have an open reading session.
 *
 *  Returns the `ad_event_id` the reward-claim call needs to
 *  link back to this row. Returns `null` on network failure
 *  — the caller continues regardless because a missing
 *  impression row is recoverable (the reward-claim call
 *  will create its own row with `ad_event_id=null`). */
export async function logAdImpression(input: {
  adType: 'banner' | 'native' | 'interstitial' | 'rewarded';
  provider: 'admob' | 'applovin_max' | 'mock';
  adUnit: string;
  sessionId: number | null;
}): Promise<number | null> {
  try {
    const res = await apiFetch('/api/v1/ads/impression', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ad_type: input.adType,
        provider: input.provider,
        ad_unit: input.adUnit,
        session_id: input.sessionId,
      }),
    });
    if (!res.ok) {
      if (__DEV__) {
        const text = await res.text();
        console.warn(`[ads] logAdImpression failed: HTTP ${res.status}`, text.substring(0, 200));
      }
      return null;
    }
    const contentType = res.headers.get('content-type');
    if (!contentType || !contentType.includes('application/json')) {
      if (__DEV__) {
        const text = await res.text();
        console.warn('[ads] logAdImpression: Non-JSON response', text.substring(0, 200));
      }
      return null;
    }
    const body = (await res.json()) as { ad_event_id: number };
    return body.ad_event_id;
  } catch (err) {
    if (__DEV__) {
      console.warn('[ads] logAdImpression failed', err);
    }
    return null;
  }
}


/** Claim the credit for a watched ad. Called when the SDK's
 *  revenue callback fires (AdMob `onAdPaid`, AppLovin MAX
 *  postback). `transactionId` is the SSV-style dedupe key —
 *  replaying the same call is a no-op and returns the same
 *  outcome.
 *
 *  `adEventId` is the impression row created at load time
 *  (pass the value `logAdImpression` returned earlier). It's
 *  optional because the claim can succeed even when the
 *  impression log was lost (network blip on the load call);
 *  the server creates a fresh row in that case and the
 *  audit trail just has a load-less credit. */
export type RewardClaimResult = {
  adEventId: number;
  pointsCredited: number;
  newBalance: number;
  fxRate: number;
  userShareNgn: number;
  creditStatus: 'credited' | 'rejected_low_value' | 'duplicate';
};

export async function claimAdReward(input: {
  adEventId: number | null;
  adType: 'banner' | 'native' | 'interstitial' | 'rewarded';
  provider: 'admob' | 'applovin_max' | 'mock';
  adUnit: string;
  revenueUsd: number;
  transactionId: string;
}): Promise<RewardClaimResult | null> {
  try {
    const res = await apiFetch('/api/v1/ads/reward-claim', {
      method: 'POST',
      body: JSON.stringify({
        ad_event_id: input.adEventId,
        ad_type: input.adType,
        provider: input.provider,
        ad_unit: input.adUnit,
        revenue_usd: input.revenueUsd,
        transaction_id: input.transactionId,
      }),
    });
    if (!res.ok) {
      // 401/422/503 — the caller should show the existing
      // error UI (the MockAdModal already has a "couldn't
      // credit" branch). We return null so the caller's
      // `useMutation` knows it failed.
      return null;
    }
    const body = (await res.json()) as {
      ad_event_id: number;
      points_credited: number;
      new_balance: number;
      fx_rate_used: number;
      user_share_ngn: number;
      credit_status: 'credited' | 'rejected_low_value' | 'duplicate';
    };
    return {
      adEventId: body.ad_event_id,
      pointsCredited: body.points_credited,
      newBalance: body.new_balance,
      fxRate: body.fx_rate_used,
      userShareNgn: body.user_share_ngn,
      creditStatus: body.credit_status,
    };
  } catch (err) {
    if (__DEV__) {
      console.warn('[ads] claimAdReward failed', err);
    }
    return null;
  }
}
