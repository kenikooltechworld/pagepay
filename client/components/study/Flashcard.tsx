import { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import Animated, {
  Flipped,
  FlipInEasyUp,
  FlipOutEasyDown,
} from 'react-native-reanimated';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type FlashcardProps = {
  front: string;
  back: string;
};

export function Flashcard({ front, back }: FlashcardProps) {
  const [flipped, setFlipped] = useState(false);
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  return (
    <TouchableOpacity
      onPress={() => setFlipped((v) => !v)}
      activeOpacity={0.85}
      accessibilityRole="button"
      accessibilityLabel={flipped ? 'Show front' : 'Show back'}
    >
      <View style={[styles.card, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
        <View style={[styles.labelPill, { backgroundColor: tokens.mintSoft }]}>
          <Text style={[styles.labelText, { color: tokens.mint }]}>
            {flipped ? 'Answer' : 'Question'}
          </Text>
        </View>
        {flipped ? (
          <Flipped
            key="back"
            flipKey={`flash-${front.length}-${back.length}-back`}
            enterAnimation={FlipInEasyUp}
            exitAnimation={FlipOutEasyDown}
          >
            <Animated.View style={styles.content}>
              <Text style={[styles.text, { color: tokens.ink }]}>{back}</Text>
            </Animated.View>
          </Flipped>
        ) : (
          <Flipped
            key="front"
            flipKey={`flash-${front.length}-${back.length}-front`}
            enterAnimation={FlipInEasyUp}
            exitAnimation={FlipOutEasyDown}
          >
            <Animated.View style={styles.content}>
              <Text style={[styles.text, { color: tokens.ink }]}>{front}</Text>
            </Animated.View>
          </Flipped>
        )}
        <Text style={[styles.hint, { color: tokens.inkMuted }]}>Tap to flip</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 20,
    minHeight: 160,
    justifyContent: 'center',
    gap: 12,
  },
  labelPill: {
    alignSelf: 'flex-start',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  labelText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  content: {
    gap: 8,
  },
  text: {
    fontSize: 16,
    lineHeight: 22,
    fontFamily: 'normal',
  },
  hint: {
    fontSize: 11,
    textAlign: 'center',
    marginTop: 4,
  },
});
