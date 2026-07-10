/**
 * Onboarding screen scaffold.
 *
 * Lays out one onboarding "phone screen" — faked status bar at the top,
 * a `Skip` button (right-aligned, hidden on the last screen), the
 * hero illustration (children), copy (eyebrow + headline + body), the
 * dot indicator, and a CTA button with a pulse halo and tap ripple.
 *
 * The hero is rendered as a `children` slot so each screen's hero
 * (book / study / wallet / streak / premium) is its own component.
 *
 * The CTA has a `pulse` halo (the same one from the auth login screen)
 * and a ripple effect on tap. Final-screen `Get started` taps also
 * fire the parent-supplied `onGetStarted` which kicks off the confetti.
 */
import { ReactNode, useEffect } from 'react';
import {
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { Fonts, PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { OnboardingDots } from './Dots';

type OnboardingScreenProps = {
  /** Small uppercase eyebrow above the headline. */
  eyebrow: string;
  /** H2 headline. */
  headline: string;
  /** Body copy beneath the headline. */
  body: string;
  /** True on the final screen; hides Skip and changes CTA label. */
  isLast?: boolean;
  /** Index 0..n of this screen. */
  index: number;
  /** Total number of screens (for the dot indicator). */
  total: number;
  /** Skip-jump handler; ignored when `isLast`. */
  onSkip: () => void;
  /** Next / Get started handler. */
  onPrimary: (origin: { x: number; y: number }) => void;
  /** Hero illustration. */
  children: ReactNode;
  /** Extra style overrides for the root view. */
  style?: ViewStyle;
};

/**
 * Faked iOS status bar: 9:41 clock + signal bars + wifi + battery.
 * We use this for visual fidelity with the HTML preview; the real
 * StatusBar is controlled at the layout level.
 */
function FakeStatusBar() {
  return (
    <View style={styles.status}>
      <Text style={styles.statusTime}>9:41</Text>
      <View style={styles.statusRight}>
        {/* signal bars */}
        <View style={styles.signalBars}>
          <View style={[styles.bar, { height: 4 }]} />
          <View style={[styles.bar, { height: 6 }]} />
          <View style={[styles.bar, { height: 8 }]} />
          <View style={[styles.bar, { height: 11 }]} />
        </View>
        {/* wifi glyph (3 arcs) */}
        <View style={styles.wifi}>
          <View style={[styles.wifiArc, styles.wifiArc3]} />
          <View style={[styles.wifiArc, styles.wifiArc2]} />
          <View style={styles.wifiDot} />
        </View>
        {/* battery */}
        <View style={styles.battery}>
          <View style={styles.batteryFill} />
          <View style={styles.batteryTip} />
        </View>
      </View>
    </View>
  );
}

export function OnboardingScreen({
  eyebrow,
  headline,
  body,
  isLast,
  index,
  total,
  onSkip,
  onPrimary,
  children,
  style,
}: OnboardingScreenProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  // Ripple origin captured at tap-down. These must be shared values
  // because the ripple's `useAnimatedStyle` reads them on the UI thread.
  const rippleScale = useSharedValue(0);
  const rippleOpacity = useSharedValue(0);
  const rippleX = useSharedValue(0);
  const rippleY = useSharedValue(0);

  // Halo pulse (continuous loop, not focus-gated because the CTA only
  // exists on the active screen anyway).
  const halo = useSharedValue(0);

  const haloStyle = useAnimatedStyle(() => ({
    transform: [{ scale: 1 + halo.value * 0.04 }],
    opacity: halo.value * 0.4,
  }));

  const rippleStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: rippleX.value - 180 },
      { translateY: rippleY.value - 180 },
      { scale: rippleScale.value },
    ],
    opacity: rippleOpacity.value,
  }));

  // Boot the halo pulse once on mount. The CTA is the same instance
  // across its screen's lifetime (we only swap screens, not CTAs), so
  // a mount-once pattern is fine.
  useEffect(() => {
    halo.value = withRepeat(
      withTiming(1, { duration: 1600, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => {
      cancelAnimation(halo);
    };
  }, [halo]);

  const handlePress = (e: any) => {
    // Capture the press point relative to the CTA box so the ripple
    // can expand from where the finger actually landed.
    rippleX.value = e.nativeEvent.locationX;
    rippleY.value = e.nativeEvent.locationY;
    rippleScale.value = 0;
    rippleOpacity.value = 0.6;
    rippleScale.value = withTiming(1, {
      duration: 600,
      easing: Easing.out(Easing.cubic),
    });
    rippleOpacity.value = withTiming(0, {
      duration: 600,
      easing: Easing.out(Easing.cubic),
    });
  };

  const handlePrimary = (e: any) => {
    // Get absolute screen coordinates for the confetti origin. The
    // Pressable's onPress fires after the ripple; we use
    // `pageX/pageY` (page = scrolled + screen) so the burst starts
    // at the actual tap point even if the user is mid-swipe.
    const target = e.target;
    target?.measure?.((x: number, y: number, w: number, h: number, px: number, py: number) => {
      onPrimary({ x: px + w / 2, y: py + h / 2 });
    });
  };

  return (
    <View style={[styles.root, { backgroundColor: tokens.paper }, style]}>
      <FakeStatusBar />

      <SafeAreaView style={styles.safe} edges={['bottom']}>
        <View style={styles.top}>
          {isLast ? (
            <View style={styles.skipSpacer} />
          ) : (
            <Pressable
              onPress={onSkip}
              hitSlop={10}
              accessibilityRole="button"
              accessibilityLabel="Skip"
            >
              <Text style={[styles.skip, { color: tokens.inkMuted }]}>
                Skip
              </Text>
            </Pressable>
          )}
        </View>

        <View style={styles.hero}>{children}</View>

        <View style={styles.copy}>
          <Text
            style={[
              styles.eyebrow,
              { color: tokens.mint, fontFamily: Fonts.display },
            ]}
          >
            {eyebrow}
          </Text>
          <Text
            style={[
              styles.headline,
              { color: tokens.ink, fontFamily: Fonts.display },
            ]}
          >
            {headline}
          </Text>
          <Text style={[styles.body, { color: tokens.inkMuted }]}>{body}</Text>
        </View>

        <View style={styles.footer}>
          <OnboardingDots count={total} active={index} />

          <View style={styles.ctaWrap}>
            <Animated.View
              pointerEvents="none"
              style={[styles.halo, { backgroundColor: tokens.mint }, haloStyle]}
            />
            <Pressable
              onPressIn={handlePress}
              onPress={handlePrimary}
              accessibilityRole="button"
              accessibilityLabel={isLast ? 'Get Started' : 'Next'}
            >
              <View
                style={[
                  styles.cta,
                  { backgroundColor: tokens.mint, shadowColor: tokens.mint },
                ]}
              >
                <Text
                  style={[
                    styles.ctaText,
                    { color: tokens.mintText, fontFamily: Fonts.display },
                  ]}
                >
                  {isLast ? 'Get Started' : 'Next'}
                </Text>
              </View>
            </Pressable>
            <Animated.View
              pointerEvents="none"
              style={[
                styles.ripple,
                rippleStyle,
              ]}
            />
          </View>
        </View>

        <View style={styles.homeIndicator} />
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  safe: { flex: 1, paddingHorizontal: 24, paddingBottom: 8 },
  status: {
    height: 44,
    paddingHorizontal: 24,
    flexDirection: 'row',
    alignItems: 'flex-end',
    justifyContent: 'space-between',
    paddingBottom: 6,
  },
  statusTime: {
    fontSize: 15,
    fontWeight: '600',
    color: '#0E1116',
  },
  statusRight: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 6,
  },
  signalBars: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: 2,
  },
  bar: {
    width: 3,
    backgroundColor: '#0E1116',
    borderRadius: 1,
  },
  wifi: {
    width: 14,
    height: 10,
    justifyContent: 'flex-end',
    alignItems: 'center',
  },
  wifiArc: {
    position: 'absolute',
    borderColor: '#0E1116',
    borderTopWidth: 1.6,
    borderRadius: 999,
  },
  wifiArc2: {
    width: 8,
    height: 8,
    bottom: 1,
  },
  wifiArc3: {
    width: 14,
    height: 14,
    bottom: 0,
  },
  wifiDot: {
    width: 2,
    height: 2,
    borderRadius: 1,
    backgroundColor: '#0E1116',
    marginBottom: 0,
  },
  battery: {
    width: 24,
    height: 11,
    borderWidth: 1,
    borderColor: '#0E1116',
    borderRadius: 2.5,
    flexDirection: 'row',
    alignItems: 'center',
    padding: 1,
  },
  batteryFill: {
    flex: 1,
    backgroundColor: '#0E1116',
    borderRadius: 1,
  },
  batteryTip: {
    width: 1.5,
    height: 4,
    backgroundColor: '#0E1116',
    marginLeft: 0.5,
    borderTopRightRadius: 1,
    borderBottomRightRadius: 1,
  },
  top: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    paddingTop: 8,
    height: 40,
  },
  skipSpacer: { width: 1 },
  skip: {
    fontSize: 14,
    fontWeight: '500',
  },
  hero: {
    marginTop: 18,
    width: '100%',
    aspectRatio: 1,
    borderRadius: 28,
    backgroundColor: 'transparent',
    overflow: 'visible',
  },
  copy: {
    marginTop: 28,
    gap: 10,
  },
  eyebrow: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 1.6,
  },
  headline: {
    fontSize: 30,
    fontWeight: '700',
    letterSpacing: -0.6,
    lineHeight: 34,
  },
  body: {
    fontSize: 15,
    lineHeight: 22,
  },
  footer: {
    marginTop: 'auto',
    gap: 22,
    alignItems: 'stretch',
  },
  ctaWrap: {
    position: 'relative',
  },
  halo: {
    position: 'absolute',
    top: -2,
    left: -2,
    right: -2,
    bottom: -2,
    borderRadius: 16,
  },
  cta: {
    borderRadius: 14,
    paddingVertical: 17,
    alignItems: 'center',
    justifyContent: 'center',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.28,
    shadowRadius: 20,
    elevation: 4,
  },
  ctaText: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.1,
  },
  ripple: {
    position: 'absolute',
    width: 360,
    height: 360,
    borderRadius: 180,
    backgroundColor: 'rgba(255,255,255,0.45)',
    top: 0,
    left: 0,
  },
  homeIndicator: {
    width: 134,
    height: 5,
    borderRadius: 2.5,
    backgroundColor: '#0E1116',
    alignSelf: 'center',
    marginTop: 12,
    opacity: 0.85,
  },
});
