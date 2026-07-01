/**
 * MockAdModal
 *
 * A stand-in for a real rewarded-video ad. We render a video-like
 * placeholder (animated bars + countdown + simulated ad copy) that
 * runs for `durationSeconds` (default 30s — short enough to not feel
 * punitive, long enough to exercise the ad-playback flow). The user
 * has to sit through the full duration before the claim button
 * activates. There is no real SDK in the loop yet — Phase 2 wires
 * AdMob and replaces the body without touching the props.
 *
 * Used in two places:
 *   1. Pre-read gate ("watch to earn from this read")
 *   2. Post-read gate ("watch to lock in your points")
 *
 * The component is fully self-contained: it owns its own playback
 * state (a ticking countdown + a few animated bars that progress over
 * time so the user sees the "ad" is "playing"), exposes the canonical
 * `onClaim` / `onSkip` callbacks, and never calls the network.
 *
 * `onClaim` receives a synthetic `revenue_usd` value covering the
 * realistic Nigeria rewarded-video range (AdMob $0.0006–$0.0015,
 * AppLovin MAX $0.0010–$0.0020). The parent POSTs that to
 * /api/v1/ads/credit which converts at the live USD/NGN rate. Phase 2
 * swaps the synthetic revenue for the real SDK callback's value; the
 * modal's rendering never has to change.
 */

import { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';


const DEFAULT_DURATION_SECONDS = 30;

/** Realistic per-impression USD revenue range for Nigeria.
 *
 * Sources: AdMob benchmarks $0.30–$1.80 eCPM for Nigeria tier-3
 * rewarded video; AppLovin MAX $0.50–$2.50 eCPM. eCPM is per-1,000
 * impressions, so per-impression is eCPM/1000. We round to plausible
 * micro-USD values that produce meaningful point credits after the
 * 80/20 split. Phase 2 swaps this for the real SDK callback.
 */
const AD_NETWORK_USD_RANGES = {
  admob: { min: 0.0006, max: 0.0015 },         // AdMob Nigeria
  applovin_max: { min: 0.0010, max: 0.0020 },  // AppLovin MAX Nigeria
  mock:   { min: 0.0008, max: 0.0018 },        // Dev / Phase 1 placeholder
} as const;


export type AdProvider = keyof typeof AD_NETWORK_USD_RANGES;

export type MockAdModalProps = {
  visible: boolean;
  /** Eyebrow above the title. Defaults to "Sponsored". */
  eyebrow?: string;
  /** Headline shown after the eyebrow. */
  title: string;
  /** Body copy under the title. Keep it short — it competes with the timer. */
  body?: string;
  /** What the claim button says once it activates. */
  claimLabel?: string;
  /** Skip is allowed unless explicitly disabled (some flows must be opt-in). */
  allowSkip?: boolean;
  /** Skip button label. */
  skipLabel?: string;
  /** How long the simulated ad plays before the claim button unlocks. */
  durationSeconds?: number;
  /** Which ad network we're simulating. Drives the per-impression
   *  revenue range passed to onClaim. */
  provider?: AdProvider;
  /** Called once the user taps the activated claim button.
   *  Receives the synthetic USD revenue for this impression so the
   *  parent can POST it to /api/v1/ads/credit. */
  onClaim: (revenue_usd: number) => void;
  /** Called when the user taps skip. Omitted when `allowSkip` is false. */
  onSkip?: () => void;
};


/**
 * Pick a deterministic-but-varied USD revenue for a simulated ad impression.
 *
 * We use Math.random rather than a hash so different ad watches in the
 * same session produce different points — makes the wallet update feel
 * real instead of "every ad pays exactly the same".
 */
function pickRevenueUsd(provider: AdProvider): number {
  const range = AD_NETWORK_USD_RANGES[provider] ?? AD_NETWORK_USD_RANGES.mock;
  const value = range.min + Math.random() * (range.max - range.min);
  // Round to 6 decimal places so the wire payload is small but precise.
  return Math.round(value * 1_000_000) / 1_000_000;
}


export function MockAdModal({
  visible,
  eyebrow = 'Sponsored',
  title,
  body,
  claimLabel = 'Claim',
  allowSkip = true,
  skipLabel = 'Skip',
  durationSeconds = DEFAULT_DURATION_SECONDS,
  provider = 'mock',
  onClaim,
  onSkip,
}: MockAdModalProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const [remaining, setRemaining] = useState(durationSeconds);
  // Lock the claim button until the full duration has elapsed. Skip
  // stays locked too — a free-skip would defeat the point of the gate.
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!visible) {
      // Reset on close so the next open starts fresh.
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      setRemaining(durationSeconds);
      return;
    }
    setRemaining(durationSeconds);
    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [visible, durationSeconds]);

  const ready = remaining === 0;
  // Progress 0..1 — drives the on-screen video-progress bar so the user
  // sees the ad "playing". Even at 30s we want this to feel like video,
  // not a countdown.
  const progress = 1 - remaining / durationSeconds;

  const handleClaim = () => {
    if (!ready) return;
    onClaim(pickRevenueUsd(provider));
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={() => {}}>
      <View style={styles.overlay}>
        <View style={[styles.sheet, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          <View style={styles.headerRow}>
            <Text style={[styles.eyebrow, { color: tokens.signal }]}>{eyebrow}</Text>
            <View style={[styles.dot, { backgroundColor: tokens.signalSoft }]}>
              <ActivityIndicator size="small" color={tokens.signal} />
            </View>
          </View>

          <Text style={[styles.title, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
            {title}
          </Text>

          {body ? (
            <Text style={[styles.body, { color: tokens.inkMuted }]}>{body}</Text>
          ) : null}

          {/* Video placeholder. A dark "player" surface with a simulated
              playhead + animated progress bars that move during playback
              so the user can SEE the ad playing, not just see a number
              counting down. This is what ad networks call the "ad
              surface" — the real SDK swaps this for an actual video
              element, but the visual contract (player + countdown) stays. */}
          <View style={[styles.player, { backgroundColor: tokens.ink, borderColor: tokens.border }]}>
            <View style={styles.playerBars}>
              {[0, 1, 2, 3, 4, 5, 6].map((i) => (
                <View
                  key={i}
                  style={[
                    styles.bar,
                    {
                      // Each bar lights up "above the playhead" so the
                      // block of lit bars grows left-to-right as the
                      // ad plays. Looks like an audio waveform/spectrum
                      // analyzer — the standard "this is video" hint.
                      backgroundColor:
                        i / 7 < progress ? tokens.mint : 'rgba(255,255,255,0.18)',
                    },
                  ]}
                />
              ))}
            </View>
            <View style={styles.playerOverlay}>
              <Ionicons
                name={ready ? 'checkmark-circle' : 'play-circle'}
                size={32}
                color={ready ? tokens.mint : 'rgba(255,255,255,0.85)'}
              />
              <Text style={styles.playerLabel}>
                {ready ? 'Ad finished' : `Playing · ${remaining}s`}
              </Text>
            </View>
            <View style={styles.playerProgress}>
              <View
                style={[
                  styles.playerProgressFill,
                  { backgroundColor: tokens.mint, width: `${Math.round(progress * 100)}%` },
                ]}
              />
            </View>
          </View>

          {/* Status pill below the player. Mirrors the player state in a
              short, glanceable form. */}
          <View style={[styles.timerPill, { borderColor: tokens.border }]}>
            <Ionicons
              name={ready ? 'checkmark-circle' : 'time-outline'}
              size={18}
              color={ready ? tokens.mint : tokens.inkMuted}
            />
            <Text style={[styles.timerText, { color: ready ? tokens.mint : tokens.inkMuted }]}>
              {ready ? 'Ready to claim' : `Ad plays for ${remaining}s`}
            </Text>
          </View>

          <Pressable
            onPress={handleClaim}
            disabled={!ready}
            accessibilityRole="button"
            accessibilityLabel={claimLabel}
            accessibilityState={{ disabled: !ready }}
            style={({ pressed }) => [
              styles.claim,
              {
                backgroundColor: ready ? tokens.mint : tokens.border,
                transform: [{ scale: pressed && ready ? 0.97 : 1 }],
              },
            ]}
          >
            <Text
              style={[
                styles.claimText,
                {
                  color: ready ? tokens.mintText : tokens.inkMuted,
                  fontFamily: 'SpaceGrotesk_700Bold',
                },
              ]}
            >
              {claimLabel}
            </Text>
          </Pressable>

          {allowSkip && onSkip ? (
            <Pressable
              onPress={ready ? onSkip : undefined}
              disabled={!ready}
              accessibilityRole="button"
              hitSlop={8}
              style={({ pressed }) => [
                styles.skip,
                { opacity: !ready ? 0.4 : pressed ? 0.6 : 1 },
              ]}
            >
              <Text style={[styles.skipText, { color: tokens.inkMuted }]}>{skipLabel}</Text>
            </Pressable>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
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
  dot: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
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
  // Video-like placeholder. Dark surface + animated bars + overlay
  // play/checkmark icon + progress strip. Phones it's not the real
  // ad SDK's <Video> element (Phase 2 swap), but the visual contract
  // is exactly the same: a black panel with a playhead, the user sees
  // it playing.
  player: {
    width: '100%',
    aspectRatio: 16 / 9,
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
    justifyContent: 'center',
    overflow: 'hidden',
  },
  playerBars: {
    position: 'absolute',
    top: 12,
    left: 16,
    right: 16,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    height: 28,
  },
  bar: {
    flex: 1,
    marginHorizontal: 2,
    height: '100%',
    borderRadius: 2,
  },
  playerOverlay: {
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
  },
  playerLabel: {
    color: 'rgba(255,255,255,0.85)',
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  playerProgress: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 3,
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  playerProgressFill: {
    height: 3,
  },
  timerPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    borderWidth: 1,
    alignSelf: 'flex-start',
  },
  timerText: {
    fontSize: 13,
    fontWeight: '600',
    letterSpacing: 0.2,
  },
  claim: {
    minHeight: 52,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
    marginTop: 4,
  },
  claimText: {
    fontSize: 16,
    letterSpacing: 0.1,
  },
  skip: {
    alignSelf: 'center',
    paddingVertical: 8,
  },
  skipText: {
    fontSize: 13,
    fontWeight: '500',
  },
});
