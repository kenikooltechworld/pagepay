/**
 * BannerAd
 *
 * Top- or bottom-of-screen banner slot. Renders the real
 * AdMob banner (via `react-native-google-mobile-ads`) when
 * the unit ID is present and the SDK is available; falls back
 * to `AdPlaceholder` for dev / no-fill / missing SDK scenarios.
 *
 * Usage:
 *   <BannerAd adUnit={unitId} />
 *
 * The component is a thin pass-through — it never queries
 * the config itself. Callers (e.g. the layout or the catalog
 * screen) call `useAdsConfig()` and pass the resolved unit
 * ID in. This keeps the config fetch at the screen level so
 * the layout doesn't have to know about ads.
 */

import { useEffect, useState } from 'react';
import { View, StyleSheet, Platform } from 'react-native';

import { AdPlaceholder } from './AdPlaceholder';
import { logAdImpression } from '@/src/shared/lib/ads';


export type BannerAdProps = {
  /** AdMob banner unit ID. Empty string = "slot disabled". */
  adUnit: string;
  /** Optional session id for impression logging. */
  sessionId?: number | null;
  /** Eyebrow / body copy. Defaults to a generic Premium pitch
   *  in English; pass through to localize later. */
  body?: string;
};


export function BannerAd({ adUnit, sessionId, body }: BannerAdProps) {
  const [sdkAvailable, setSdkAvailable] = useState(false);
  const [adLoaded, setAdLoaded] = useState(false);

  // Check if real SDK is available (native build only)
  useEffect(() => {
    if (!adUnit) return;
    
    // Try to dynamically import the SDK
    (async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const { BannerAd: RealBannerAd } = require('react-native-google-mobile-ads');
        if (RealBannerAd) {
          setSdkAvailable(true);
        }
      } catch {
        // SDK not available - use placeholder
        setSdkAvailable(false);
      }
    })();
  }, [adUnit]);

  // If SDK available and unit ID present, mount real banner
  if (sdkAvailable && adUnit && Platform.OS !== 'web') {
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const { BannerAd: RealBannerAd, BannerAdSize } = require('react-native-google-mobile-ads');
      
      return (
        <View style={styles.root}>
          <RealBannerAd
            unitId={adUnit}
            size={BannerAdSize.ANCHORED_ADAPTIVE_BANNER}
            onAdLoaded={() => {
              setAdLoaded(true);
              // Log impression when banner loads
              logAdImpression({
                adType: 'banner',
                provider: 'admob',
                adUnit,
                sessionId: sessionId ?? null,
              }).catch(() => undefined);
            }}
            onAdFailedToLoad={(error) => {
              if (__DEV__) {
                console.warn('[BannerAd] Failed to load:', error);
              }
            }}
          />
        </View>
      );
    } catch (err) {
      // SDK require failed - fall through to placeholder
      if (__DEV__) {
        console.warn('[BannerAd] SDK import failed:', err);
      }
    }
  }

  // Fallback: placeholder for dev / no-fill / missing SDK
  return (
    <View style={styles.root}>
      <AdPlaceholder
        adType="banner"
        adUnit={adUnit}
        sessionId={sessionId}
        variant="banner"
        body={body}
      />
    </View>
  );
}


const styles = StyleSheet.create({
  root: {
    width: '100%',
  },
});
