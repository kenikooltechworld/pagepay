/**
 * NativeAdBanner
 *
 * In-feed native ad card. Drop-in replacement for the
 * sponsored slot in the catalog list — same shape as
 * `ContentCard` so the FlatList doesn't have to branch.
 *
 * Renders the real AdMob Native Advanced view (via the
 * future `react-native-google-mobile-ads` binding) when
 * the unit ID is present; falls back to `AdPlaceholder`
 * for the dev / no-fill branch.
 *
 * Why a "card" shape and not a "banner" shape: the spec
 * says "native advanced unit for feed ads that shows while
 * user scroll" — AdMob's Native Advanced is a card-style
 * ad where the head/body/icon/media can each be styled.
 * The component keeps the card surface so the user can't
 * tell it apart from a regular ContentCard at a glance.
 */

import { AdPlaceholder } from './AdPlaceholder';


export type NativeAdBannerProps = {
  /** AdMob native unit ID for in_feed slot. Empty = disabled. */
  adUnit: string;
  /** Optional session id for impression logging. */
  sessionId?: number | null;
  /** Optional tap handler — defaults to no-op for ad cards. */
  onPress?: () => void;
};


export function NativeAdBanner({ adUnit, sessionId, onPress }: NativeAdBannerProps) {
  // Future: branch on adUnit presence to mount
  // <NativeAdView ref={ref} onAdPaid={...} /> from
  // react-native-google-mobile-ads. The placeholder stays
  // as the fallback.
  return (
    <AdPlaceholder
      adType="native"
      adUnit={adUnit}
      sessionId={sessionId}
      variant="inline"
      onPress={onPress}
    />
  );
}
