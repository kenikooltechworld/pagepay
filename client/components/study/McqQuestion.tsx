import { useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type McqQuestionProps = {
  question: string;
  options: string[];
  correct_index: number;
  explanation: string;
  onAnswered: (correct: boolean) => void;
};

export function McqQuestion({
  question,
  options,
  correct_index,
  explanation,
  onAnswered,
}: McqQuestionProps) {
  const [selected, setSelected] = useState<number | null>(null);
  const [showAnswer, setShowAnswer] = useState(false);
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const handleSelect = (idx: number) => {
    if (showAnswer) return;
    setSelected(idx);
    setShowAnswer(true);
    onAnswered(idx === correct_index);
  };

  const isCorrect = selected === correct_index;
  const optionColors = options.map((_, idx) => {
    if (!showAnswer) return tokens.border;
    if (idx === correct_index) return tokens.mint;
    if (idx === selected && idx !== correct_index) return tokens.signal;
    return tokens.border;
  });

  return (
    <View style={[styles.card, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
      <Text style={[styles.question, { color: tokens.ink }]}>{question}</Text>
      <View style={styles.options}>
        {options.map((opt, idx) => (
          <TouchableOpacity
            key={idx}
            onPress={() => handleSelect(idx)}
            disabled={showAnswer}
            activeOpacity={0.7}
            style={[
              styles.option,
              { borderColor: optionColors[idx], backgroundColor: tokens.paper },
            ]}
          >
            <View style={[styles.badge, { backgroundColor: optionColors[idx] }]}>
              <Text style={styles.badgeText}>{String.fromCharCode(65 + idx)}</Text>
            </View>
            <Text style={[styles.optionText, { color: tokens.ink }]}>{opt}</Text>
            {showAnswer && idx === correct_index && (
              <Ionicons name="checkmark-circle" size={18} color={tokens.mint} />
            )}
            {showAnswer && idx === selected && idx !== correct_index && (
              <Ionicons name="close-circle" size={18} color={tokens.signal} />
            )}
          </TouchableOpacity>
        ))}
      </View>
      {showAnswer && (
        <View style={[styles.explanation, { backgroundColor: tokens.paper }]}>
          <Text style={[styles.explanationLabel, { color: isCorrect ? tokens.mint : tokens.signal }]}>
            {isCorrect ? 'Correct!' : 'Incorrect'}
          </Text>
          <Text style={[styles.explanationText, { color: tokens.inkMuted }]}>{explanation}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 18,
    gap: 14,
  },
  question: {
    fontSize: 16,
    fontWeight: '600',
    lineHeight: 22,
  },
  options: {
    gap: 10,
  },
  option: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 12,
    borderWidth: 1.5,
    padding: 14,
  },
  badge: {
    width: 28,
    height: 28,
    borderRadius: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    color: '#fff',
    fontSize: 12,
    fontWeight: '700',
  },
  optionText: {
    flex: 1,
    fontSize: 14,
    lineHeight: 18,
  },
  explanation: {
    borderRadius: 10,
    padding: 12,
    gap: 4,
  },
  explanationLabel: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
  },
  explanationText: {
    fontSize: 13,
    lineHeight: 18,
  },
});
