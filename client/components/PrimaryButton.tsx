import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';
import * as Haptics from 'expo-haptics';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type PrimaryButtonProps = {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
};

/**
 * The PagePay primary CTA: solid mint, full width, press-scale, haptic,
 * spinner-while-loading. Used for the auth submit and any primary screen action.
 */
export function PrimaryButton({
  title,
  onPress,
  loading = false,
  disabled = false,
}: PrimaryButtonProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const isInert = loading || disabled;
  const bg = isInert
    ? scheme === 'light'
      ? '#C9D6D2' // soft mint-tinted grey when disabled in light mode
      : '#2A3A35'
    : tokens.mint;
  const fg = isInert
    ? scheme === 'light'
      ? '#FFFFFF'
      : tokens.inkMuted
    : tokens.mintText;

  return (
    <Pressable
      onPress={() => {
        if (!isInert) {
          Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light).catch(() => {});
          onPress();
        }
      }}
      disabled={isInert}
      accessibilityRole="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: isInert, busy: loading }}
      style={({ pressed }) => [
        styles.btn,
        {
          backgroundColor: bg,
          transform: [{ scale: pressed && !isInert ? 0.97 : 1 }],
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={fg} />
      ) : (
        <Text style={[styles.label, { color: fg }]}>{title}</Text>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    minHeight: 52,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    letterSpacing: 0.1,
  },
});