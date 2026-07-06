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
  id?: string;
  plan_id?: string;
  plan_code?: string;
  provider?: string;
  name?: string;
  price_naira?: number;
  amount?: number;
  channels?: string | null;
  commission_rate?: number;
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
  const [phone, setPhone] = useState('');
  const [provider, setProvider] = useState('dstv');
  const [selectedBouquet, setSelectedBouquet] = useState<string | null>(null);

  const bouquetsQ = useQuery({
    queryKey: ['tv-plans', provider],
    queryFn: async () => {
      const res = await apiFetch(`/api/v1/bills/tv/plans?provider=${provider}`);
      if (!res.ok) throw new Error('Failed to load plans');
      return (await res.json()) as Bouquet[];
    },
  });

  const selectedPkg = bouquetsQ.data?.find((b) => (b.plan_code || b.id) === selectedBouquet);

  const purchaseMutation = useMutation({
    mutationFn: async () => {
      if (!selectedPkg) throw new Error('Select a bouquet');
      if (!phone) throw new Error('Phone number required');
      const res = await apiFetch('/api/v1/bills/tv', {
        method: 'POST',
        body: JSON.stringify({
          smartcard_number: smartcard,
          provider,
          plan_code: selectedPkg.plan_code || selectedBouquet,
          phone: phone,
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

  const canSubmit = smartcard.length >= 10 && phone.length === 11 && selectedBouquet !== null;
  const estPoints = selectedPkg
    ? Math.floor((selectedPkg.price_naira || selectedPkg.amount || 0) * 0.018 * 0.67 * 100)
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
            {(bouquetsQ.data ?? []).map((b) => {
              // Bouquet objects come from the bill-providers API and
              // their shape isn't fully typed — fall back to '' so the
              // rest of the closure sees `string`, not `string | undefined`.
              const id = b.plan_code ?? b.id ?? '';
              return (
              <TouchableOpacity
                key={id}
                onPress={() => setSelectedBouquet(id)}
                style={[
                  styles.bundleCard,
                  {
                    backgroundColor: selectedBouquet === id ? tokens.mintSoft : tokens.card,
                    borderColor: selectedBouquet === id ? tokens.mint : tokens.border,
                  },
                ]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={[styles.bundleName, { color: tokens.ink }]}>{b.name}</Text>
                  {b.channels && (
                    <Text style={[styles.bundleMeta, { color: tokens.inkMuted }]}>{b.channels}</Text>
                  )}
                </View>
                <Text style={[styles.bundlePrice, { color: tokens.mint }]}>
                  ₦{((b.price_naira || b.amount || 0).toLocaleString())}
                </Text>
              </TouchableOpacity>
              );
            })}
          </View>
        )}

        {/* Smartcard */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Smartcard / IUC Number</Text>
        <TextInput
          style={[styles.input, { backgroundColor: tokens.card, color: tokens.ink, borderColor: tokens.border }]}
          placeholder="1234567890"
          placeholderTextColor={tokens.inkMuted}
          value={smartcard}
          onChangeText={(text) => {
            // Only allow numbers
            const cleaned = text.replace(/[^0-9]/g, '');
            setSmartcard(cleaned);
          }}
          keyboardType="number-pad"
          maxLength={15}
        />
        {smartcard.length > 0 && smartcard.length < 10 && (
          <Text style={{ color: tokens.error, fontSize: 12, marginTop: -10 }}>
            Smartcard number must be at least 10 digits
          </Text>
        )}

        {/* Phone Number */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Phone Number</Text>
        <TextInput
          style={[styles.input, { backgroundColor: tokens.card, color: tokens.ink, borderColor: tokens.border }]}
          placeholder="08012345678"
          placeholderTextColor={tokens.inkMuted}
          value={phone}
          onChangeText={(text) => {
            // Only allow numbers
            const cleaned = text.replace(/[^0-9]/g, '');
            setPhone(cleaned);
          }}
          keyboardType="phone-pad"
          maxLength={11}
        />
        {phone.length > 0 && phone.length < 11 && (
          <Text style={{ color: tokens.error, fontSize: 12, marginTop: -10 }}>
            Phone number must be 11 digits
          </Text>
        )}

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
                {selectedPkg ? `Pay ₦${((selectedPkg.price_naira || selectedPkg.amount || 0).toLocaleString())}` : 'Select a bouquet'}
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
