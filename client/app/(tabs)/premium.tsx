import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View, ActivityIndicator, Alert } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { SafeAreaView } from 'react-native-safe-area-context';
import * as Linking from 'expo-linking';

import { apiFetch } from '@/src/shared/api/client';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PrimaryButton } from '@/components/PrimaryButton';

type Tier = {
  tier: string;
  display_name: string;
  price_kobo: number;
  duration_days: number;
  benefits: string[];
};

type UserTierInfo = {
  current_tier: string;
  subscription_expires_at: string | null;
  is_premium: boolean;
  days_remaining: number | null;
};

export default function PremiumScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const [selectedTier, setSelectedTier] = useState<string>('premium_monthly');

  const tiersQ = useQuery({
    queryKey: ['payments', 'tiers'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/payments/tiers');
      if (!res.ok) throw new Error('Failed to load tiers');
      return res.json() as Promise<Tier[]>;
    },
  });

  const tierInfoQ = useQuery({
    queryKey: ['payments', 'tier-info'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/payments/tier-info');
      if (!res.ok) throw new Error('Failed to load tier info');
      return res.json() as Promise<UserTierInfo>;
    },
  });

  const handleSelectTier = (tierId: string) => {
    setSelectedTier(tierId);
  };

  const handleUpgrade = async (tier: string) => {
    try {
      const res = await apiFetch('/api/v1/payments/initiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tier, provider: 'paystack' }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Initiation failed');
      }
      const data = await res.json();
      // Open Paystack checkout in browser
      if (data.payment_url) {
        await Linking.openURL(data.payment_url);
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : 'Something went wrong';
      Alert.alert('Payment Error', message);
    }
  };

  const tiers = tiersQ.data ?? [];
  const userTier = tierInfoQ.data;
  const isPremium = userTier?.is_premium ?? false;

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: tokens.paper }}>
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.header}>
          <Text style={[styles.headline, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
            Go Premium
          </Text>
          <Text style={[styles.subline, { color: tokens.inkMuted }]}>
            Unlock unlimited study materials and AI tutoring
          </Text>
        </View>

        {isPremium && userTier ? (
          <View style={[styles.currentTierBadge, { backgroundColor: tokens.mintSoft, borderColor: tokens.mint }]}>
            <Ionicons name="checkmark-circle" size={20} color={tokens.mint} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.badgeTitle, { color: tokens.mint }]}>Active Subscription</Text>
              <Text style={[styles.badgeSubtitle, { color: tokens.inkMuted }]}>
                {userTier.current_tier === 'premium_monthly' ? 'Monthly' : 'Yearly'} •{' '}
                {userTier.days_remaining} days remaining
              </Text>
            </View>
          </View>
        ) : null}

        {tiersQ.isLoading ? (
          <View style={styles.loading}>
            <ActivityIndicator color={tokens.mint} size="large" />
          </View>
        ) : (
          <View style={styles.tiersContainer}>
            {tiers.map((tier) => (
              <TouchableOpacity
                key={tier.tier}
                onPress={() => handleSelectTier(tier.tier)}
                activeOpacity={0.7}
                style={[
                  styles.tierCard,
                  {
                    backgroundColor: selectedTier === tier.tier ? tokens.mintSoft : tokens.card,
                    borderColor: selectedTier === tier.tier ? tokens.mint : tokens.border,
                    borderWidth: selectedTier === tier.tier ? 2 : 1,
                  },
                ]}
              >
                <View style={styles.tierHeader}>
                  <Text style={[styles.tierName, { color: tokens.ink }]}>{tier.display_name}</Text>
                  <Text style={[styles.tierPrice, { color: tokens.mint }]}>
                    ₦{(tier.price_kobo / 100).toLocaleString()}
                  </Text>
                </View>

                <Text style={[styles.tierDuration, { color: tokens.inkMuted }]}>
                  {tier.duration_days} days
                </Text>

                <View style={styles.benefits}>
                  {tier.benefits.map((benefit, idx) => (
                    <View key={idx} style={styles.benefitRow}>
                      <Ionicons name="checkmark" size={16} color={tokens.mint} />
                      <Text style={[styles.benefitText, { color: tokens.ink }]}>{benefit}</Text>
                    </View>
                  ))}
                </View>

                <View style={styles.button}>
                  <PrimaryButton
                    title={isPremium && userTier?.current_tier === tier.tier ? 'Current Plan' : 'Choose'}
                    onPress={() => handleUpgrade(tier.tier)}
                    disabled={isPremium && userTier?.current_tier === tier.tier}
                  />
                </View>
              </TouchableOpacity>
            ))}
          </View>
        )}

        <View style={[styles.faqSection, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          <Text style={[styles.faqTitle, { color: tokens.ink }]}>Can I change my plan?</Text>
          <Text style={[styles.faqText, { color: tokens.inkMuted }]}>
            Yes. Upgrade or downgrade anytime. Your subscription will automatically renew.
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: 16,
    paddingBottom: 48,
    gap: 24,
  },
  header: {
    paddingTop: 12,
    paddingBottom: 8,
    gap: 4,
  },
  headline: {
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.5,
  },
  subline: {
    fontSize: 14,
    lineHeight: 20,
  },
  currentTierBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 14,
    borderWidth: 1,
    padding: 14,
  },
  badgeTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  badgeSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  loading: {
    paddingVertical: 48,
    alignItems: 'center',
  },
  tiersContainer: {
    gap: 14,
  },
  tierCard: {
    borderRadius: 16,
    padding: 18,
    gap: 12,
  },
  tierHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  tierName: {
    fontSize: 18,
    fontWeight: '600',
  },
  tierPrice: {
    fontSize: 20,
    fontWeight: '700',
  },
  tierDuration: {
    fontSize: 13,
  },
  benefits: {
    gap: 8,
  },
  benefitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  benefitText: {
    fontSize: 13,
    lineHeight: 18,
  },
  button: {
    marginTop: 8,
  },
  faqSection: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
    gap: 8,
  },
  faqTitle: {
    fontSize: 14,
    fontWeight: '600',
  },
  faqText: {
    fontSize: 13,
    lineHeight: 18,
  },
});
