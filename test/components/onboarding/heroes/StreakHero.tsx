/**
 * HERO 4 — Reading streak.
 *
 * A 7-day cell row (M T W T F S S, Saturday = today, Sunday = locked
 * dashed outline), a 4-layer flame (body/mid/inner/core) in the center
 * with each layer flickering at its own rate, 5 embers rising at
 * staggered positions, a "7 day streak" badge that pops, and a
 * "KEEP THE STREAK ALIVE" label. Ported from HERO 4 in
 * `client/design-preview/onboarding.html`.
 */
import { useEffect } from 'react';
import Svg, {
  Circle,
  Ellipse,
  G,
  Path,
  Rect,
  Text as SvgText,
} from 'react-native-svg';
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

const DAYS = [
  { x: 40,  letter: 'M', today: false, locked: false },
  { x: 74,  letter: 'T', today: false, locked: false },
  { x: 108, letter: 'W', today: false, locked: false },
  { x: 142, letter: 'T', today: false, locked: false },
  { x: 176, letter: 'F', today: false, locked: false },
  { x: 210, letter: 'S', today: true,  locked: false },
  { x: 244, letter: 'S', today: false, locked: true  },
];

const EMBERS: { cx: number; cy: number; r: number; color: string; delay: number }[] = [
  { cx: 120, cy: 80, r: 3,   color: '#C2410C', delay: 0 },
  { cx: 200, cy: 60, r: 2.5, color: '#FB923C', delay: 600 },
  { cx: 100, cy: 100, r: 2,  color: '#FBBF24', delay: 1200 },
  { cx: 220, cy: 90, r: 2.5, color: '#C2410C', delay: 1800 },
  { cx: 180, cy: 40, r: 2,   color: '#FB923C', delay: 2400 },
];

function DayCell({ x, letter, today, locked }: typeof DAYS[number]) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const t = useSharedValue(0);
  const cx = x + 14;
  const cy = 238;

  useEffect(() => {
    if (!today) return;
    t.value = withRepeat(
      withTiming(1, { duration: 1600, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => cancelAnimation(t);
  }, [t, today]);

  const animProps = useAnimatedProps(() => ({
    transform: `translate(${cx} ${cy}) scale(${1 + t.value * 0.12}) translate(${-cx} ${-cy})`,
  }));

  return (
    <G>
      {locked ? (
        <Rect
          x={x}
          y={220}
          width={28}
          height={36}
          rx={6}
          fill={tokens.mintSoft}
          stroke={tokens.mint}
          strokeWidth={2}
          strokeDasharray="2 3"
        />
      ) : (
        <AnimatedG animatedProps={today ? animProps : undefined}>
          <Rect
            x={x}
            y={220}
            width={28}
            height={36}
            rx={6}
            fill={tokens.mint}
          />
        </AnimatedG>
      )}
      {today ? (
        <Rect
          x={x - 3}
          y={217}
          width={34}
          height={42}
          rx={8}
          fill="none"
          stroke={tokens.mint}
          strokeWidth={2}
          opacity={0.4}
        />
      ) : null}
      <SvgText
        x={x + 14}
        y={244}
        textAnchor="middle"
        fill={locked ? tokens.mint : tokens.paper}
        fontSize={11}
        fontWeight="700"
        opacity={locked ? 0.5 : 1}
      >
        {letter}
      </SvgText>
    </G>
  );
}

function Ember({ cx, cy, r, color, delay }: typeof EMBERS[number]) {
  const t = useSharedValue(0);

  useEffect(() => {
    t.value = 0;
    t.value = withDelay(
      delay,
      withRepeat(
        withTiming(1, { duration: 3200, easing: Easing.out(Easing.cubic) }),
        -1,
        false,
      ),
    );
    return () => cancelAnimation(t);
  }, [t, delay]);

  // The ember is a small circle — we want it to rise (`translateY`)
  // and grow (`scale`), around its own center. The wrapper applies
  // the transforms in SVG-transform order (right-to-left).
  const animProps = useAnimatedProps(() => ({
    transform: `translate(${cx} ${cy}) scale(${0.6 + t.value * 0.4}) translate(${-cx} ${-cy}) translate(0 ${-t.value * 90})`,
    opacity: t.value < 0.15 ? t.value * 6 : 0.9 * (1 - t.value),
  }));

  return (
    <AnimatedG animatedProps={animProps}>
      <Circle cx={cx} cy={cy} r={r} fill={color} />
    </AnimatedG>
  );
}

export function StreakHero() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const flameBody = useSharedValue(0);
  const flameMid = useSharedValue(0);
  const flameInner = useSharedValue(0);
  const badge = useSharedValue(0);

  useEffect(() => {
    flameBody.value = withRepeat(
      withTiming(1, { duration: 1100, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    flameMid.value = withRepeat(
      withTiming(1, { duration: 900, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    flameInner.value = withRepeat(
      withTiming(1, { duration: 700, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    badge.value = withRepeat(
      withTiming(1, { duration: 2400, easing: Easing.inOut(Easing.cubic) }),
      -1,
      true,
    );
    return () => {
      cancelAnimation(flameBody);
      cancelAnimation(flameMid);
      cancelAnimation(flameInner);
      cancelAnimation(badge);
    };
  }, [flameBody, flameMid, flameInner, badge]);

  // Flame layers are inside a `<G transform="translate(160, 130)">`,
  // so the local origin is (0, 0). Each layer scales around that.
  const flameBodyProps = useAnimatedProps(() => ({
    transform: `scale(${1 + flameBody.value * 0.04} ${1 - flameBody.value * 0.04})`,
  }));
  const flameMidProps = useAnimatedProps(() => ({
    transform: `scale(${1 - flameMid.value * 0.04} ${1 + flameMid.value * 0.06})`,
  }));
  const flameInnerProps = useAnimatedProps(() => ({
    transform: `scale(${1 + flameInner.value * 0.08} ${1 - flameInner.value * 0.08})`,
  }));

  // Badge scales around its own center (160, 194).
  const badgeProps = useAnimatedProps(() => ({
    transform: `translate(160 194) scale(${1 + badge.value * 0.04}) translate(-160 -194)`,
  }));

  return (
    <Svg viewBox="0 0 320 320" width="100%" height="100%">
      <Ellipse cx={160} cy={282} rx={120} ry={12} fill={tokens.mint} opacity={0.1} />

      {/* 7-day streak row */}
      {DAYS.map((d, i) => (
        <DayCell key={i} {...d} />
      ))}

      {/* Streak badge */}
      <AnimatedG animatedProps={badgeProps}>
        <Rect x={100} y={180} width={120} height={28} rx={14} fill={tokens.mintSoft} stroke={tokens.mint} strokeWidth={2} />
        <SvgText
          x={160}
          y={199}
          textAnchor="middle"
          fill={tokens.mint}
          fontSize={13}
          fontWeight="700"
        >
          7 day streak
        </SvgText>
      </AnimatedG>

      {/* Flame (4 layers) */}
      <G transform="translate(160, 130)">
        <AnimatedG animatedProps={flameBodyProps}>
          <Path
            d="M 0 -56 C 22 -32 28 -16 28 -4 C 28 22 14 36 0 36 C -14 36 -28 22 -28 -4 C -28 -16 -22 -32 0 -56 Z"
            fill="#C2410C"
          />
        </AnimatedG>
        <AnimatedG animatedProps={flameMidProps}>
          <Path
            d="M 0 -38 C 14 -22 18 -8 18 2 C 18 18 10 28 0 28 C -10 28 -18 18 -18 2 C -18 -8 -14 -22 0 -38 Z"
            fill="#FB923C"
          />
        </AnimatedG>
        <AnimatedG animatedProps={flameInnerProps}>
          <Path
            d="M 0 -22 C 8 -12 10 -2 10 6 C 10 16 6 22 0 22 C -6 22 -10 16 -10 6 C -10 -2 -8 -12 0 -22 Z"
            fill="#FBBF24"
          />
        </AnimatedG>
        <Ellipse cx={0} cy={14} rx={4} ry={6} fill={tokens.paper} />
      </G>

      {/* Embers */}
      {EMBERS.map((e, i) => (
        <Ember key={i} {...e} />
      ))}

      {/* "Today" label */}
      <SvgText
        x={160}
        y={280}
        textAnchor="middle"
        fill={tokens.inkMuted}
        fontSize={10}
        fontWeight="500"
        letterSpacing={0.8}
      >
        KEEP THE STREAK ALIVE
      </SvgText>
    </Svg>
  );
}
