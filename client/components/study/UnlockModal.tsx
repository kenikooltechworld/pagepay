import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import { apiFetch } from '@/src/shared/api/client';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PrimaryButton } from '@/components/PrimaryButton';
import { MockAdModal, type AdProvider } from '@/components/ads/MockAdModal';

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
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const canAfford = userBalance >= pointsCost;

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

  const handleAdClaim = async (revenueUsd: number) => {
    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/ads/credit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ad_unit: 'study_unlock',
          provider: 'mock',
          revenue_usd: revenueUsd,
          transaction_id: `study_${Date.now()}`,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(err.detail || 'Ad credit failed');
      }
      await onUnlockPoints();
      setShowAd(false);
      onClose();
    } catch {
      // stay on modal
    } finally {
      setLoading(false);
    }
  };

  const handleAdSkip = () => {
    setShowAd(false);
  };

  if (showAd) {
    return (
      <MockAdModal
        visible
        eyebrow="Sponsored"
        title="Watch to unlock"
        body={`Watch this short ad to unlock the study material for free.`}
        claimLabel="Claim unlock"
        allowSkip
        skipLabel="Skip"
        durationSeconds={15}
        provider="mock"
        onClaim={handleAdClaim}
        onSkip={handleAdSkip}
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
