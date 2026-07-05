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

type Bouquet = {
  id: string;
  provider: string;
  name: string;
  price_naira: number;
  channels: string | null;
  commission_rate: number;
};

type PurchaseResult = {
  reference: string;
  commission_naira: number;
  points_earned: number;
  new_balance: number;
  status: string;
  customer_name: string | null;
};

const PROVIDERS = [
  { key: 'dstv', label: 'DStv' },
  { key: 'gotv', label: 'GOtv' },
  { key: 'startimes', label: 'Startimes' },
];

export default function BuyTvScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();

  const [smartcard, setSmartcard] = useState('');
  const [provider, setProvider] = useState('dstv');
  const [selectedBouquet, setSelectedBouquet] = useState<string | null>(null);

  const bouquetsQ = useQuery({
    queryKey: ['tv-bouquets', provider],
    queryFn: async () => {
      const res = await apiFetch(`/api/v1/bills/tv-bouquets?provider=${provider}`);
      if (!res.ok) throw new Error('Failed to load bouquets');
      return (await res.json()) as Bouquet[];
    },
  });

  const selectedPkg = bouquetsQ.data?.find((b) => b.id === selectedBouquet);

  const purchaseMutation = useMutation({
    mutationFn: async () => {
      if (!selectedPkg) throw new Error('Select a bouquet');
      const res = await apiFetch('/api/v1/bills/tv', {
        method: 'POST',
        body: JSON.stringify({
          smartcard_number: smartcard,
          provider,
          variation_id: selectedBouquet,
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
        'Subscription Activated!',
        `${selectedPkg?.name} activated on ${smartcard}. You earned +${data.points_earned} points!`,
        [{ text: 'Done', onPress: () => router.back() }],
      );
    },
    onError: (error: Error) => {
      Alert.alert('Purchase Failed', error.message);
    },
  });

  const canSubmit = smartcard.length >= 8 && selectedBouquet !== null;
  const estPoints = selectedPkg
    ? Math.floor(selectedPkg.price_naira * 0.018 * 0.67 * 100)
    : 0;

  return (
    <View style={{ flex: 1, backgroundColor: tokens.paper, paddingTop: insets.top }}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        {/* Header */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color={tokens.ink} />
          </TouchableOpacity>
          <Text style={[styles.title, { color: tokens.ink }]}>Buy TV Subscription</Text>
        </View>

        {/* Provider */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Provider</Text>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          {PROVIDERS.map((p) => (
            <TouchableOpacity
              key={p.key}
              onPress={() => { setProvider(p.key); setSelectedBouquet(null); }}
              style={[
                styles.providerCard,
                {
                  backgroundColor: provider === p.key ? tokens.mintSoft : tokens.card,
                  borderColor: provider === p.key ? tokens.mint : tokens.border,
                },
              ]}
            >
              <Ionicons name="tv-outline" size={24} color={tokens.mint} />
              <Text style={[
                styles.chipText,
                { color: provider === p.key ? tokens.mint : tokens.ink },
              ]}>{p.label}</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Bouquets */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Select Bouquet</Text>
        {bouquetsQ.isLoading ? (
          <ActivityIndicator color={tokens.mint} />
        ) : (
          <View style={{ gap: 8 }}>
            {(bouquetsQ.data ?? []).map((b) => (
              <TouchableOpacity
                key={b.id}
                onPress={() => setSelectedBouquet(b.id)}
                style={[
                  styles.bundleCard,
                  {
                    backgroundColor: selectedBouquet === b.id ? tokens.mintSoft : tokens.card,
                    borderColor: selectedBouquet === b.id ? tokens.mint : tokens.border,
                  },
                ]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[styles.bundleName, { color: tokens.ink }]}>{b.name}</Text>
                  {b.channels && (
                    <Text style={[styles.bundleMeta, { color: tokens.inkMuted }]}>{b.channels}</Text>
                  )}
                </View>
                <Text style={[styles.bundlePrice, { color: tokens.mint }]}>₦{b.price_naira.toLocaleString()}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Smartcard */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Smartcard / IUC Number</Text>
        <TextInput
          style={[styles.input, { backgroundColor: tokens.card, color: tokens.ink, borderColor: tokens.border }]}
          placeholder="1234 5678 9012"
          placeholderTextColor={tokens.inkMuted}
          value={smartcard}
          onChangeText={setSmartcard}
          keyboardType="number-pad"
          maxLength={15}
        />

        {/* Earn notice */}
        {selectedPkg && (
          <View style={[styles.earnCard, { backgroundColor: tokens.mintSoft, borderColor: tokens.mint }]}>
            <Ionicons name="gift-outline" size={20} color={tokens.mint} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.earnLabel, { color: tokens.mint }]}>You'll earn +{estPoints} points</Text>
              <Text style={[styles.earnSub, { color: tokens.ink }]}>
                Commission from the TV subscription is split — you get points, we keep the platform running.
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
                {selectedPkg ? `Pay ₦${selectedPkg.price_naira.toLocaleString()}` : 'Select a bouquet'}
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
  chipText: { fontSize: 14, fontWeight: '600' },
  providerCard: {
    flex: 1, padding: 14, borderRadius: 12, borderWidth: 1,
    alignItems: 'center', gap: 6,
  },
  bundleCard: {
    flexDirection: 'row', alignItems: 'center',
    borderRadius: 12, padding: 14, borderWidth: 1,
  },
  bundleName: { fontSize: 14, fontWeight: '600' },
  bundleMeta: { fontSize: 11, marginTop: 1 },
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
