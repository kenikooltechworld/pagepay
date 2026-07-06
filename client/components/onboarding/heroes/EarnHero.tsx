/**
 * HERO 1 — Read & earn.
 *
 * A book opens (left + right pages), 5 coins fall from the top of the
 * SVG in a staggered cascade, and a soft mint glow pulses behind the
 * book. Ported from `client/design-preview/onboarding.html` HERO 1.
 */
import { useEffect } from 'react';
import { View } from 'react-native';
import Svg, {
  Circle,
  Ellipse,
  G,
  Line,
  Path,
  Rect,
  Text as SvgText,
} from 'react-native-svg';
import Animated, {
  Easing,
  cancelAnimation,
  useAnimatedProps,
  useAnimatedStyle,
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

// Coin positions in the 320x320 artboard, in falling-order.
const COINS: {
  cx: number;
  startCy: number;
  r: number;
  delay: number;
  value: string;
  ring?: boolean;
}[] = [
  { cx: 84,  startCy: 60, r: 14, delay: 0,   value: '+5',  ring: true },
  { cx: 124, startCy: 40, r: 11, delay: 500, value: '+1' },
  { cx: 160, startCy: 20, r: 16, delay: 1000, value: '+10', ring: true },
  { cx: 196, startCy: 40, r: 11, delay: 1600, value: '+1' },
  { cx: 236, startCy: 60, r: 14, delay: 2100, value: '+5',  ring: true },
];

function Coin({ cx, startCy, r, delay, value, ring }: typeof COINS[number]) {
  const t = useSharedValue(0);
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  useEffect(() => {
    t.value = 0;
    t.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration: 3200, easing: Easing.in(Easing.cubic) }),
        -1,
        false,
      ),
    );
    return () => cancelAnimation(t);
  }, [t, delay]);

  const animProps = useAnimatedProps(() => ({
    transform: `translate(0, ${t.value * 200}) rotate(${t.value * 540} ${cx} ${startCy})`,
    opacity: t.value < 0.1 ? t.value * 10 : t.value > 0.85 ? (1 - t.value) * 6.5 : 1,
  }));

  return (
    <AnimatedG animatedProps={animProps}>
      <Circle cx={cx} cy={startCy} r={r} fill={tokens.mint} />
      {ring ? (
        <Circle
          cx={cx}
          cy={startCy}
          r={r - 4}
          fill="none"
          stroke={tokens.paper}
          strokeWidth={1.5}
          opacity={0.7}
        />
      ) : null}
      <SvgText
        x={cx}
        y={startCy + 4}
        textAnchor="middle"
        fill={tokens.paper}
        fontSize={r > 13 ? 9 : 8}
        fontWeight="700"
      >
        {value}
      </SvgText>
    </AnimatedG>
  );
}

export function EarnHero() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  // Book breathe (left + right pages)
  const leftPage = useSharedValue(0);
  const rightPage = useSharedValue(0);
  const book = useSharedValue(0);
  const glow = useSharedValue(0);

  useEffect(() => {
    book.value = withRepeat(
      withTiming(1, { duration: 4000, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    leftPage.value = withRepeat(
      withTiming(1, { duration: 5000, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    rightPage.value = withDelay(
      400,
      withRepeat(
        withTiming(1, { duration: 5000, easing: Easing.inOut(Easing.cubic) }),
        -1,
        true,
      ),
    );
    glow.value = withRepeat(
      withTiming(1, { duration: 3000, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => {
      cancelAnimation(book);
      cancelAnimation(leftPage);
      cancelAnimation(rightPage);
      cancelAnimation(glow);
    };
  }, [book, leftPage, rightPage, glow]);

  const bookAnimProps = useAnimatedProps(() => ({
    transform: `translate(160, 205) scale(${1 + book.value * 0.025}) translate(-160, -205)`,
  }));

  const leftPageAnimProps = useAnimatedProps(() => ({
    transform: `translate(160, 205) rotateY(${-leftPage.value * 12}) translate(-160, -205)`,
  }));

  const rightPageAnimProps = useAnimatedProps(() => ({
    transform: `translate(160, 205) rotateY(${rightPage.value * 12}) translate(-160, -205)`,
  }));

  const glowStyle = useAnimatedStyle(() => ({
    transform: [{ scale: 1 + glow.value * 0.15 }],
    opacity: 0.6 + glow.value * 0.4,
  }));

  return (
    <View style={{ flex: 1, position: 'relative' }}>
      <Animated.View
        style={[
          {
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: 240,
            height: 240,
            marginLeft: -120,
            marginTop: -120,
            borderRadius: 120,
            backgroundColor: tokens.mint,
            opacity: 0.18,
          },
          glowStyle,
        ]}
      />
      <Svg viewBox="0 0 320 320" width="100%" height="100%">
        {/* floor shadow */}
        <Ellipse cx={160} cy={282} rx={120} ry={12} fill={tokens.mint} opacity={0.1} />

        {/* book base shadow */}
        <Rect x={58} y={148} width={204} height={120} rx={10} fill="#0B5C4B" />

        <AnimatedG animatedProps={bookAnimProps}>
          {/* Left page */}
          <AnimatedG animatedProps={leftPageAnimProps}>
            <Path
              d="M60 152 L160 158 L160 258 L60 252 Z"
              fill={tokens.paper}
              stroke={tokens.mint}
              strokeWidth={3}
            />
            <Line x1={76} y1={174} x2={146} y2={176} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" opacity={0.6} />
            <Line x1={76} y1={190} x2={148} y2={192} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" opacity={0.45} />
            <Line x1={76} y1={206} x2={142} y2={208} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" opacity={0.45} />
            <Line x1={76} y1={222} x2={148} y2={224} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" opacity={0.45} />
          </AnimatedG>

          {/* Right page */}
          <AnimatedG animatedProps={rightPageAnimProps}>
            <Path
              d="M160 158 L260 152 L260 252 L160 258 Z"
              fill={tokens.card}
              stroke={tokens.mint}
              strokeWidth={3}
            />
            <Line x1={174} y1={176} x2={244} y2={174} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" />
            <Line x1={174} y1={192} x2={240} y2={190} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" opacity={0.55} />
            <Line x1={174} y1={208} x2={244} y2={206} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" opacity={0.55} />
            <Line x1={174} y1={224} x2={238} y2={222} stroke={tokens.mint} strokeWidth={3} strokeLinecap="round" opacity={0.55} />
          </AnimatedG>

          {/* book spine */}
          <Line x1={160} y1={158} x2={160} y2={258} stroke={tokens.mint} strokeWidth={2} strokeDasharray="3 4" />
        </AnimatedG>

        {/* Falling coins */}
        {COINS.map((c, i) => (
          <Coin key={i} {...c} />
        ))}
      </Svg>
    </View>
  );
}
