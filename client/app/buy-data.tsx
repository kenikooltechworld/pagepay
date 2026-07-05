import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity, ScrollView,
  Alert, ActivityIndicator, StyleSheet,
} from 'react-native';
import { router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { apiFetch } from '@/src/shared/api/client';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PagePay } from '@/constants/theme';

type DataNetwork = {
  identifier: string;
  name: string;
};

type DataPlan = {
  plan_code: string;
  amount: number;
  label: string;
};

type ValidityPeriod = 'daily' | 'weekly' | 'monthly';

// Helper to categorize plans by validity period from label
function categorizePlan(label: string): ValidityPeriod {
  const lower = label.toLowerCase();
  if (lower.includes('day') && !lower.includes('days')) return 'daily';
  if (lower.includes('1day') || lower.includes('2day')) return 'daily';
  if (lower.includes('week')) return 'weekly';
  if (lower.includes('month') || lower.includes('year')) return 'monthly';
  return 'monthly'; // default
}

type PurchaseResult = {
  reference: string;
  commission_naira: number;
  points_earned: number;
  new_balance: number;
  status: string;
  phone: string;
  customer_name: string | null;
};

export default function BuyDataScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();

  const [phone, setPhone] = useState('');
  const [network, setNetwork] = useState('mtn_data_share');
  const [selectedPlan, setSelectedPlan] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ValidityPeriod>('monthly');

  const networksQ = useQuery({
    queryKey: ['data-networks'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/bills/data/networks');
      if (!res.ok) throw new Error('Failed to load networks');
      return (await res.json()) as DataNetwork[];
    },
  });

  const plansQ = useQuery({
    queryKey: ['data-plans', network],
    queryFn: async () => {
      const res = await apiFetch(`/api/v1/bills/data/plans?network=${encodeURIComponent(network)}`);
      if (!res.ok) throw new Error('Failed to load plans');
      return (await res.json()) as DataPlan[];
    },
    enabled: !!network,
  });

  const selectedPkg = plansQ.data?.find((p) => p.plan_code === selectedPlan);

  // Categorize plans by validity
  const categorizedPlans = (plansQ.data ?? []).reduce((acc, plan) => {
    const period = categorizePlan(plan.label);
    if (!acc[period]) acc[period] = [];
    acc[period].push(plan);
    return acc;
  }, {} as Record<ValidityPeriod, DataPlan[]>);

  const purchaseMutation = useMutation({
    mutationFn: async () => {
      if (!selectedPlan || !selectedPkg) throw new Error('Select a plan');
      const res = await apiFetch('/api/v1/bills/data', {
        method: 'POST',
        body: JSON.stringify({
          phone,
          network,
          plan_code: selectedPlan,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Purchase failed');
      }
      return (await res.json()) as PurchaseResult;
    },
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: ['me'] });
      Alert.alert(
        'Data Sent!',
        `${selectedPkg?.label} sent to ${phone}. You earned +${data.points_earned} points!`,
        [{ text: 'Done', onPress: () => router.back() }],
      );
    },
    onError: (error: Error) => {
      Alert.alert('Purchase Failed', error.message);
    },
  });

  const canSubmit = phone.length >= 10 && selectedPlan !== null;
  
  // Points will come from backend response after purchase
  // For display, show "Earn cashback" without hardcoded calculation

  return (
    <View style={{ flex: 1, backgroundColor: tokens.paper, paddingTop: insets.top }}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        {/* Header */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color={tokens.ink} />
          </TouchableOpacity>
          <Text style={[styles.title, { color: tokens.ink }]}>Buy Data</Text>
        </View>

        {/* Phone */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Phone Number</Text>
        <TextInput
          style={[styles.input, { backgroundColor: tokens.card, color: tokens.ink, borderColor: tokens.border }]}
          placeholder="0803 123 4567"
          placeholderTextColor={tokens.inkMuted}
          value={phone}
          onChangeText={setPhone}
          keyboardType="phone-pad"
          maxLength={15}
        />

        {/* Network */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Data Network</Text>
        {networksQ.isLoading ? (
          <ActivityIndicator color={tokens.mint} />
        ) : (
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            {(networksQ.data ?? []).map((n) => (
              <TouchableOpacity
                key={n.identifier}
                onPress={() => { setNetwork(n.identifier); setSelectedPlan(null); }}
                style={[
                  styles.chip,
                  {
                    backgroundColor: network === n.identifier ? tokens.mint : tokens.card,
                    borderColor: network === n.identifier ? tokens.mint : tokens.border,
                  },
                ]}
              >
                <Text style={[
                  styles.chipText,
                  { color: network === n.identifier ? tokens.mintText : tokens.ink },
                ]}>{n.name}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Plans with tabs */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Select Bundle</Text>
        
        {/* Validity Tabs */}
        <View style={{ flexDirection: 'row', gap: 8, marginBottom: 8 }}>
          {(['daily', 'weekly', 'monthly'] as ValidityPeriod[]).map((period) => {
            const count = categorizedPlans[period]?.length || 0;
            if (count === 0) return null;
            return (
              <TouchableOpacity
                key={period}
                onPress={() => setActiveTab(period)}
                style={[
                  styles.tab,
                  {
                    backgroundColor: activeTab === period ? tokens.mint : tokens.card,
                    borderColor: activeTab === period ? tokens.mint : tokens.border,
                  },
                ]}
              >
                <Text style={[
                  styles.tabText,
                  { color: activeTab === period ? tokens.mintText : tokens.ink },
                ]}>
                  {period.charAt(0).toUpperCase() + period.slice(1)} ({count})
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>
        
        {plansQ.isLoading ? (
          <ActivityIndicator color={tokens.mint} />
        ) : (
          <View style={{ gap: 8 }}>
            {(categorizedPlans[activeTab] ?? []).map((p) => {
              return (
                <TouchableOpacity
                  key={p.plan_code}
                  onPress={() => setSelectedPlan(p.plan_code)}
                  style={[
                    styles.bundleCard,
                    {
                      backgroundColor: selectedPlan === p.plan_code ? tokens.mintSoft : tokens.card,
                      borderColor: selectedPlan === p.plan_code ? tokens.mint : tokens.border,
                    },
                  ]}
                >
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.bundleName, { color: tokens.ink }]}>
                      {p.label}
                    </Text>
                    <Text style={[styles.bundlePoints, { color: tokens.mint }]}>
                      💰 Earn cashback points
                    </Text>
                  </View>
                  <Text style={[styles.bundlePrice, { color: tokens.mint }]}>
                    ₦{p.amount.toLocaleString()}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Earn notice */}
        {selectedPkg && (
          <View style={[styles.earnCard, { backgroundColor: tokens.mintSoft, borderColor: tokens.mint }]}>
            <Ionicons name="gift-outline" size={20} color={tokens.mint} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.earnLabel, { color: tokens.mint }]}>You'll earn cashback points!</Text>
              <Text style={[styles.earnSub, { color: tokens.ink }]}>
                Real commission from Peyflex will be credited after purchase (varies by network).
              </Text>
            </View>
          </View>
        )}

        {/* Pay button */}
        <TouchableOpacity
          onPress={() => purchaseMutation.mutate()}
          disabled={!canSubmit || purchaseMutation.isPending}
          style={[
            styles.payBtn,
            {
              backgroundColor: canSubmit ? tokens.mint : tokens.border,
              opacity: purchaseMutation.isPending ? 0.7 : 1,
            },
          ]}
        >
          {purchaseMutation.isPending ? (
            <ActivityIndicator color={tokens.mintText} />
          ) : (
            <>
              <Ionicons name="cart-outline" size={20} color={tokens.mintText} />
              <Text style={[styles.payText, { color: tokens.mintText }]}>
                {selectedPkg ? `Pay ₦${selectedPkg.amount.toLocaleString()}` : 'Select a bundle'}
              </Text>
            </>
          )}
        </TouchableOpacity>
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  title: { fontSize: 22, fontWeight: '700', fontFamily: 'SpaceGrotesk_700Bold' },
  label: { fontSize: 13, fontWeight: '500' },
  input: {
    borderRadius: 12, padding: 14, fontSize: 18, fontWeight: '600',
    borderWidth: 1,
  },
  chip: {
    paddingHorizontal: 16, paddingVertical: 10, borderRadius: 20,
    borderWidth: 1,
  },
  chipText: { fontSize: 13, fontWeight: '600' },
  tab: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
    borderWidth: 1, flex: 1, alignItems: 'center',
  },
  tabText: { fontSize: 12, fontWeight: '600' },
  bundleCard: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 12, padding: 14, borderWidth: 1,
  },
  bundleName: { fontSize: 13, fontWeight: '500' },
  bundlePoints: { fontSize: 11, fontWeight: '600', marginTop: 3 },
  bundlePrice: { fontSize: 15, fontWeight: '700', fontFamily: 'SpaceGrotesk_700Bold' },
  earnCard: {
    flexDirection: 'row', alignItems: 'center', gap: 12,
    borderRadius: 12, padding: 14, borderWidth: 1, marginTop: 4,
  },
  earnLabel: { fontSize: 14, fontWeight: '700', fontFamily: 'SpaceGrotesk_700Bold' },
  earnSub: { fontSize: 12, marginTop: 2 },
  payBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 8, borderRadius: 14, padding: 16, marginTop: 8,
  },
  payText: { fontSize: 16, fontWeight: '700', fontFamily: 'SpaceGrotesk_700Bold' },
});
