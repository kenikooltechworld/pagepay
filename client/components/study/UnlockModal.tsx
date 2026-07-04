import { useState, useEffect } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useQuery } from '@tanstack/react-query';

import { apiFetch } from '@/src/shared/api/client';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PrimaryButton } from '@/components/PrimaryButton';
import { RewardedAd } from '@/components/ads/RewardedAd';

type UnlockModalProps = {
  visible: boolean;
  pointsCost: number;
  userBalance: number;
  onUnlockPoints: () => Promise<void>;
  onWatchAd: () => Promise<void>;
  onClose: () => void;
};

export function UnlockModal({
  visible,
  pointsCost,
  userBalance,
  onUnlockPoints,
  onWatchAd,
  onClose,
}: UnlockModalProps) {
  const [showAd, setShowAd] = useState(false);
  const [loading, setLoading] = useState(false);
  const [adUnit, setAdUnit] = useState('');
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const canAfford = userBalance >= pointsCost;

  // Fetch current user for userId (required for SSV)
  const { data: user } = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/auth/me');
      if (!res.ok) throw new Error('Failed to load profile');
      return (await res.json()) as { id: number; points_balance: number };
    },
  });

  // Fetch ad config for rewarded unit
  const { data: adConfig } = useQuery({
    queryKey: ['ads-config'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/config/ads?env=dev');
      if (!res.ok) return {};
      return (await res.json()) as Record<string, string>;
    },
  });

  useEffect(() => {
    if (adConfig) {
      const platform = require('react-native').Platform.OS;
      const unitKey = platform === 'android' ? 'rewarded_android' : 'rewarded_ios';
      setAdUnit(adConfig[unitKey] || '');
    }
  }, [adConfig]);

  const handlePointsUnlock = async () => {
    setLoading(true);
    try {
      await onUnlockPoints();
      onClose();
    } finally {
      setLoading(false);
    }
  };

  const handleAdStart = () => {
    setShowAd(true);
  };

  const handleAdClaimed = async (info: {
    adEventId: number;
    pointsCredited: number;
    newBalance: number;
  }) => {
    // Ad reward already credited by RewardedAd component
    // Now unlock the study material
    setLoading(true);
    try {
      await onUnlockPoints();
      setShowAd(false);
      onClose();
    } catch {
      // stay on modal
    } finally {
      setLoading(false);
    }
  };

  const handleAdClose = () => {
    setShowAd(false);
  };

  if (showAd && user) {
    return (
      <RewardedAd
        visible
        adUnit={adUnit}
        userId={user.id}
        sessionId={null}
        title="Watch to unlock"
        eyebrow="Sponsored"
        body="Watch this ad to unlock the study material for free."
        claimLabel="Claim unlock"
        allowSkip
        skipLabel="Skip"
        durationSeconds={15}
        onClaimed={handleAdClaimed}
        onSkipped={handleAdClose}
        onClose={handleAdClose}
      />
    );
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.overlay}>
        <View style={[styles.sheet, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          <View style={styles.headerRow}>
            <Ionicons name="lock-closed-outline" size={22} color={tokens.mint} />
            <Text style={[styles.title, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
              Unlock answer
            </Text>
          </View>

          <Text style={[styles.cost, { color: tokens.inkMuted }]}>
            This asset costs <Text style={{ color: tokens.mint, fontWeight: '700' }}>{pointsCost} pts</Text> to unlock.
            {'\n'}Your balance: <Text style={{ color: tokens.ink, fontWeight: '600' }}>{userBalance} pts</Text>
          </Text>

          <View style={styles.buttons}>
            <PrimaryButton
              title={canAfford ? `Spend ${pointsCost} pts` : 'Not enough points'}
              onPress={handlePointsUnlock}
              loading={loading}
              disabled={!canAfford}
            />
            <PrimaryButton
              title="Watch ad instead"
              onPress={handleAdStart}
              loading={loading}
            />
          </View>

          <Pressable onPress={onClose} style={({ pressed }) => [styles.close, { opacity: pressed ? 0.5 : 1 }]}>
            <Text style={[styles.closeText, { color: tokens.inkMuted }]}>Cancel</Text>
          </Pressable>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  sheet: {
    width: '100%',
    borderRadius: 20,
    borderWidth: 1,
    padding: 24,
    gap: 16,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  title: {
    fontSize: 20,
    letterSpacing: -0.4,
  },
  cost: {
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  buttons: {
    gap: 10,
  },
  close: {
    alignSelf: 'center',
    paddingVertical: 8,
  },
  closeText: {
    fontSize: 13,
    fontWeight: '500',
  },
});
