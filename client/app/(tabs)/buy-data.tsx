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

type Bundle = {
  id: string;
  network: string;
  name: string;
  size_mb: number;
  validity_days: number;
  price_naira: number;
  commission_rate: number;
};

type PurchaseResult = {
  reference: string;
  commission_naira: number;
  points_earned: number;
  new_balance: number;
  status: string;
  phone: string;
};

const NETWORKS = [
  { key: 'mtn', label: 'MTN' },
  { key: 'airtel', label: 'Airtel' },
  { key: 'glo', label: 'GLO' },
  { key: '9mobile', label: '9mobile' },
];

export default function BuyDataScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();

  const [phone, setPhone] = useState('');
  const [network, setNetwork] = useState('mtn');
  const [selectedBundle, setSelectedBundle] = useState<string | null>(null);

  const bundlesQ = useQuery({
    queryKey: ['data-bundles', network],
    queryFn: async () => {
      const res = await apiFetch(`/api/v1/bills/bundles?network=${network}`);
      if (!res.ok) throw new Error('Failed to load bundles');
      return (await res.json()) as Bundle[];
    },
  });

  const selectedPkg = bundlesQ.data?.find((b) => b.id === selectedBundle);

  const purchaseMutation = useMutation({
    mutationFn: async () => {
      if (!selectedBundle || !selectedPkg) throw new Error('Select a bundle');
      const res = await apiFetch('/api/v1/bills/data', {
        method: 'POST',
        body: JSON.stringify({
          phone,
          network,
          data_id: selectedBundle,
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
        `${selectedPkg?.name} sent to ${phone}. You earned +${data.points_earned} points!`,
        [{ text: 'Done', onPress: () => router.back() }],
      );
    },
    onError: (error: Error) => {
      Alert.alert('Purchase Failed', error.message);
    },
  });

  const canSubmit = phone.length >= 10 && selectedBundle !== null;

  const estPoints = selectedPkg
    ? Math.floor(selectedPkg.price_naira * selectedPkg.commission_rate * 0.67 * 100)
    : 0;

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
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Network</Text>
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          {NETWORKS.map((n) => (
            <TouchableOpacity
              key={n.key}
              onPress={() => { setNetwork(n.key); setSelectedBundle(null); }}
              style={[
                styles.chip,
                {
                  backgroundColor: network === n.key ? tokens.mint : tokens.card,
                  borderColor: network === n.key ? tokens.mint : tokens.border,
                },
              ]}
            >
              <Text style={[
                styles.chipText,
                { color: network === n.key ? tokens.mintText : tokens.ink },
              ]}>{n.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Bundles */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Select Bundle</Text>
        {bundlesQ.isLoading ? (
          <ActivityIndicator color={tokens.mint} />
        ) : (
          <View style={{ gap: 8 }}>
            {(bundlesQ.data ?? []).map((b) => (
              <TouchableOpacity
                key={b.id}
                onPress={() => setSelectedBundle(b.id)}
                style={[
                  styles.bundleCard,
                  {
                    backgroundColor: selectedBundle === b.id ? tokens.mintSoft : tokens.card,
                    borderColor: selectedBundle === b.id ? tokens.mint : tokens.border,
                  },
                ]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[styles.bundleName, { color: tokens.ink }]}>{b.name}</Text>
                  <Text style={[styles.bundleMeta, { color: tokens.inkMuted }]}>
                    {b.size_mb >= 1024 ? `${(b.size_mb / 1024).toFixed(0)}GB` : `${b.size_mb}MB`} • {b.validity_days} days
                  </Text>
                </View>
                <Text style={[styles.bundlePrice, { color: tokens.mint }]}>₦{b.price_naira.toLocaleString()}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Earn notice */}
        {selectedPkg && (
          <View style={[styles.earnCard, { backgroundColor: tokens.mintSoft, borderColor: tokens.mint }]}>
            <Ionicons name="gift-outline" size={20} color={tokens.mint} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.earnLabel, { color: tokens.mint }]}>You'll earn +{estPoints} points</Text>
              <Text style={[styles.earnSub, { color: tokens.ink }]}>
                Commission from the data purchase is split — you get points, we keep the platform running.
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
                {selectedPkg ? `Pay ₦${selectedPkg.price_naira.toLocaleString()}` : 'Select a bundle'}
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
  chipText: { fontSize: 14, fontWeight: '600' },
  bundleCard: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 12, padding: 14, borderWidth: 1,
  },
  bundleName: { fontSize: 14, fontWeight: '600' },
  bundleMeta: { fontSize: 11, marginTop: 2 },
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
