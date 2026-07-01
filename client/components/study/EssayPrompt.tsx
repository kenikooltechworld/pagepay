import { StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type EssayPromptProps = {
  prompt: string;
  outline: string[];
};

export function EssayPrompt({ prompt, outline }: EssayPromptProps) {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  return (
    <View style={[styles.card, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
      <View style={[styles.labelPill, { backgroundColor: tokens.mintSoft }]}>
        <Ionicons name="document-text-outline" size={14} color={tokens.mint} />
        <Text style={[styles.labelText, { color: tokens.mint }]}>Essay Question</Text>
      </View>
      <Text style={[styles.prompt, { color: tokens.ink }]}>{prompt}</Text>
      <View style={[styles.outlineBox, { backgroundColor: tokens.paper }]}>
        <Text style={[styles.outlineTitle, { color: tokens.inkMuted }]}>Suggested outline:</Text>
        {outline.map((point, idx) => (
          <View key={idx} style={styles.outlineRow}>
            <View style={[styles.bullet, { backgroundColor: tokens.mint }]} />
            <Text style={[styles.outlinePoint, { color: tokens.ink }]}>{point}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 16,
    borderWidth: 1,
    padding: 18,
    gap: 12,
  },
  labelPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
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
  prompt: {
    fontSize: 16,
    fontWeight: '600',
    lineHeight: 22,
  },
  outlineBox: {
    borderRadius: 10,
    padding: 14,
    gap: 8,
  },
  outlineTitle: {
    fontSize: 12,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.8,
    marginBottom: 2,
  },
  outlineRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
  },
  bullet: {
    width: 6,
    height: 6,
    borderRadius: 3,
    marginTop: 6,
  },
  outlinePoint: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
  },
});
