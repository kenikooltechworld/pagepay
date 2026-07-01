import React from 'react';
import { View, StyleSheet } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  Easing,
} from 'react-native-reanimated';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PagePay } from '@/constants/theme';

type SkeletonProps = {
  width?: number | string;
  height: number;
  borderRadius?: number;
  marginBottom?: number;
};

/**
 * Base animated skeleton component.
 * Renders a shimmer-animated placeholder bone using Reanimated.
 *
 * The component uses the PagePay theme tokens to ensure dark/light mode
 * consistency. The shimmer animates between the border color (light) and
 * a slightly lighter shade to create the pulse effect.
 *
 * @param width - Width of the skeleton (default: '100%')
 * @param height - Height of the skeleton (required)
 * @param borderRadius - Border radius for rounded corners (default: 8)
 * @param marginBottom - Bottom margin for spacing (default: 0)
 */
export function Skeleton({
  width = '100%',
  height,
  borderRadius = 8,
  marginBottom = 0,
}: SkeletonProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  // Shared value for shimmer animation (0 -> 1 -> 0 loop)
  const shimmer = useSharedValue(0);

  // Start animation on mount
  React.useEffect(() => {
    shimmer.value = withRepeat(
      withTiming(1, {
        duration: 1200,
        easing: Easing.inOut(Easing.ease),
      }),
      -1,
      true
    );
  }, [shimmer]);

  // Animated style: interpolate between two background colors
  const animatedStyle = useAnimatedStyle(() => {
    // Light shade (border color) -> slightly lighter -> back
    // Using the theme's border color as the base and a computed lighter version
    const baseColor = tokens.border;
    const lightColor = tokens.mintSoft; // Softer color for the shimmer highlight

    // Interpolate between the two colors based on shimmer value
    return {
      backgroundColor: shimmer.value < 0.5 
        ? baseColor 
        : lightColor,
    };
  });

  return (
    <Animated.View
      style={[
        {
          width,
          height,
          borderRadius,
          marginBottom,
        },
        animatedStyle,
      ]}
    />
  );
}
