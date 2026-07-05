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

type Disco = {
  code: string;
  name: string;
};

type PurchaseResult = {
  reference: string;
  commission_naira: number;
  points_earned: number;
  new_balance: number;
  status: string;
  token: string | null;
  units: string | null;
};

const AMOUNTS = [1000, 2000, 5000, 10000, 20000];

export default function BuyElectricityScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const insets = useSafeAreaInsets();
  const qc = useQueryClient();

  const [meterNumber, setMeterNumber] = useState('');
  const [disco, setDisco] = useState('ikedc');
  const [meterType, setMeterType] = useState<'prepaid' | 'postpaid'>('prepaid');
  const [amount, setAmount] = useState<number | null>(null);

  const discosQ = useQuery({
    queryKey: ['discos'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/bills/discos');
      if (!res.ok) throw new Error('Failed to load discos');
      return (await res.json()) as Disco[];
    },
  });

  const purchaseMutation = useMutation({
    mutationFn: async () => {
      if (!amount) throw new Error('Select an amount');
      const res = await apiFetch('/api/v1/bills/electricity', {
        method: 'POST',
        body: JSON.stringify({
          meter_number: meterNumber,
          disco,
          meter_type: meterType,
          amount_naira: amount,
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
        'Tokens Purchased!',
        `₦${amount} electricity tokens sent to meter ${meterNumber}. You earned +${data.points_earned} points!`,
        [{ text: 'Done', onPress: () => router.back() }],
      );
    },
    onError: (error: Error) => {
      Alert.alert('Purchase Failed', error.message);
    },
  });

  const canSubmit = meterNumber.length >= 6 && amount !== null;
  const estPoints = amount ? Math.floor(amount * 0.012 * 0.67 * 100) : 0;

  return (
    <View style={{ flex: 1, backgroundColor: tokens.paper, paddingTop: insets.top }}>
      <ScrollView contentContainerStyle={{ padding: 20, gap: 16 }}>
        {/* Header */}
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <TouchableOpacity onPress={() => router.back()}>
            <Ionicons name="chevron-back" size={24} color={tokens.ink} />
          </TouchableOpacity>
          <Text style={[styles.title, { color: tokens.ink }]}>Buy Electricity</Text>
        </View>

        {/* DISCO */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Distribution Company (DISCO)</Text>
        {discosQ.isLoading ? (
          <ActivityIndicator color={tokens.mint} />
        ) : (
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            {(discosQ.data ?? []).map((d) => (
              <TouchableOpacity
                key={d.code}
                onPress={() => setDisco(d.code)}
                style={[
                  styles.discoChip,
                  {
                    backgroundColor: disco === d.code ? tokens.mint : tokens.card,
                    borderColor: disco === d.code ? tokens.mint : tokens.border,
                  },
                ]}
              >
                <Text style={[
                  styles.chipText,
                  {
                    color: disco === d.code ? tokens.mintText : tokens.ink,
                    fontSize: 11,
                  },
                ]}>{d.name.split('(')[0].trim()}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )}

        {/* Meter Type */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Meter Type</Text>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          {(['prepaid', 'postpaid'] as const).map((type) => (
            <TouchableOpacity
              key={type}
              onPress={() => setMeterType(type)}
              style={[
                styles.meterOpt,
                {
                  backgroundColor: meterType === type ? tokens.mintSoft : tokens.card,
                  borderColor: meterType === type ? tokens.mint : tokens.border,
                },
              ]}
            >
              <Ionicons
                name={type === 'prepaid' ? 'keypad-outline' : 'receipt-outline'}
                size={22}
                color={tokens.mint}
              />
              <Text style={[styles.chipText, { color: meterType === type ? tokens.mint : tokens.ink }]}>
                {type.charAt(0).toUpperCase() + type.slice(1)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Meter Number */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Meter Number</Text>
        <TextInput
          style={[styles.input, { backgroundColor: tokens.card, color: tokens.ink, borderColor: tokens.border }]}
          placeholder="1234 5678 9012 3456"
          placeholderTextColor={tokens.inkMuted}
          value={meterNumber}
          onChangeText={setMeterNumber}
          keyboardType="number-pad"
          maxLength={20}
        />

        {/* Amount */}
        <Text style={[styles.label, { color: tokens.inkMuted }]}>Amount</Text>
        <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
          {AMOUNTS.map((a) => (
            <TouchableOpacity
              key={a}
              onPress={() => setAmount(a)}
              style={[
                styles.amtBtn,
                {
                  backgroundColor: amount === a ? tokens.mint : tokens.card,
                  borderColor: amount === a ? tokens.mint : tokens.border,
                },
              ]}
            >
              <Text style={[
                styles.amtText,
                { color: amount === a ? tokens.mintText : tokens.ink },
              ]}>₦{a.toLocaleString()}</Text>
              <Text style={[
                styles.earnText,
                { color: amount === a ? tokens.mintText : tokens.mint },
              ]}>+{Math.floor(a * 0.012 * 0.67 * 100)} pts</Text>
            </TouchableOpacity>
          ))}
        </View>

        {/* Earn notice */}
        {amount && (
          <View style={[styles.earnCard, { backgroundColor: tokens.mintSoft, borderColor: tokens.mint }]}>
            <Ionicons name="gift-outline" size={20} color={tokens.mint} />
            <View style={{ flex: 1 }}>
              <Text style={[styles.earnLabel, { color: tokens.mint }]}>You'll earn +{estPoints} points</Text>
              <Text style={[styles.earnSub, { color: tokens.ink }]}>
                Commission from the electricity purchase is split — you get points, we keep the platform running.
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
                {amount ? `Pay ₦${amount.toLocaleString()}` : 'Select an amount'}
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
  discoChip: {
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 10,
    borderWidth: 1,
  },
  meterOpt: {
    flex: 1, padding: 12, borderRadius: 10, borderWidth: 1,
    alignItems: 'center', gap: 4,
  },
  amtBtn: {
    paddingHorizontal: 16, paddingVertical: 12, borderRadius: 12,
    borderWidth: 1, alignItems: 'center',
  },
  amtText: { fontSize: 14, fontWeight: '700', fontFamily: 'SpaceGrotesk_700Bold' },
  earnText: { fontSize: 10, fontWeight: '600', marginTop: 2 },
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
