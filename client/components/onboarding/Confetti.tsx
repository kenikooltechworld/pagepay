/**
 * Confetti burst. Renders 18 pieces that fly out from an `origin` with
 * per-piece computed `--dx / --dy / --rot`. Driven by Reanimated 4
 * worklets; unmounts itself after the burst completes so battery
 * doesn't leak on a hidden screen.
 *
 * Ported from `client/design-preview/onboarding.html` (the screen 5
 * CTA tap effect). 18 pieces, 6 brand colors, gravity, 1.1-1.7s per piece.
 */
import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withTiming,
} from 'react-native-reanimated';

const COLORS = [
  '#0E7C66', // mint
  '#34C39B', // mint-soft
  '#E6F1ED', // paper-tint
  '#C2410C', // signal (orange)
  '#FDEFE7', // signal-soft
  '#0B5C4B', // mint-deep
];

const PIECE_COUNT = 18;
const RENDER_MS = 1800; // how long pieces stay mounted before we unmount

type Origin = { x: number; y: number };

type Piece = {
  dx: number;
  dy: number;
  rot: number;
  color: string;
  delay: number;
  duration: number;
  startX: number;
  startY: number;
};

type ConfettiBurstProps = {
  /** When set, the burst plays. When `null`, nothing is rendered. */
  origin: Origin | null;
  /**
   * Called after the last piece's animation finishes (RENDER_MS after
   * mount) so the parent can clear the `origin` state and unmount us.
   */
  onComplete: () => void;
};

export function ConfettiBurst({ origin, onComplete }: ConfettiBurstProps) {
  const [pieces, setPieces] = useState<Piece[] | null>(null);

  // Recompute piece targets on every origin change. `Math.random` here
  // is safe — it only runs when the user taps the CTA, not in render.
  useEffect(() => {
    if (!origin) {
      setPieces(null);
      return;
    }
    const next: Piece[] = Array.from({ length: PIECE_COUNT }, (_, i) => {
      const angle = (Math.PI * 2 * i) / PIECE_COUNT + Math.random() * 0.3;
      const dist = 120 + Math.random() * 100;
      return {
        dx: Math.cos(angle) * dist,
        dy: Math.sin(angle) * dist + 200, // gravity
        rot: Math.random() * 720 - 360,
        color: COLORS[i % COLORS.length],
        delay: Math.random() * 60,
        duration: 1100 + Math.random() * 600,
        startX: origin.x,
        startY: origin.y,
      };
    });
    setPieces(next);

    // Auto-cleanup so the parent doesn't have to time the unmount.
    const t = setTimeout(onComplete, RENDER_MS);
    return () => clearTimeout(t);
  }, [origin, onComplete]);

  if (!pieces) return null;
  return (
    <View pointerEvents="none" style={StyleSheet.absoluteFill}>
      {pieces.map((p, i) => (
        <ConfettiPiece key={i} {...p} />
      ))}
    </View>
  );
}

function ConfettiPiece({
  dx,
  dy,
  rot,
  color,
  delay,
  duration,
  startX,
  startY,
}: Piece) {
  const t = useSharedValue(0);

  useEffect(() => {
    t.value = 0;
    t.value = withDelay(
      delay,
      withTiming(1, {
        duration,
        easing: Easing.bezier(0.2, 0.8, 0.2, 1),
      }),
    );
  }, [t, delay, duration]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: dx * t.value },
      { translateY: dy * t.value },
      { rotate: `${rot * t.value}deg` },
    ],
    opacity: t.value < 0.05 ? t.value * 20 : 1 - (t.value - 0.7) * 3.3,
  }));

  return (
    <Animated.View
      style={[
        styles.piece,
        {
          left: startX - 4,
          top: startY - 6,
          backgroundColor: color,
        },
        animatedStyle,
      ]}
    />
  );
}

const styles = StyleSheet.create({
  piece: {
    position: 'absolute',
    width: 8,
    height: 12,
    borderRadius: 1.5,
  },
});
