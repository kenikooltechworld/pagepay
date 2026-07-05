/**
 * RewardedAd
 *
 * Professional AdMob rewarded ad implementation with:
 * - Ad preloads ONLY when visible becomes true (no background loading)
 * - State machine UI (loading → ready → showing → completed)
 * - Single ad instance per modal open (no recreation loops)
 * - SSV configuration for production revenue
 */

import { useCallback, useRef, useEffect, useState } from 'react';
import { Modal, View, Text, StyleSheet, ActivityIndicator, Pressable, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { claimAdReward, logAdImpression } from '@/src/shared/lib/ads';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type AdState = 'loading' | 'ready' | 'showing' | 'error';

export type RewardedAdProps = {
  /** Whether the modal is currently shown. Parent-controlled. */
  visible: boolean;
  /** AdMob rewarded unit ID. */
  adUnit: string;
  /** Current user ID for SSV custom_data. Required for production. */
  userId: number;
  /** Optional session id for impression + claim logging. */
  sessionId?: number | null;
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
  /** Called when the user completes the ad and earns reward. */
  onClaimed: (info: {
    adEventId: number;
    pointsCredited: number;
    newBalance: number;
  }) => void;
  /** Called when the user skips without claiming. */
  onSkipped?: () => void;
  /** Called when the modal closes. */
  onClose: () => void;
};

export function RewardedAd(props: RewardedAdProps) {
  const {
    visible,
    adUnit,
    userId,
    sessionId,
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
  // Captures the real revenue from the AdMob PAID event (in micro-units).
  // Passed to claimAdReward so the backend credits based on actual ad earnings.
  const paidRevenueRef = useRef<number>(0);

  // Handle reward claim
  const handleRewardClaim = useCallback(async () => {
    const transactionId = `rewarded-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    // Convert AdMob micro-units (millionths of USD) to USD.
    // If no PAID event fired yet, fall back to 0.00035 (Nigeria
    // AdMob CPM averages ~$0.35 per 1k impressions = $0.00035 per ad).
    const revenueUsd = paidRevenueRef.current > 0
      ? paidRevenueRef.current / 1_000_000
      : 0.00035;
    const result = await claimAdReward({
      adEventId: null,
      adType: 'rewarded',
      provider: 'admob',
      adUnit: adUnit || 'unknown',
      revenueUsd,
      transactionId,
    });

    if (result && result.creditStatus === 'credited') {
      onClaimed({
        adEventId: result.adEventId,
        pointsCredited: result.pointsCredited,
        newBalance: result.newBalance,
      });
    }
    onClose();
  }, [adUnit, onClaimed, onClose]);

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
        const { RewardedAd: RealRewardedAd, RewardedAdEventType, AdEventType } = sdk;

        const ad = RealRewardedAd.createForAdRequest(adUnit, {
          serverSideVerificationOptions: {
            userId: userId.toString(),
            customData: JSON.stringify({ user_id: userId }),
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

        // Real ad revenue from AdMob (in micro-units — millionths of USD).
        // This fires after the SDK resolves the impression-level revenue.
        const unsubPaid = ad.addAdEventListener(AdEventType.PAID, (event: { currency: string; value: number }) => {
          if (__DEV__) {
            console.log('[RewardedAd] Paid event:', event);
          }
          if (event.value > 0) {
            paidRevenueRef.current = event.value;
          }
        });

        // Ad closed
        const unsubClosed = ad.addAdEventListener(AdEventType.CLOSED, async () => {
          if (__DEV__) {
            console.log('[RewardedAd] Ad closed');
          }

          // Cleanup listeners
          unsubLoaded();
          unsubEarned();
          unsubPaid();
          unsubClosed();

          // Cleanup ad
          rewardedRef.current = null;

          // Handle reward or skip
          if (rewardDataRef.current) {
            await handleRewardClaim();
            rewardDataRef.current = null;
          } else {
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
        setErrorMessage('Ad service unavailable');
      }
    })();
  }, [visible, adUnit, userId, handleRewardClaim, onSkipped, onClose]);

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
      
      // Log impression
      logAdImpression({
        adType: 'rewarded',
        provider: 'admob',
        adUnit,
        sessionId: sessionId ?? null,
      }).catch(() => undefined);
    } catch (err) {
      if (__DEV__) {
        console.error('[RewardedAd] Failed to show ad:', err);
      }
      setAdState('error');
      setErrorMessage('Failed to display ad');
    }
  }, [adState, adUnit, sessionId]);

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
