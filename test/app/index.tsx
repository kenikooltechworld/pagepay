import { View, Text, StyleSheet } from 'react-native';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

export default function Index() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  return (
    <View style={[styles.container, { backgroundColor: tokens.paper }]}>
      <Text style={[styles.title, { color: tokens.mint }]}>
        PagePay Test
      </Text>
      <Text style={[styles.subtitle, { color: tokens.inkMuted }]}>
        Splash animation test completed successfully! 🎉
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 20,
  },
  title: {
    fontSize: 32,
    fontWeight: '700',
    fontFamily: 'SpaceGrotesk_700Bold',
    marginBottom: 12,
  },
  subtitle: {
    fontSize: 16,
    textAlign: 'center',
  },
});
