/**
 * HERO 5 — Go premium.
 *
 * A crown with band + jewels + tips, an aura circle behind it, 4
 * corner sparks twinkling, a "2× POINTS" badge that pops beneath the
 * crown, and a "PREMIUM" eyebrow chip. Ported from HERO 5 in
 * `client/design-preview/onboarding.html`.
 */
import { useEffect } from 'react';
import Svg, { Circle, Ellipse, G, Path, Rect, Text as SvgText } from 'react-native-svg';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedProps,
  useSharedValue,
  withDelay,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

// `<G>` from react-native-svg doesn't accept React Native `style`, so we
// drive its `transform` prop with a string and `useAnimatedProps`.
const AnimatedG = Animated.createAnimatedComponent(G);

const SPARKS: {
  cx: number; cy: number; path: string; delay: number;
}[] = [
  { cx: 80,  cy: 80,  path: 'M 0 0 L 2 6 L 8 8 L 2 10 L 0 16 L -2 10 L -8 8 L -2 6 Z', delay: 0 },
  { cx: 240, cy: 90,  path: 'M 0 0 L 2 6 L 8 8 L 2 10 L 0 16 L -2 10 L -8 8 L -2 6 Z', delay: 600 },
  { cx: 70,  cy: 180, path: 'M 0 0 L 2 4 L 6 6 L 2 8 L 0 12 L -2 8 L -6 6 L -2 4 Z', delay: 1200 },
  { cx: 250, cy: 170, path: 'M 0 0 L 2 4 L 6 6 L 2 8 L 0 12 L -2 8 L -6 6 L -2 4 Z', delay: 1800 },
];

function CrownSpark({ cx, cy, path, delay }: typeof SPARKS[number]) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const t = useSharedValue(0);

  useEffect(() => {
    t.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration: 2400, easing: Easing.inOut(Easing.cubic) }),
        -1,
        true,
      ),
    );
    return () => cancelAnimation(t);
  }, [t, delay]);

  // Scale + rotate around the spark's own center (cx, cy).
  const animProps = useAnimatedProps(() => ({
    transform: `translate(${cx} ${cy}) scale(${0.4 + t.value * 0.8}) rotate(${t.value * 45}) translate(${-cx} ${-cy})`,
    opacity: t.value,
  }));

  return (
    <AnimatedG animatedProps={animProps}>
      <Path d={path} fill={tokens.mint} transform={`translate(${cx}, ${cy})`} />
    </AnimatedG>
  );
}

export function PremiumHero() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const crown = useSharedValue(0);
  const aura = useSharedValue(0);
  const badge = useSharedValue(0);
  const eyebrow = useSharedValue(0);

  useEffect(() => {
    crown.value = withRepeat(
      withTiming(1, { duration: 3200, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    aura.value = withRepeat(
      withTiming(1, { duration: 2600, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    badge.value = withRepeat(
      withTiming(1, { duration: 1800, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    eyebrow.value = withRepeat(
      withTiming(1, { duration: 2000, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => {
      cancelAnimation(crown);
      cancelAnimation(aura);
      cancelAnimation(badge);
      cancelAnimation(eyebrow);
    };
  }, [crown, aura, badge, eyebrow]);

  // Crown: bob up/down + slight rotation around its own center (160, 130).
  const crownProps = useAnimatedProps(() => ({
    transform: `translate(160 130) rotate(${-crown.value * 2}) translate(0 ${-crown.value * 6}) translate(-160 -130)`,
  }));

  // Aura: scale + opacity around (160, 140).
  const auraProps = useAnimatedProps(() => ({
    transform: `translate(160 140) scale(${1 + aura.value * 0.18}) translate(-160 -140)`,
    opacity: 0.3 + aura.value * 0.25,
  }));

  // Badge: scale around (160, 244).
  const badgeProps = useAnimatedProps(() => ({
    transform: `translate(160 244) scale(${1 + badge.value * 0.06}) translate(-160 -244)`,
  }));

  // Eyebrow: scale around (160, 200).
  const eyebrowProps = useAnimatedProps(() => ({
    transform: `translate(160 200) scale(${1 + eyebrow.value * 0.05}) translate(-160 -200)`,
  }));

  return (
    <Svg viewBox="0 0 320 320" width="100%" height="100%">
      <Ellipse cx={160} cy={282} rx={120} ry={12} fill={tokens.mint} opacity={0.1} />

      {/* Aura */}
      <AnimatedG animatedProps={auraProps}>
        <Circle cx={160} cy={140} r={100} fill={tokens.mintSoft} opacity={0.6} />
      </AnimatedG>

      {/* Crown */}
      <AnimatedG animatedProps={crownProps}>
        <G transform="translate(160, 130)">
          <Path
            d="M -50 10 L -50 -10 L -32 -28 L -16 -8 L 0 -34 L 16 -8 L 32 -28 L 50 -10 L 50 10 Z"
            fill={tokens.mint}
          />
          <Rect x={-50} y={10} width={100} height={14} rx={2} fill="#0B5C4B" />
          <Circle cx={-30} cy={17} r={3} fill="#FBBF24" />
          <Circle cx={0}   cy={17} r={3.5} fill="#C2410C" />
          <Circle cx={30}  cy={17} r={3} fill="#FBBF24" />
          <Circle cx={-32} cy={-28} r={4} fill="#FBBF24" />
          <Circle cx={0}   cy={-34} r={5} fill="#C2410C" />
          <Circle cx={32}  cy={-28} r={4} fill="#FBBF24" />
        </G>
      </AnimatedG>

      {/* Sparkles */}
      {SPARKS.map((s, i) => (
        <CrownSpark key={i} {...s} />
      ))}

      {/* Premium eyebrow */}
      <AnimatedG animatedProps={eyebrowProps}>
        <Rect x={124} y={190} width={72} height={20} rx={10} fill={tokens.mint} />
        <SvgText
          x={160}
          y={204}
          textAnchor="middle"
          fill={tokens.paper}
          fontSize={10}
          fontWeight="700"
          letterSpacing={1.2}
        >
          PREMIUM
        </SvgText>
      </AnimatedG>

      {/* 2× POINTS badge */}
      <AnimatedG animatedProps={badgeProps}>
        <Rect x={100} y={220} width={120} height={48} rx={24} fill={tokens.paper} stroke={tokens.mint} strokeWidth={3} />
        <SvgText
          x={160}
          y={252}
          textAnchor="middle"
          fill={tokens.mint}
          fontSize={22}
          fontWeight="700"
        >
          2× POINTS
        </SvgText>
      </AnimatedG>
    </Svg>
  );
}
