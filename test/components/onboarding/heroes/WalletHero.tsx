/**
 * HERO 3 — Cash out / premium.
 *
 * A wallet (mint body with a deep-mint flap that periodically opens),
 * 3 coins dropping onto a stack on the right, a pulsing ₦ on top of
 * the stack with 3 trail ₦ symbols rising, a payment-glyph chip on
 * the top-left, and an NGN note peeking out of the wallet. Ported from
 * `client/design-preview/onboarding.html` HERO 3.
 */
import { useEffect } from 'react';
import Svg, { Circle, Ellipse, G, Line, Path, Rect, Text as SvgText } from 'react-native-svg';
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

const STACK_COINS = [
  { y: 194, delay: 0 },
  { y: 170, delay: 250 },
  { y: 146, delay: 500 },
];

const TRAIL_SYMBOLS = [
  { y: 100, size: 14, delay: 0,   opacity: 0.6 },
  { y: 100, size: 11, delay: 600, opacity: 0.5 },
  { y: 100, size: 8,  delay: 1200, opacity: 0.4 },
];

function StackCoin({ y, delay }: { y: number; delay: number }) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const t = useSharedValue(0);

  useEffect(() => {
    t.value = 0;
    t.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration: 2400, easing: Easing.out(Easing.cubic) }),
        -1,
        false,
      ),
    );
    return () => cancelAnimation(t);
  }, [t, delay]);

  const animProps = useAnimatedProps(() => ({
    transform: `translate(0 ${(1 - t.value) * -50})`,
    opacity: t.value,
  }));

  return (
    <AnimatedG animatedProps={animProps}>
      <Rect x={208} y={y} width={72} height={22} fill={tokens.mint} />
      <Ellipse cx={244} cy={y} rx={36} ry={10} fill={tokens.mintSoft} stroke={tokens.mint} strokeWidth={3} />
    </AnimatedG>
  );
}

function TrailSymbol({ y, size, delay, opacity }: typeof TRAIL_SYMBOLS[number]) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const t = useSharedValue(0);

  useEffect(() => {
    t.value = 0;
    t.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration: 2200, easing: Easing.out(Easing.cubic) }),
        -1,
        false,
      ),
    );
    return () => cancelAnimation(t);
  }, [t, delay]);

  const animProps = useAnimatedProps(() => ({
    transform: `translate(0 ${-t.value * 60})`,
    opacity: t.value < 0.2 ? t.value * 5 : 0.7 * (1 - t.value),
  }));

  return (
    <AnimatedG animatedProps={animProps}>
      <SvgText
        x={244}
        y={y}
        textAnchor="middle"
        fill={tokens.mint}
        fontSize={size}
        fontWeight="700"
        opacity={opacity}
      >
        ₦
      </SvgText>
    </AnimatedG>
  );
}

export function WalletHero() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const flap = useSharedValue(0);
  const naira = useSharedValue(0);

  useEffect(() => {
    flap.value = withRepeat(
      withTiming(1, { duration: 3600, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    naira.value = withRepeat(
      withTiming(1, { duration: 1800, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => {
      cancelAnimation(flap);
      cancelAnimation(naira);
    };
  }, [flap, naira]);

  // Pulsing ₦: scale around the glyph's center (244, 138).
  const nairaProps = useAnimatedProps(() => ({
    transform: `translate(244 138) scale(${1 + naira.value * 0.18}) translate(-244 -138)`,
  }));

  // Wallet flap: react-native-svg doesn't expose 3D transforms, so we
  // approximate "flap opening" with a Y-translate + opacity to fake a
  // hinge at the top edge.
  const flapProps = useAnimatedProps(() => ({
    transform: `translate(0 ${flap.value * 8})`,
    opacity: 1 - flap.value * 0.4,
  }));

  return (
    <Svg viewBox="0 0 320 320" width="100%" height="100%">
      <Ellipse cx={160} cy={282} rx={120} ry={12} fill={tokens.mint} opacity={0.1} />

      {/* Payment chip (top-left) */}
      <G transform="translate(50, 56)">
        <Rect width={68} height={36} rx={8} fill={tokens.card} stroke={tokens.mint} strokeWidth={3} />
        <Rect x={10} y={11} width={48} height={14} rx={3} fill={tokens.mint} />
        <Line x1={10} y1={18} x2={58} y2={18} stroke={tokens.paper} strokeWidth={2} />
      </G>

      {/* Coin stack on the right */}
      <Ellipse cx={244} cy={220} rx={36} ry={10} fill="#0B5C4B" />
      {STACK_COINS.map((c, i) => (
        <StackCoin key={i} y={c.y} delay={c.delay} />
      ))}

      {/* Pulsing ₦ on top of stack */}
      <AnimatedG animatedProps={nairaProps}>
        <SvgText
          x={244}
          y={138}
          textAnchor="middle"
          fill={tokens.paper}
          fontSize={22}
          fontWeight="700"
        >
          ₦
        </SvgText>
      </AnimatedG>

      {/* Trail ₦ rising */}
      {TRAIL_SYMBOLS.map((sym, i) => (
        <TrailSymbol key={i} y={sym.y} size={sym.size} delay={sym.delay} opacity={sym.opacity} />
      ))}

      {/* NGN note peeking out (behind wallet) */}
      <Rect x={100} y={130} width={100} height={40} rx={4} fill={tokens.mintSoft} stroke={tokens.mint} strokeWidth={3} />
      <SvgText x={118} y={158} fill={tokens.mint} fontSize={20} fontWeight="700">
        ₦
      </SvgText>
      <Line x1={142} y1={146} x2={186} y2={146} stroke={tokens.mint} strokeWidth={2} opacity={0.6} />
      <Line x1={142} y1={156} x2={180} y2={156} stroke={tokens.mint} strokeWidth={2} opacity={0.6} />

      {/* Wallet body */}
      <Rect x={60} y={148} width={160} height={100} rx={14} fill={tokens.mint} />
      <Rect x={60} y={148} width={160} height={20} rx={14} fill="#0B5C4B" />

      {/* Wallet flap */}
      <AnimatedG animatedProps={flapProps}>
        <Path d="M60 148 L220 148 L220 192 L60 192 Z" fill="#0B5C4B" />
        <Rect x={180} y={166} width={36} height={14} rx={4} fill={tokens.paper} />
        <Circle cx={216} cy={173} r={3} fill={tokens.mint} />
      </AnimatedG>
    </Svg>
  );
}
