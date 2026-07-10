/**
 * HERO 2 — Study with AI.
 *
 * A phone shell with a stacked quiz card (front + 2 back cards), an
 * AI spark orbiting around the phone, and 6 flashcards floating in
 * the background. Ported from `client/design-preview/onboarding.html`
 * HERO 2.
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

const FLASHCARDS: {
  x: number; y: number; w: number; h: number; rot: number; delay: number; lines: number;
}[] = [
  { x: 40,  y: 64,  w: 36, h: 48, rot: -8, delay: 0,   lines: 3 },
  { x: 244, y: 68,  w: 40, h: 52, rot: 6,  delay: 600, lines: 2 },
  { x: 34,  y: 180, w: 40, h: 52, rot: -4, delay: 1200, lines: 2 },
  { x: 248, y: 196, w: 44, h: 56, rot: 7,  delay: 1800, lines: 2 },
  { x: 260, y: 40,  w: 32, h: 42, rot: -3, delay: 2400, lines: 1 },
  { x: 24,  y: 108, w: 32, h: 42, rot: 4,  delay: 3000, lines: 1 },
];

function Flashcard({
  x, y, w, h, rot, delay, lines,
}: typeof FLASHCARDS[number]) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const t = useSharedValue(0);
  const cx = x + w / 2;
  const cy = y + h / 2;

  useEffect(() => {
    t.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration: 4000, easing: Easing.inOut(Easing.cubic) }),
        -1,
        true,
      ),
    );
    return () => cancelAnimation(t);
  }, [t, delay]);

  // SVG transform string: rotate around the card's center, then drift
  // up by `-t * 8` for the float.
  const animatedProps = useAnimatedProps(() => ({
    transform: `translate(${cx} ${cy}) rotate(${rot}) translate(${-cx} ${-cy}) translate(0 ${-t.value * 8})`,
  }));

  return (
    <AnimatedG animatedProps={animatedProps}>
      <Rect
        x={x}
        y={y}
        width={w}
        height={h}
        rx={6}
        fill={lines > 1 ? tokens.mintSoft : tokens.card}
        stroke={tokens.mint}
        strokeWidth={2}
      />
      {Array.from({ length: lines }).map((_, i) => (
        <Line
          key={i}
          x1={x + 8}
          y1={y + 12 + i * 10}
          x2={x + w - (i === lines - 1 ? 6 : 10)}
          y2={y + 12 + i * 10}
          stroke={tokens.mint}
          strokeWidth={2}
          opacity={0.6 - i * 0.15}
        />
      ))}
    </AnimatedG>
  );
}

export function StudyHero() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const aiSpark = useSharedValue(0);
  const card = useSharedValue(0);
  const cardL = useSharedValue(0);
  const cardR = useSharedValue(0);

  useEffect(() => {
    aiSpark.value = withRepeat(
      withTiming(360, { duration: 4500, easing: Easing.linear }),
      -1,
      false,
    );
    card.value = withRepeat(
      withTiming(1, { duration: 6000, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    cardL.value = withRepeat(
      withTiming(1, { duration: 6000, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    cardR.value = withRepeat(
      withTiming(1, { duration: 6000, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => {
      cancelAnimation(aiSpark);
      cancelAnimation(card);
      cancelAnimation(cardL);
      cancelAnimation(cardR);
    };
  }, [aiSpark, card, cardL, cardR]);

  // Quiz card stack: front card bobs + breathes; back cards fan out.
  // SVG transform strings avoid the RN-style `style` prop on `<G>`.
  const cardLProps = useAnimatedProps(() => ({
    transform: `rotate(${-4 - cardL.value * 3} 160 192)`,
  }));
  const cardRProps = useAnimatedProps(() => ({
    transform: `rotate(${4 + cardR.value * 3} 160 192)`,
  }));
  const cardProps = useAnimatedProps(() => {
    const t = card.value;
    const ty = t > 0.5 ? -6 : 0;
    const s = t > 0.4 && t < 0.55 ? 1.04 : t > 0.6 ? 0.98 : 1;
    // First scale around the card center, then bob by `ty` in world space.
    return {
      transform: `translate(160 192) scale(${s}) translate(-160 -192) translate(0 ${ty})`,
    };
  });

  // AI spark orbits the phone by rotating the wrapper around (232, 96).
  const aiSparkProps = useAnimatedProps(() => ({
    transform: `translate(232 96) rotate(${aiSpark.value}) translate(-232 -96)`,
  }));

  return (
    <Svg viewBox="0 0 320 320" width="100%" height="100%">
      <Ellipse cx={160} cy={282} rx={120} ry={12} fill={tokens.mint} opacity={0.1} />
      {FLASHCARDS.map((f, i) => (
        <Flashcard key={i} {...f} />
      ))}

      {/* Phone shell */}
      <Rect x={86} y={86} width={148} height={200} rx={20} fill={tokens.card} stroke={tokens.mint} strokeWidth={3} />
      <Rect x={86} y={86} width={148} height={20} rx={20} fill={tokens.mint} />
      <Circle cx={160} cy={96} r={2.5} fill={tokens.paper} />

      {/* Quiz card stack */}
      <AnimatedG animatedProps={cardLProps}>
        <Rect x={106} y={146} width={108} height={92} rx={10} fill={tokens.mintSoft} stroke={tokens.mint} strokeWidth={2} />
      </AnimatedG>
      <AnimatedG animatedProps={cardRProps}>
        <Rect x={106} y={146} width={108} height={92} rx={10} fill={tokens.mintSoft} stroke={tokens.mint} strokeWidth={2} />
      </AnimatedG>
      <AnimatedG animatedProps={cardProps}>
        <Rect x={100} y={142} width={120} height={100} rx={10} fill={tokens.card} stroke={tokens.mint} strokeWidth={3} />
        <SvgText
          x={160}
          y={186}
          textAnchor="middle"
          fill={tokens.mint}
          fontSize={36}
          fontWeight="700"
        >
          ?
        </SvgText>
        <Rect x={112} y={206} width={96} height={12} rx={6} fill={tokens.mintSoft} />
        <Rect x={112} y={222} width={78} height={12} rx={6} fill={tokens.mintSoft} />
      </AnimatedG>

      {/* AI spark (orbiting) */}
      <AnimatedG animatedProps={aiSparkProps}>
        <G transform="translate(232, 96)">
          <Path
            d="M0 -22 L6 -6 L22 0 L6 6 L0 22 L-6 6 L-22 0 L-6 -6 Z"
            fill={tokens.mint}
          />
          <Circle cx={0} cy={0} r={4} fill={tokens.paper} />
        </G>
      </AnimatedG>
    </Svg>
  );
}
