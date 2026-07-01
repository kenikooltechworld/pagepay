/**
 * RewardedAd
 *
 * The "double earn" rewarded video slot shown after a
 * reading session completes. Parent calls `claim` (after
 * the user taps the activated claim button) and the
 * component:
 *   1. POSTs to /api/v1/ads/reward-claim with the synthetic
 *      `revenueUsd` the caller passed (or, with the real
 *      SDK, the value the SDK reported in onAdPaid).
 *   2. Returns the credit outcome to the parent so the
 *      wallet can re-fetch its balance.
 *
 * Today this is a thin wrapper around the existing
 * `MockAdModal` (Phase 1 placeholder) — the modal has the
 * same surface (`visible`, `onClaim(revenue)`, `onSkip`)
 * the real rewarded ad SDK will use, so the parent code
 * stays the same when the SDK lands. The wrapper layer
 * adds the impression + claim API calls the spec calls
 * out at `.kilo/command/phase2-ads.md` step 4.
 *
 * Why split RewardedAd from MockAdModal: the modal knows
 * how to render the "playing ad" surface; RewardedAd knows
 * how to translate a successful claim into a server-side
 * credit. When the real SDK lands, the modal body is
 * replaced with a `<RewardedAd>` from
 * `react-native-google-mobile-ads` and the wrapper code
 * (impression log, claim call) stays put.
 */

import { useCallback, useRef } from 'react';
import { Alert } from 'react-native';

import {
  AdProvider,
  MockAdModal,
  MockAdModalProps,
} from '@/components/MockAdModal';
import { claimAdReward, logAdImpression } from '@/src/shared/lib/ads';


export type RewardedAdProps = {
  /** Whether the modal is currently shown. Parent-controlled. */
  visible: boolean;
  /** AdMob rewarded unit ID. Empty = "use mock provider". */
  adUnit: string;
  /** Optional session id for impression + claim logging. */
  sessionId?: number | null;
  /** Title shown above the simulated player. */
  title: string;
  /** Eyebrow above the title. */
  eyebrow?: string;
  /** Body copy under the title. */
  body?: string;
  /** Claim button label. */
  claimLabel?: string;
  /** Whether the user is allowed to skip without claiming. */
  allowSkip?: boolean;
  /** Skip button label. */
  skipLabel?: string;
  /** How long the simulated ad plays before the claim
   *  button unlocks. Real SDK ignores this. */
  durationSeconds?: number;
  /** Which provider we're simulating. Real SDK ignores this. */
  provider?: AdProvider;
  /** Called when the user taps the activated claim button.
   *  Receives the new wallet balance from the server (so
   *  the parent can update the cached balance without
   *  an extra round-trip) and the `ad_event_id` the
   *  server logged. */
  onClaimed: (info: {
    adEventId: number;
    pointsCredited: number;
    newBalance: number;
  }) => void;
  /** Called when the user skips without claiming. */
  onSkipped?: () => void;
  /** Called when the modal closes (claim, skip, or error). */
  onClose: () => void;
};


export function RewardedAd(props: RewardedAdProps) {
  const {
    visible,
    adUnit,
    sessionId,
    title,
    eyebrow,
    body,
    claimLabel,
    allowSkip,
    skipLabel,
    durationSeconds,
    provider = 'mock',
    onClaimed,
    onSkipped,
    onClose,
  } = props;

  // We log the impression once per modal-open. The ref
  // dedupes if React re-renders while the modal is up.
  const impressionLoggedRef = useRef(false);
  if (visible && !impressionLoggedRef.current) {
    impressionLoggedRef.current = true;
    logAdImpression({
      adType: 'rewarded',
      provider: adUnit ? 'admob' : 'mock',
      adUnit: adUnit || 'mock_unit',
      sessionId: sessionId ?? null,
    }).catch(() => undefined);
  }

  const handleModalClose = useCallback(() => {
    // Reset the impression dedupe so the next open logs again.
    impressionLoggedRef.current = false;
    onClose();
  }, [onClose]);

  const handleClaim = useCallback(
    async (revenueUsd: number) => {
      // SSV-style dedupe key. Unique per claim attempt; replays
      // are no-ops server-side. We mint a fresh id per claim
      // so a user retrying after a network blip doesn't
      // accidentally short-circuit to "duplicate".
      const transactionId = `rewarded-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
      const result = await claimAdReward({
        adEventId: null, // the impression log is best-effort; claim creates its own row if missing
        adType: 'rewarded',
        provider: adUnit ? 'admob' : 'mock',
        adUnit: adUnit || 'mock_unit',
        revenueUsd,
        transactionId,
      });
      if (!result) {
        Alert.alert(
          'Couldn\'t credit your reward',
          'The server is unreachable. Your points will land once you\'re back online.',
        );
        handleModalClose();
        return;
      }
      if (result.creditStatus === 'rejected_low_value') {
        Alert.alert(
          'Reward too small to credit',
          'This ad paid under the minimum threshold. Try another ad to earn.',
        );
        handleModalClose();
        return;
      }
      if (result.creditStatus === 'duplicate') {
        // We just sent a unique tx id, so this should be
        // impossible — but the server is the source of truth.
        // Treat as a soft no-op so the user doesn't lose
        // their state.
        handleModalClose();
        return;
      }
      onClaimed({
        adEventId: result.adEventId,
        pointsCredited: result.pointsCredited,
        newBalance: result.newBalance,
      });
      handleModalClose();
    },
    [adUnit, onClaimed, handleModalClose],
  );

  const handleSkip = useCallback(() => {
    onSkipped?.();
    handleModalClose();
  }, [onSkipped, handleModalClose]);

  const modalProps: MockAdModalProps = {
    visible,
    title,
    eyebrow,
    body,
    claimLabel,
    allowSkip,
    skipLabel,
    durationSeconds,
    provider,
    onClaim: handleClaim,
    onSkip: allowSkip ? handleSkip : undefined,
  };

  return <MockAdModal {...modalProps} />;
}
