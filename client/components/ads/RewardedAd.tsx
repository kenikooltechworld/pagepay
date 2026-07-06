/**
 * RewardedAd
 *
 * Server-token SSV flow for AdMob rewarded videos.
 *
 * Flow (server-authoritative — the client never tells the
 * server how much revenue the ad earned):
 *
 *   1. User taps "Watch Ad" → handleWatchAd fires.
 *   2. Client POSTs to /api/v1/ads/request-token with the slot
 *      name (e.g. "rewarded_android"). Server returns a
 *      `custom_data` string bound to a one-time AdRequest row.
 *   3. Client creates the AdMob ad request with that
 *      `custom_data` in serverSideVerificationOptions. AdMob
 *      signs the data and fires a server-to-server SSV
 *      callback when the user finishes watching.
 *   4. The server's SSV handler verifies the signature, looks
 *      up the AdRequest by token, and credits the user.
 *   5. AdEventType.CLOSED fires on the client. Client polls
 *      /api/v1/ads/recent-credits?since=<tokenIssuedAt> until
 *      a credit lands (or 15s elapses).
 *   6. onClaimed fires with the credited amount + new balance,
 *      and the parent screen invalidates ['me'] so the wallet
 *      chip updates.
 *
 * The previous implementation had the client compute revenue
 * from the AdMob `PAID` event and POST it to a
 * `/ads/reward-claim` endpoint. That endpoint was an attack
 * surface (a client could fabricate `revenue_usd` and mint
 * arbitrary points) and is now 410 Gone. The new flow has the
 * client trust the server for everything credit-related.
 */

import { useCallback, useRef, useEffect, useState } from 'react';
import { Modal, View, Text, StyleSheet, ActivityIndicator, Pressable, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { requestAdToken, pollRecentCredits } from '@/src/shared/lib/ads';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type AdState = 'loading' | 'ready' | 'showing' | 'error';

/** Slot name (e.g. "rewarded_android") used as the `ad_unit`
 *  argument to /api/v1/ads/request-token. The actual AdMob
 *  unit ID (ca-app-pub-.../...) is the `adUnit` prop and is
 *  passed straight to createForAdRequest. */
export type RewardedAdProps = {
  /** Whether the modal is currently shown. Parent-controlled. */
  visible: boolean;
  /** AdMob rewarded unit ID (e.g. "ca-app-pub-.../..."). */
  adUnit: string;
  /** Slot name (e.g. "rewarded_android") used when requesting
   *  the server-issued ad-request token. */
  adUnitName: string;
  /** Current user ID for SSV customData. Required. */
  userId: number;
  /** Title shown in modal. */
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
  /** Called when the credit is confirmed (or, with `pending:
   *  true`, when the poll budget ran out and the credit is
   *  still in flight server-side). */
  onClaimed: (info: {
    pointsCredited: number;
    newBalance: number;
    /** True if the poll timed out — the credit is still
     *  expected to land but the client didn't observe it.
     *  Parents should show a "credit pending" toast and
     *  still advance the user (the credit will appear on
     *  the next /auth/me refresh). */
    pending?: boolean;
  }) => void;
  /** Called when the user skips without watching. */
  onSkipped?: () => void;
  /** Called when the modal closes. */
  onClose: () => void;
};

export function RewardedAd(props: RewardedAdProps) {
  const {
    visible,
    adUnit,
    adUnitName,
    userId,
    title,
    eyebrow,
    body,
    claimLabel = 'Watch Ad',
    allowSkip = false,
    skipLabel = 'Skip',
    onClaimed,
    onSkipped,
    onClose,
  } = props;

  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const [adState, setAdState] = useState<AdState>('loading');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const rewardedRef = useRef<any>(null);
  const rewardDataRef = useRef<{ type: string; amount: number } | null>(null);
  const hasLoadedRef = useRef(false); // Track if we've loaded for this modal open
  // The freshly-issued AdRequest token + the timestamp captured
  // right before requesting it. The poll uses this timestamp to
  // scope /recent-credits to "credits that landed during/after
  // this ad" so we don't accidentally pick up an unrelated
  // credit from earlier in the session.
  const tokenIssuedAtRef = useRef<string | null>(null);
  // AbortController for the in-flight pollRecentCredits. The
  // AdEventType.CLOSED handler awaits this; if the component
  // unmounts mid-poll (user navigated away), the controller
  // aborts and the loop exits cleanly.
  const pollAbortRef = useRef<AbortController | null>(null);

  // Load ad when modal opens
  useEffect(() => {
    // Only load if modal is visible AND we haven't loaded yet
    if (!visible) {
      // Modal closed - reset for next time
      hasLoadedRef.current = false;
      return;
    }

    if (Platform.OS === 'web' || !adUnit || !userId || hasLoadedRef.current) {
      return;
    }

    // Mark as loaded for this modal session
    hasLoadedRef.current = true;
    setAdState('loading');
    setErrorMessage(null);

    if (__DEV__) {
      console.log('[RewardedAd] Loading ad...');
    }

    (async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const sdk = require('react-native-google-mobile-ads');
        const { RewardedAd: RealRewardedAd, RewardedAdEventType } = sdk;

        // Step 2: ask the server for a one-time AdRequest token.
        // The returned `custom_data` carries the token into the
        // SDK; AdMob signs it as part of the SSV callback. We
        // capture the timestamp BEFORE the request so the
        // post-ad poll can scope /recent-credits to "credits
        // that landed from this point on."
        tokenIssuedAtRef.current = new Date().toISOString();
        const { custom_data } = await requestAdToken(adUnitName);

        const ad = RealRewardedAd.createForAdRequest(adUnit, {
          serverSideVerificationOptions: {
            userId: userId.toString(),
            customData: custom_data,
          },
        });

        // Ad loaded successfully
        const unsubLoaded = ad.addAdEventListener(RewardedAdEventType.LOADED, () => {
          if (__DEV__) {
            console.log('[RewardedAd] Ad ready');
          }
          setAdState('ready');
        });

        // User earned reward
        const unsubEarned = ad.addAdEventListener(RewardedAdEventType.EARNED_REWARD, (reward: { type: string; amount: number }) => {
          if (__DEV__) {
            console.log('[RewardedAd] Reward earned:', reward);
          }
          rewardDataRef.current = reward;
        });

        // Ad closed. This is where the credit polling kicks in.
        const unsubClosed = ad.addAdEventListener(RewardedAdEventType.CLOSED, async () => {
          if (__DEV__) {
            console.log('[RewardedAd] Ad closed');
          }

          // Cleanup listeners
          unsubLoaded();
          unsubEarned();
          unsubClosed();

          // Cleanup ad
          rewardedRef.current = null;

          // Handle reward or skip
          if (rewardDataRef.current) {
            await handleRewardClaimed();
            rewardDataRef.current = null;
          } else {
            // No EARNED_REWARD event = user closed the ad before
            // completing it. No credit will land server-side.
            // Match the legacy behavior: skip → onSkipped.
            onSkipped?.();
            onClose();
          }
        });

        rewardedRef.current = ad;
        ad.load();

      } catch (err) {
        if (__DEV__) {
          console.error('[RewardedAd] Load failed:', err);
        }
        setAdState('error');
        setErrorMessage(err instanceof Error ? err.message : 'Ad service unavailable');
      }
    })();

    // Cleanup on unmount: abort any in-flight poll so the
    // /recent-credits loop exits cleanly when the user
    // navigates away mid-ad.
    return () => {
      pollAbortRef.current?.abort();
      pollAbortRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, adUnit, adUnitName, userId, onSkipped, onClose]);

  // Step 4-6: poll for the credit. This is the core of the
  // server-authoritative flow — the AdMob SDK has already
  // fired the SSV callback by now (or is about to), and the
  // server is the only authority on whether the credit
  // actually landed. We poll /recent-credits until it shows
  // up or 15s elapses.
  const handleRewardClaimed = useCallback(async () => {
    const since = tokenIssuedAtRef.current ?? new Date(Date.now() - 60_000).toISOString();
    const controller = new AbortController();
    pollAbortRef.current = controller;

    try {
      const credit = await pollRecentCredits(since, { signal: controller.signal });
      if (credit) {
        onClaimed({
          pointsCredited: credit.points_credited,
          newBalance: credit.new_balance,
        });
      } else {
        // Poll budget ran out. The credit may still land — the
        // next /auth/me refresh will show it. Fire onClaimed
        // with pending=true so the parent can show a "credit
        // pending" toast but still advance the user.
        if (__DEV__) {
          console.log('[RewardedAd] pollRecentCredits returned null — credit may still be in flight');
        }
        onClaimed({ pointsCredited: 0, newBalance: 0, pending: true });
      }
    } catch (err) {
      if (__DEV__) {
        console.error('[RewardedAd] pollRecentCredits threw', err);
      }
      onClaimed({ pointsCredited: 0, newBalance: 0, pending: true });
    } finally {
      pollAbortRef.current = null;
      onClose();
    }
  }, [onClaimed, onClose]);

  const handleWatchAd = useCallback(() => {
    if (!rewardedRef.current || adState !== 'ready') {
      if (__DEV__) {
        console.warn('[RewardedAd] Cannot show ad - state:', adState);
      }
      return;
    }

    try {
      setAdState('showing');
      rewardedRef.current.show();

      if (__DEV__) {
        console.log('[RewardedAd] Ad showing');
      }
    } catch (err) {
      if (__DEV__) {
        console.error('[RewardedAd] Failed to show ad:', err);
      }
      setAdState('error');
      setErrorMessage('Failed to display ad');
    }
  }, [adState]);

  const handleSkip = useCallback(() => {
    onSkipped?.();
    onClose();
  }, [onSkipped, onClose]);

  const handleRetry = useCallback(() => {
    setErrorMessage(null);
    hasLoadedRef.current = false; // Reset to allow retry
    setAdState('loading');
  }, []);

  // Don't render modal when not visible or when showing fullscreen ad
  if (!visible || adState === 'showing') {
    return null;
  }

  return (
    <Modal visible transparent animationType="fade" onRequestClose={allowSkip ? handleSkip : undefined}>
      <View style={styles.overlay}>
        <View style={[styles.modal, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          {/* Eyebrow */}
          {eyebrow && (
            <Text style={[styles.eyebrow, { color: tokens.inkMuted }]}>
              {eyebrow}
            </Text>
          )}

          {/* Title */}
          <Text style={[styles.title, { color: tokens.ink }]}>{title}</Text>

          {/* Body */}
          {body && (
            <Text style={[styles.body, { color: tokens.inkMuted }]}>
              {body}
            </Text>
          )}

          {/* State-specific content */}
          {adState === 'loading' && (
            <View style={styles.content}>
              <ActivityIndicator size="large" color={tokens.mint} />
              <Text style={[styles.statusText, { color: tokens.inkMuted }]}>
                Loading your ad...
              </Text>
            </View>
          )}

          {adState === 'ready' && (
            <View style={styles.content}>
              <View style={[styles.iconContainer, { backgroundColor: tokens.mintSoft }]}>
                <Ionicons name="play-circle" size={48} color={tokens.mint} />
              </View>
              <Text style={[styles.statusText, { color: tokens.mint }]}>
                Your ad is ready!
              </Text>
            </View>
          )}

          {adState === 'error' && (
            <View style={styles.content}>
              <View style={[styles.iconContainer, { backgroundColor: tokens.signalSoft }]}>
                <Ionicons name="alert-circle" size={48} color={tokens.signal} />
              </View>
              <Text style={[styles.statusText, { color: tokens.signal }]}>
                {errorMessage || 'Ad temporarily unavailable'}
              </Text>
            </View>
          )}

          {/* Actions */}
          <View style={styles.actions}>
            {/* Loading state - show disabled button */}
            {adState === 'loading' && (
              <View style={[styles.button, styles.primaryButton, { backgroundColor: tokens.inkMuted, opacity: 0.5 }]}>
                <ActivityIndicator size="small" color="#fff" style={{ marginRight: 8 }} />
                <Text style={styles.buttonText}>Loading ad...</Text>
              </View>
            )}

            {/* Ready state - show enabled button */}
            {adState === 'ready' && (
              <Pressable
                onPress={handleWatchAd}
                style={({ pressed }) => [
                  styles.button,
                  styles.primaryButton,
                  { backgroundColor: tokens.mint, opacity: pressed ? 0.8 : 1 },
                ]}
              >
                <Ionicons name="play" size={20} color="#fff" style={{ marginRight: 8 }} />
                <Text style={styles.buttonText}>{claimLabel}</Text>
              </Pressable>
            )}

            {/* Error state - show retry button */}
            {adState === 'error' && (
              <Pressable
                onPress={handleRetry}
                style={({ pressed }) => [
                  styles.button,
                  styles.primaryButton,
                  { backgroundColor: tokens.mint, opacity: pressed ? 0.8 : 1 },
                ]}
              >
                <Ionicons name="refresh" size={20} color="#fff" style={{ marginRight: 8 }} />
                <Text style={styles.buttonText}>Try Again</Text>
              </Pressable>
            )}

            {/* Skip button - always available */}
            {allowSkip && (
              <Pressable
                onPress={handleSkip}
                style={({ pressed }) => [
                  styles.button,
                  styles.secondaryButton,
                  { opacity: pressed ? 0.6 : 1 },
                ]}
              >
                <Text style={[styles.secondaryButtonText, { color: tokens.inkMuted }]}>
                  {skipLabel}
                </Text>
              </Pressable>
            )}
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modal: {
    width: '100%',
    maxWidth: 400,
    borderRadius: 24,
    borderWidth: 1,
    padding: 24,
    gap: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.15,
    shadowRadius: 16,
    elevation: 8,
  },
  eyebrow: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 1,
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    letterSpacing: -0.5,
  },
  body: {
    fontSize: 14,
    lineHeight: 20,
  },
  content: {
    alignItems: 'center',
    paddingVertical: 24,
    gap: 16,
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    justifyContent: 'center',
    alignItems: 'center',
  },
  statusText: {
    fontSize: 15,
    fontWeight: '600',
    textAlign: 'center',
  },
  actions: {
    gap: 12,
    marginTop: 8,
  },
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 12,
  },
  primaryButton: {
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 2,
  },
  buttonText: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '700',
  },
  secondaryButton: {
    backgroundColor: 'transparent',
  },
  secondaryButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },
});
