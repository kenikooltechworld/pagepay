/**
 * InterstitialAd
 *
 * Full-screen ad shown at natural break points (after
 * every 3 articles, end of a session, etc.). The component
 * is a controller — the parent decides when to call
 * `show()` and the ad is dismissed via the `onClose`
 * callback.
 *
 * With real SDK: Preloads InterstitialAd instance and calls
 * `.show()` when ready. Falls back to MockAdModal if SDK
 * unavailable.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View, Platform } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { logAdImpression } from '@/src/shared/lib/ads';


export type InterstitialAdProps = {
  /** AdMob interstitial unit ID. Empty = always no-fill. */
  adUnit: string;
  /** Optional session id for impression logging. */
  sessionId?: number | null;
  /** Whether the ad is currently shown. Parent-controlled. */
  visible: boolean;
  /** Called when the ad closes (skipped, finished, or no-fill). */
  onClose: () => void;
  /** Optional pre-close hook — fires just before the modal
   *  collapses. Use it to record analytics ("interstitial
   *  closed at 4.2s, skipped=false"). */
  onBeforeClose?: (info: { skipped: boolean; durationMs: number }) => void;
};


const MIN_DURATION_MS = 5_000;


export function InterstitialAd({
  adUnit,
  sessionId,
  visible,
  onClose,
  onBeforeClose,
}: InterstitialAdProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const startTimeRef = useRef<number | null>(null);
  const impressionLoggedRef = useRef(false);
  const [skipReady, setSkipReady] = useState(false);
  const [sdkAvailable, setSdkAvailable] = useState(false);
  const [realAdShown, setRealAdShown] = useState(false);
  const interstitialRef = useRef<any>(null);

  // Preload real SDK interstitial
  useEffect(() => {
    if (!adUnit || Platform.OS === 'web') return;

    (async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-require-imports
        const { InterstitialAd: RealInterstitialAd, AdEventType } = require('react-native-google-mobile-ads');
        
        const interstitial = RealInterstitialAd.createForAdRequest(adUnit);
        
        // Load ad in background
        const unsubscribeLoaded = interstitial.addAdEventListener(AdEventType.LOADED, () => {
          setSdkAvailable(true);
        });
        
        const unsubscribeClosed = interstitial.addAdEventListener(AdEventType.CLOSED, () => {
          setRealAdShown(false);
          onClose();
        });
        
        interstitial.load();
        interstitialRef.current = interstitial;

        return () => {
          unsubscribeLoaded();
          unsubscribeClosed();
        };
      } catch (err) {
        if (__DEV__) {
          console.warn('[InterstitialAd] SDK not available:', err);
        }
        setSdkAvailable(false);
      }
    })();
  }, [adUnit, onClose]);

  // Show real ad when visible prop becomes true
  useEffect(() => {
    if (visible && sdkAvailable && interstitialRef.current && !realAdShown) {
      interstitialRef.current.show();
      setRealAdShown(true);
      
      // Log impression
      logAdImpression({
        adType: 'interstitial',
        provider: 'admob',
        adUnit,
        sessionId: sessionId ?? null,
      }).catch(() => undefined);
      
      return;
    }
  }, [visible, sdkAvailable, realAdShown, adUnit, sessionId]);

  // If real SDK shown, don't render modal
  if (realAdShown) {
    return null;
  }

  // Fallback: Mock modal for dev/no SDK
  // Reset the skip button on every open.
  useEffect(() => {
    if (!visible) {
      setSkipReady(false);
      impressionLoggedRef.current = false;
      startTimeRef.current = null;
      return;
    }
    startTimeRef.current = Date.now();
    if (adUnit && !impressionLoggedRef.current) {
      impressionLoggedRef.current = true;
      logAdImpression({
        adType: 'interstitial',
        provider: 'mock',
        adUnit,
        sessionId: sessionId ?? null,
      }).catch(() => undefined);
    }
    const t = setTimeout(() => setSkipReady(true), MIN_DURATION_MS);
    return () => clearTimeout(t);
  }, [visible, adUnit, sessionId]);

  const handleClose = useCallback(
    (skipped: boolean) => {
      if (!skipReady && !skipped) return;
      const now = Date.now();
      const durationMs = startTimeRef.current ? now - startTimeRef.current : 0;
      onBeforeClose?.({ skipped, durationMs });
      onClose();
    },
    [skipReady, onBeforeClose, onClose],
  );

  if (!visible) return null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => handleClose(false)}>
      <View style={styles.overlay}>
        <View
          style={[
            styles.sheet,
            { backgroundColor: tokens.card, borderColor: tokens.border },
          ]}
        >
          <View style={styles.headerRow}>
            <Text style={[styles.eyebrow, { color: tokens.signal }]}>Sponsored</Text>
            {__DEV__ ? (
              <View style={[styles.devPill, { borderColor: tokens.border }]}>
                <Text style={[styles.devPillText, { color: tokens.inkMuted }]}>DEV</Text>
              </View>
            ) : null}
          </View>

          <Text
            style={[styles.title, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}
          >
            Your interstitial lives here.
          </Text>
          <Text style={[styles.body, { color: tokens.inkMuted }]}>
            The real AdMob InterstitialAd will replace this card when the native SDK is
            installed. Today this is a stand-in so the &ldquo;after every 3 articles&rdquo; trigger
            has something to show.
          </Text>

          <Pressable
            onPress={() => handleClose(false)}
            disabled={!skipReady}
            accessibilityRole="button"
            accessibilityLabel="Close ad"
            style={({ pressed }) => [
              styles.close,
              {
                backgroundColor: skipReady ? tokens.mint : tokens.border,
                transform: [{ scale: pressed && skipReady ? 0.97 : 1 }],
              },
            ]}
          >
            <Ionicons name="close" size={18} color={skipReady ? tokens.mintText : tokens.inkMuted} />
            <Text
              style={[
                styles.closeText,
                {
                  color: skipReady ? tokens.mintText : tokens.inkMuted,
                  fontFamily: 'SpaceGrotesk_700Bold',
                },
              ]}
            >
              {skipReady ? 'Continue' : `Skip in ${Math.ceil(MIN_DURATION_MS / 1000)}s`}
            </Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}


const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  sheet: {
    width: '100%',
    borderRadius: 20,
    borderWidth: 1,
    padding: 24,
    gap: 14,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  eyebrow: {
    fontSize: 11,
    lineHeight: 14,
    letterSpacing: 1.4,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  devPill: {
    borderWidth: 1,
    borderRadius: 999,
    paddingHorizontal: 6,
    paddingVertical: 2,
  },
  devPillText: {
    fontSize: 9,
    lineHeight: 12,
    letterSpacing: 0.6,
    fontWeight: '700',
  },
  title: {
    fontSize: 22,
    lineHeight: 28,
    letterSpacing: -0.4,
  },
  body: {
    fontSize: 14,
    lineHeight: 20,
  },
  close: {
    minHeight: 52,
    borderRadius: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingHorizontal: 20,
    marginTop: 4,
  },
  closeText: {
    fontSize: 16,
    letterSpacing: 0.1,
  },
});
