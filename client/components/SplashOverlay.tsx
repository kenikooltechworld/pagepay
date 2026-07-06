/**
 * In-app splash overlay.
 *
 * Bridges the gap between the OS-cached cold splash (a static PNG shown
 * by `expo-splash-screen`) and the first paint of `RootLayout`. Mounted
 * for ~600-900ms; calls `SplashScreen.hideAsync()` on mount to dismiss
 * the native splash, runs the entry bounce on the monogram + a slide-up
 * on the wordmark, and rides continuous ambient loops (8 floating
 * point tokens + 6 sparkle dots) until `onDone` fires.
 *
 * No Lottie — Reanimated 4 only. The motion matches `design-preview/
 * splash.html` but ported to worklets (battery-friendly, off the JS
 * thread, and survives the new architecture / Fabric renderer).
 *
 * Battery rules (from design/README §5):
 *   - Only animate `transform` (translate, scale, rotate).
 *   - Continuous loops: ≤8 floating tokens, ≤6 sparkles.
 *   - Static cold-splash PNG is the OS-cached one; never animate that
 *     image itself. This overlay is what runs *after* it.
 */
import { useEffect } from 'react';
import { Dimensions, Image, StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  cancelAnimation,
  runOnJS,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import * as SplashScreen from 'expo-splash-screen';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

const { width: SCREEN_W } = Dimensions.get('window');
const TOKEN_COUNT = 8;
const SPARKLE_COUNT = 6;

// The wordmark PNG is rasterized from `assets/brand/wordmark.svg`. We
// point to the same path used in app.json for the static splash, so
// there's a single source of truth. If you change the wordmark, regenerate
// `assets/images/splash-icon.png` from `scripts/render_icons.py`.
const WORDMARK = require('@/assets/images/splash-icon.png');
const MONOGRAM = require('@/assets/images/icon.png');

type SplashOverlayProps = {
  /** Called once the overlay has finished its exit fade. */
  onDone: () => void;
};

/**
 * One floating point token. Randomly positioned + a `+1` / `+5` / `+10`
 * label, slowly drifting up and fading out, then looping.
 */
function FloatingToken({ index }: { index: number }) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const t = useSharedValue(0);
  const xJitter = (index * 73) % 100; // 0-99 pseudo-random, stable per index

  useEffect(() => {
    t.value = 0;
    t.value = withRepeat(
      withTiming(1, {
        duration: 5400,
        easing: Easing.out(Easing.quad),
      }),
      -1,
      false,
    );
    return () => cancelAnimation(t);
  }, [t]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: -SCREEN_W * 0.4 + (xJitter / 100) * (SCREEN_W * 0.8) },
      { translateY: -t.value * 220 },
    ],
    opacity: t.value < 0.1 ? t.value * 10 : 1 - t.value,
  }));

  // +1 / +5 / +10 round-robin
  const value = ['+1', '+5', '+10'][index % 3];

  return (
    <Animated.View
      style={[
        styles.token,
        { top: '55%' },
        animatedStyle,
      ]}
    >
      <View
        style={[
          styles.tokenChip,
          {
            backgroundColor: tokens.mint,
            borderColor: tokens.paper,
          },
        ]}
      >
        <Animated.Text
          style={[
            styles.tokenText,
            { color: tokens.paper },
          ]}
        >
          {value}
        </Animated.Text>
      </View>
    </Animated.View>
  );
}

/**
 * One sparkle dot. A small mint circle that fades + scales in/out at
 * staggered positions around the monogram.
 */
function Sparkle({ index }: { index: number }) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const t = useSharedValue(0);
  // Stable pseudo-random positions per index (no Math.random in render
  // so SSR / layout passes don't shift).
  const angleDeg = (index * 60) % 360;
  const radius = 90 + (index % 3) * 18;
  const x = Math.cos((angleDeg * Math.PI) / 180) * radius;
  const y = Math.sin((angleDeg * Math.PI) / 180) * radius;

  useEffect(() => {
    t.value = withRepeat(
      withTiming(1, { duration: 1800, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => cancelAnimation(t);
  }, [t]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: x },
      { translateY: y },
      { scale: 0.3 + t.value * 0.9 },
    ],
    opacity: 0.2 + t.value * 0.8,
  }));

  return (
    <Animated.View
      style={[
        styles.sparkle,
        { backgroundColor: tokens.mint },
        animatedStyle,
      ]}
    />
  );
}

export function SplashOverlay({ onDone }: SplashOverlayProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  // 0 → 1 over 800ms with a back-out easing (the spring-y bounce).
  const entry = useSharedValue(0);
  // 1 → 0 over 250ms when we dismiss.
  const fadeOut = useSharedValue(1);

  useEffect(() => {
    let cancelled = false;

    (async () => {
      try {
        // Hide the OS-cached static splash the moment we're ready to
        // overlay our own animation. This is the contract: the static
        // image is shown until YOU call hideAsync().
        await SplashScreen.hideAsync();
      } catch {
        // hideAsync is best-effort; failures (e.g. already hidden) are
        // safe to ignore — we still want the overlay to play.
      }
      if (cancelled) return;

      entry.value = withTiming(1, {
        duration: 800,
        easing: Easing.bezier(0.34, 1.56, 0.64, 1),
      });

      // After the entry settles + a beat for the wordmark to slide up,
      // start the exit fade. Total visible time ≈ 1100ms.
      fadeOut.value = withDelay(
        1100,
        withTiming(
          0,
          { duration: 250, easing: Easing.in(Easing.cubic) },
          (finished) => {
            if (finished && !cancelled) runOnJS(onDone)();
          },
        ),
      );
    })();

    return () => {
      cancelled = true;
      cancelAnimation(entry);
      cancelAnimation(fadeOut);
    };
  }, [entry, fadeOut, onDone]);

  const monogramStyle = useAnimatedStyle(() => ({
    transform: [
      // Start small + slightly tilted, land on identity.
      {
        scale: 0.6 + entry.value * 0.4,
      },
    ],
    opacity: entry.value,
  }));

  const wordmarkStyle = useAnimatedStyle(() => ({
    transform: [{ translateY: (1 - entry.value) * 16 }],
    opacity: entry.value,
  }));

  const rootStyle = useAnimatedStyle(() => ({
    opacity: fadeOut.value,
  }));

  return (
    <Animated.View
      pointerEvents="none"
      style={[
        styles.root,
        { backgroundColor: tokens.paper },
        rootStyle,
      ]}
    >
      {/* Floating point tokens — ambient loop, runs alongside the entry. */}
      {Array.from({ length: TOKEN_COUNT }).map((_, i) => (
        <FloatingToken key={`tok-${i}`} index={i} />
      ))}

      {/* Sparkles clustered around the monogram. */}
      <View style={styles.sparkleRing}>
        {Array.from({ length: SPARKLE_COUNT }).map((_, i) => (
          <Sparkle key={`sp-${i}`} index={i} />
        ))}
      </View>

      {/* Monogram (entry bounce). */}
      <Animated.View style={[styles.monogramWrap, monogramStyle]}>
        <Image
          source={MONOGRAM}
          style={styles.monogram}
          resizeMode="contain"
        />
      </Animated.View>

      {/* Wordmark (slide-up, delayed). */}
      <Animated.View style={[styles.wordmarkWrap, wordmarkStyle]}>
        <Image
          source={WORDMARK}
          style={styles.wordmark}
          resizeMode="contain"
        />
      </Animated.View>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  root: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
  },
  monogramWrap: {
    width: 144,
    height: 144,
    alignItems: 'center',
    justifyContent: 'center',
  },
  monogram: { width: '100%', height: '100%' },
  wordmarkWrap: {
    marginTop: 28,
    width: 220,
    height: 80,
  },
  wordmark: { width: '100%', height: '100%' },
  token: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
  tokenChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    borderWidth: 1.5,
  },
  tokenText: {
    fontSize: 11,
    fontWeight: '700',
  },
  sparkle: {
    position: 'absolute',
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  sparkleRing: {
    position: 'absolute',
    alignItems: 'center',
    justifyContent: 'center',
  },
});
