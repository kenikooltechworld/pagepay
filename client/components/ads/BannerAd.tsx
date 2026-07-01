/**
 * BannerAd
 *
 * Top- or bottom-of-screen banner slot. Renders the real
 * AdMob banner (via the future `react-native-google-mobile-ads`
 * binding) when the unit ID is present; falls back to
 * `AdPlaceholder` for the dev / no-fill branch.
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

import { View, StyleSheet } from 'react-native';

import { AdPlaceholder } from './AdPlaceholder';


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
  // Future: branch on Platform.OS + adUnit presence to mount
  // <BannerAd size="..." unitId={adUnit} /> from
  // react-native-google-mobile-ads. The placeholder stays as
  // the "no SDK / no fill" fallback so the screen never has
  // a hole.
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
