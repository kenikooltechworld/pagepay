import { useCallback, useState, useEffect } from 'react';
import {
  ActivityIndicator,
  Alert,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'expo-router';
import Constants from 'expo-constants';
import { Ionicons } from '@expo/vector-icons';

import { apiFetch } from '@/src/shared/api/client';
import {
  displayName,
  initials,
} from '@/src/shared/lib/display-name';
import {
  persistLanguage,
  persistTheme,
  usePreferences,
  type LanguagePref,
  type ThemePref,
} from '@/src/shared/lib/preferences';
import { clearToken } from '@/src/shared/lib/storage';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PagePay } from '@/constants/theme';
import { PageMark } from '@/components/PageMark';
import { ChangePasswordModal } from '@/components/ChangePasswordModal';
import {
  LinkPayoutAccountModal,
  PayoutAccount,
} from '@/components/LinkPayoutAccountModal';
import { HelpModal } from '@/components/HelpModal';
import { AboutModal } from '@/components/AboutModal';
import { useReferralStats, useGenerateReferral } from '@/src/features/community/hooks/use-community';
import { NativeAdBanner } from '@/components/ads/NativeAdBanner';

type UserMe = {
  id: number;
  email: string | null;
  phone: string | null;
  points_balance: number;
  tier: string;
  is_worker: boolean;
  is_sponsor: boolean;
};

const tierLabel: Record<string, string> = {
  free: 'Free',
  premium_monthly: 'Premium · Monthly',
  premium_yearly: 'Premium · Yearly',
};

const languageOptions: { value: LanguagePref; label: string; available: boolean }[] = [
  { value: 'en', label: 'English', available: true },
  { value: 'pcm', label: 'Pidgin', available: false },
  { value: 'yo', label: 'Yoruba', available: false },
  { value: 'ha', label: 'Hausa', available: false },
  { value: 'ig', label: 'Igbo', available: false },
];

const themeOptions: { value: ThemePref; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

export default function ProfileScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const router = useRouter();
  const qc = useQueryClient();

  const theme = usePreferences((s) => s.theme);
  const setTheme = usePreferences((s) => s.setTheme);
  const language = usePreferences((s) => s.language);
  const setLanguage = usePreferences((s) => s.setLanguage);

  const [showChangePassword, setShowChangePassword] = useState(false);
  const [showPayout, setShowPayout] = useState(false);
  const [showHelp, setShowHelp] = useState(false);
  const [showAbout, setShowAbout] = useState(false);

  // Fetch ad config for native unit
  const [nativeAdUnit, setNativeAdUnit] = useState('');
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
      const platform = Platform.OS;
      const unitKey = platform === 'android' ? 'in_feed_android' : 'in_feed_ios';
      setNativeAdUnit(adConfig[unitKey] || '');
    }
  }, [adConfig]);

  const meQuery = useQuery({
    queryKey: ['me'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/auth/me');
      if (!res.ok) throw new Error('Failed to load profile');
      return (await res.json()) as UserMe;
    },
  });

  const payoutQuery = useQuery({
    queryKey: ['payout', 'account'],
    queryFn: async () => {
      const res = await apiFetch('/api/v1/payouts/account');
      if (res.status === 404) return null;
      if (!res.ok) throw new Error('Failed to load payout account');
      return (await res.json()) as PayoutAccount;
    },
    // Phase 1 returns the row on first PUT; we cache briefly so flipping
    // back and forth between the modal and the profile doesn't refetch.
    staleTime: 30_000,
  });

  const handleThemeChange = useCallback(
    (next: ThemePref) => {
      setTheme(next);
      // Fire-and-forget; persistence failure shouldn't crash the UI.
      void persistTheme(next);
    },
    [setTheme],
  );

  const handleLanguageChange = useCallback(
    (next: LanguagePref) => {
      const opt = languageOptions.find((o) => o.value === next);
      if (!opt?.available) {
        Alert.alert('Coming soon', `${opt?.label ?? 'That language'} ships in Phase 4.`);
        return;
      }
      setLanguage(next);
      void persistLanguage(next);
    },
    [setLanguage],
  );

  const handleNotifications = useCallback(() => {
    Alert.alert('Coming soon', 'Notification controls ship in Phase 3.');
  }, []);

  const handleSignOut = useCallback(async () => {
    // Best-effort server-side logout. We don't block UI on it — the
    // real "logout" is `clearToken()`. If the call fails we still want
    // to drop the token and route the user to login.
    try {
      await apiFetch('/api/v1/auth/logout', { method: 'POST' });
    } catch {
      // Network error is fine here — the local token clear is what
      // actually protects the user.
    }
    await clearToken();
    qc.clear();
    router.replace('/(auth)/login');
  }, [qc, router]);

  const version =
    (Constants.expoConfig?.version as string | undefined) ||
    ((Constants.manifest as { version?: string } | undefined)?.version as string | undefined) ||
    '1.0.0';
  const platformLabel =
    scheme === 'dark' ? 'Dark' : 'Light';

  return (
    <SafeAreaView style={[styles.root, { backgroundColor: tokens.paper }]}>
      <ScrollView contentContainerStyle={styles.scroll}>
        {/* ── Header ───────────────────────────────────────────── */}
        <View style={styles.header}>
          <View style={[styles.avatar, { backgroundColor: tokens.mintSoft, borderColor: tokens.border }]}>
            <Text style={[styles.avatarText, { color: tokens.mint, fontFamily: 'SpaceGrotesk_700Bold' }]}>
              {initials(meQuery.data)}
            </Text>
          </View>
          <View style={styles.headerInfo}>
            <Text style={[styles.displayName, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
              {displayName(meQuery.data)}
            </Text>
            <Text style={[styles.identifier, { color: tokens.inkMuted }]}>
              {meQuery.data?.email || meQuery.data?.phone || 'No email or phone on file'}
            </Text>
            <Text style={[styles.tier, { color: tokens.mint }]}>
              {tierLabel[meQuery.data?.tier ?? 'free'] ?? meQuery.data?.tier}
            </Text>
          </View>
        </View>

        {/* ── Phase 7 Roles ───────────────────────────────────── */}
        <Text style={[styles.section, { color: tokens.inkMuted }]}>ROLES</Text>
        <View style={{ gap: 10 }}>
          <Pressable
            onPress={() => router.push('/(tabs)/tasks')}
            style={({ pressed }) => [
              styles.roleCard,
              { backgroundColor: tokens.card, borderColor: tokens.border, opacity: pressed ? 0.85 : 1 },
            ]}
          >
            <View style={[styles.roleIcon, { backgroundColor: tokens.mintSoft }]}>
              <Ionicons name="briefcase-outline" size={20} color={tokens.mint} />
            </View>
            <View style={styles.roleInfo}>
              <Text style={[styles.roleTitle, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
                Tasks
              </Text>
              <Text style={[styles.roleSubtitle, { color: tokens.inkMuted }]}>
                Complete tasks and earn rewards
              </Text>
            </View>
            <Ionicons name="chevron-forward" size={18} color={tokens.inkMuted} />
          </Pressable>

          {!meQuery.data?.is_sponsor && (
            <Pressable
              onPress={() => router.push('/sponsor/register')}
              style={({ pressed }) => [
                styles.roleCard,
                { backgroundColor: tokens.card, borderColor: tokens.mint, opacity: pressed ? 0.85 : 1 },
              ]}
            >
              <View style={[styles.roleIcon, { backgroundColor: tokens.mintSoft }]}>
                <Ionicons name="add-circle-outline" size={20} color={tokens.mint} />
              </View>
              <View style={styles.roleInfo}>
                <Text style={[styles.roleTitle, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
                  Become a Sponsor
                </Text>
                <Text style={[styles.roleSubtitle, { color: tokens.inkMuted }]}>
                  Post tasks and grow your audience
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={tokens.mint} />
            </Pressable>
          )}

          {meQuery.data?.is_sponsor && (
            <Pressable
              onPress={() => router.push('/sponsor/dashboard')}
              style={({ pressed }) => [
                styles.roleCard,
                { backgroundColor: tokens.card, borderColor: tokens.border, opacity: pressed ? 0.85 : 1 },
              ]}
            >
              <View style={[styles.roleIcon, { backgroundColor: tokens.mintSoft }]}>
                <Ionicons name="planet-outline" size={20} color={tokens.mint} />
              </View>
              <View style={styles.roleInfo}>
                <Text style={[styles.roleTitle, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
                  Sponsor Dashboard
                </Text>
                <Text style={[styles.roleSubtitle, { color: tokens.inkMuted }]}>
                  Manage your tasks and payouts
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={tokens.inkMuted} />
            </Pressable>
          )}
        </View>

        {/* ── Payout account ───────────────────────────────────── */}
        <Text style={[styles.section, { color: tokens.inkMuted }]}>PAYOUT ACCOUNT</Text>
        <View style={[styles.payoutCard, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          {payoutQuery.isLoading ? (
            <ActivityIndicator color={tokens.mint} />
          ) : payoutQuery.data ? (
            <View style={styles.payoutInner}>
              <View style={[styles.payoutIcon, { backgroundColor: tokens.mintSoft }]}>
                <Ionicons name="business" size={18} color={tokens.mint} />
              </View>
              <View style={styles.payoutInfo}>
                <Text style={[styles.payoutBank, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
                  {payoutQuery.data.bank_name} ···{payoutQuery.data.account_number_last4}
                </Text>
                <View style={styles.verifyRow}>
                  {payoutQuery.data.verified ? (
                    <>
                      <Ionicons name="checkmark-circle" size={14} color={tokens.mint} />
                      <Text style={[styles.verifyText, { color: tokens.mint }]}>Verified</Text>
                    </>
                  ) : (
                    <>
                      <Ionicons name="hourglass-outline" size={14} color={tokens.signal} />
                      <Text style={[styles.verifyText, { color: tokens.signal }]}>Pending validation</Text>
                    </>
                  )}
                </View>
                {payoutQuery.data.account_name ? (
                  <Text style={[styles.accountName, { color: tokens.inkMuted }]}>
                    {payoutQuery.data.account_name}
                  </Text>
                ) : null}
                <Text style={[styles.accountName, { color: tokens.inkMuted }]}>
                  Min ₦1,000 per withdrawal
                </Text>
              </View>
              <Pressable
                onPress={() => setShowPayout(true)}
                hitSlop={8}
                accessibilityRole="button"
              >
                <Text style={[styles.change, { color: tokens.mint }]}>Change</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.payoutInner}>
              <View style={[styles.payoutIcon, { backgroundColor: tokens.signalSoft }]}>
                <Ionicons name="business-outline" size={18} color={tokens.signal} />
              </View>
              <View style={styles.payoutInfo}>
                <Text style={[styles.payoutBank, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
                  No bank account linked
                </Text>
                <Text style={[styles.payoutHint, { color: tokens.inkMuted }]}>
                  Add your bank account to withdraw earnings. Paystack validation is required before any withdrawal.
                </Text>
              </View>
              <Pressable
                onPress={() => setShowPayout(true)}
                hitSlop={8}
                accessibilityRole="button"
              >
                <Text style={[styles.change, { color: tokens.mint }]}>Link</Text>
              </Pressable>
            </View>
          )}
        </View>

        {/* ── Referral ──────────────────────────────────────────── */}
        <ReferralSection tokens={tokens} />

        {/* ── Native ad after stats ─────────────────────────────── */}
        {nativeAdUnit && (
          <NativeAdBanner
            adUnit={nativeAdUnit}
            sessionId={null}
          />
        )}

        {/* ── Settings rows ────────────────────────────────────── */}
        <Text style={[styles.section, { color: tokens.inkMuted }]}>ACCOUNT</Text>
        <View style={[styles.card, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          <Row
            tokens={tokens}
            icon="lock-closed-outline"
            label="Change password"
            onPress={() => setShowChangePassword(true)}
          />
          <Divider tokens={tokens} />
          <Row
            tokens={tokens}
            icon="notifications-outline"
            label="Notifications"
            trailing={<Text style={[styles.trailingHint, { color: tokens.inkMuted }]}>Coming soon</Text>}
            onPress={handleNotifications}
          />
        </View>

        <Text style={[styles.section, { color: tokens.inkMuted }]}>APPEARANCE</Text>
        <View style={[styles.card, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          <View style={styles.row}>
            <View style={styles.rowLeft}>
              <Ionicons name="sunny-outline" size={18} color={tokens.inkMuted} />
              <Text style={[styles.rowLabel, { color: tokens.ink }]}>Theme</Text>
            </View>
          </View>
          <View style={[styles.segmented, { backgroundColor: tokens.paper, borderColor: tokens.border }]}>
            {themeOptions.map((opt) => {
              const active = theme === opt.value;
              return (
                <Pressable
                  key={opt.value}
                  onPress={() => handleThemeChange(opt.value)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  style={({ pressed }) => [
                    styles.segment,
                    {
                      backgroundColor: active ? tokens.mint : 'transparent',
                      opacity: pressed ? 0.85 : 1,
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.segmentLabel,
                      {
                        color: active ? tokens.mintText : tokens.ink,
                        fontFamily: active ? 'SpaceGrotesk_700Bold' : 'SpaceGrotesk_500Medium',
                      },
                    ]}
                  >
                    {opt.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>

          <Divider tokens={tokens} />

          <View style={styles.row}>
            <View style={styles.rowLeft}>
              <Ionicons name="language-outline" size={18} color={tokens.inkMuted} />
              <Text style={[styles.rowLabel, { color: tokens.ink }]}>Language</Text>
            </View>
          </View>
          <View style={[styles.langGrid, { borderColor: tokens.border }]}>
            {languageOptions.map((opt) => {
              const active = language === opt.value;
              return (
                <Pressable
                  key={opt.value}
                  onPress={() => handleLanguageChange(opt.value)}
                  accessibilityRole="button"
                  accessibilityState={{ selected: active }}
                  style={({ pressed }) => [
                    styles.langPill,
                    {
                      backgroundColor: active ? tokens.mint : tokens.paper,
                      borderColor: tokens.border,
                      opacity: pressed ? 0.85 : 1,
                    },
                  ]}
                >
                  <Text
                    style={[
                      styles.langLabel,
                      {
                        color: active ? tokens.mintText : tokens.ink,
                        fontFamily: active ? 'SpaceGrotesk_700Bold' : 'SpaceGrotesk_500Medium',
                      },
                    ]}
                  >
                    {opt.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
        </View>

        <Text style={[styles.section, { color: tokens.inkMuted }]}>SUPPORT</Text>
        <View style={[styles.card, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
          <Row
            tokens={tokens}
            icon="help-circle-outline"
            label="Help & support"
            onPress={() => setShowHelp(true)}
          />
          <Divider tokens={tokens} />
          <Row
            tokens={tokens}
            icon="information-circle-outline"
            label="About / app version"
            trailing={<Text style={[styles.trailingHint, { color: tokens.inkMuted }]}>v{version}</Text>}
            onPress={() => setShowAbout(true)}
          />
        </View>

        {/* ── Sign out ─────────────────────────────────────────── */}
        <Pressable
          onPress={handleSignOut}
          accessibilityRole="button"
          style={({ pressed }) => [
            styles.signOut,
            {
              backgroundColor: tokens.signalSoft,
              opacity: pressed ? 0.85 : 1,
            },
          ]}
        >
          <Ionicons name="log-out-outline" size={18} color={tokens.signal} />
          <Text style={[styles.signOutText, { color: tokens.signal, fontFamily: 'SpaceGrotesk_700Bold' }]}>
            Sign out
          </Text>
        </Pressable>

        {/* ── Footer ───────────────────────────────────────────── */}
        <View style={styles.footer}>
          <PageMark />
          <Text style={[styles.footerText, { color: tokens.inkMuted }]}>
            PagePay v{version} · {platformLabel}
          </Text>
        </View>
      </ScrollView>

      <ChangePasswordModal
        visible={showChangePassword}
        onClose={() => setShowChangePassword(false)}
      />
      <LinkPayoutAccountModal
        visible={showPayout}
        current={payoutQuery.data ?? null}
        onClose={() => setShowPayout(false)}
        onSaved={() => {
          void qc.invalidateQueries({ queryKey: ['payout', 'account'] });
          void qc.invalidateQueries({ queryKey: ['me'] });
        }}
      />
      <HelpModal visible={showHelp} onClose={() => setShowHelp(false)} />
      <AboutModal visible={showAbout} onClose={() => setShowAbout(false)} />
    </SafeAreaView>
  );
}

// ── Sub-components ───────────────────────────────────────────────────

function Row({
  tokens,
  icon,
  label,
  trailing,
  onPress,
}: {
  tokens: (typeof PagePay)['light'] | (typeof PagePay)['dark'];
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  trailing?: React.ReactNode;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [styles.row, { opacity: pressed ? 0.7 : 1 }]}
    >
      <View style={styles.rowLeft}>
        <Ionicons name={icon} size={18} color={tokens.inkMuted} />
        <Text style={[styles.rowLabel, { color: tokens.ink }]}>{label}</Text>
      </View>
      <View style={styles.rowRight}>
        {trailing}
        <Ionicons name="chevron-forward" size={18} color={tokens.inkMuted} />
      </View>
    </Pressable>
  );
}

function Divider({
  tokens,
}: {
  tokens: (typeof PagePay)['light'] | (typeof PagePay)['dark'];
}) {
  return <View style={[styles.divider, { backgroundColor: tokens.border }]} />;
}

function ReferralSection({ tokens }: { tokens: (typeof PagePay)['light'] | (typeof PagePay)['dark'] }) {
  const statsQ = useReferralStats();
  const generateMutation = useGenerateReferral();
  const [copied, setCopied] = useState(false);

  const stats = statsQ.data as { code: string; signups: number; pending_rewards: number; claimed_rewards: number } | undefined;
  const code = stats?.code ?? '';
  const link = code ? `https://pagepay.app/ref/${code}` : '';

  const handleGenerate = async () => {
    try {
      await generateMutation.mutateAsync();
    } catch {
      // silent
    }
  };

  const handleShare = async () => {
    if (!link) return;
    Alert.alert('Referral link', link);
  };

  const handleCopy = async () => {
    if (!link) return;
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <View style={[styles.referralCard, { backgroundColor: tokens.card, borderColor: tokens.border }]}>
      <View style={styles.referralHeader}>
        <Ionicons name="gift-outline" size={20} color={tokens.mint} />
        <Text style={[styles.referralTitle, { color: tokens.ink, fontFamily: 'SpaceGrotesk_700Bold' }]}>
          Refer Friends
        </Text>
      </View>
      <Text style={[styles.referralSubtitle, { color: tokens.inkMuted }]}>
        Share your code. Both you and your friend earn points!
      </Text>

      {code ? (
        <View style={[styles.codeBox, { backgroundColor: tokens.paper, borderColor: tokens.border }]}>
          <Text style={[styles.codeText, { color: tokens.mint, fontFamily: 'SpaceGrotesk_700Bold' }]}>
            {code}
          </Text>
        </View>
      ) : (
        <TouchableOpacity
          onPress={handleGenerate}
          disabled={generateMutation.isPending}
          style={[styles.generateBtn, { backgroundColor: tokens.mint }]}
          activeOpacity={0.7}
        >
          <Text style={[styles.generateText, { color: tokens.mintText }]}>
            {generateMutation.isPending ? 'Generating...' : 'Generate Referral Code'}
          </Text>
        </TouchableOpacity>
      )}

      {code && (
        <View style={{ flexDirection: 'row', gap: 8, marginTop: 10 }}>
          <TouchableOpacity
            onPress={handleCopy}
            style={[styles.actionBtn, { borderColor: tokens.border }]}
            activeOpacity={0.7}
          >
            <Ionicons name={copied ? 'checkmark-outline' : 'copy-outline'} size={16} color={tokens.mint} />
            <Text style={[styles.actionText, { color: tokens.mint }]}>
              {copied ? 'Copied!' : 'Copy'}
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            onPress={handleShare}
            style={[styles.actionBtn, { borderColor: tokens.border }]}
            activeOpacity={0.7}
          >
            <Ionicons name="share-social-outline" size={16} color={tokens.mint} />
            <Text style={[styles.actionText, { color: tokens.mint }]}>Share</Text>
          </TouchableOpacity>
        </View>
      )}

      {stats && (
        <View style={styles.statsRow}>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: tokens.ink }]}>{stats.signups}</Text>
            <Text style={[styles.statLabel, { color: tokens.inkMuted }]}>Signups</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: tokens.ink }]}>{stats.pending_rewards}</Text>
            <Text style={[styles.statLabel, { color: tokens.inkMuted }]}>Pending</Text>
          </View>
          <View style={styles.stat}>
            <Text style={[styles.statValue, { color: tokens.mint }]}>{stats.claimed_rewards}</Text>
            <Text style={[styles.statLabel, { color: tokens.inkMuted }]}>Claimed</Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
  scroll: {
    paddingHorizontal: 20,
    paddingBottom: 48,
    gap: 14,
  },
  // Header
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 12,
    marginBottom: 12,
    gap: 16,
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: 36,
    borderWidth: StyleSheet.hairlineWidth,
    alignItems: 'center',
    justifyContent: 'center',
  },
  avatarText: {
    fontSize: 24,
    letterSpacing: 0.5,
  },
  headerInfo: {
    flex: 1,
    gap: 2,
  },
  displayName: {
    fontSize: 22,
    letterSpacing: -0.3,
  },
  identifier: {
    fontSize: 13,
  },
  tier: {
    fontSize: 12,
    fontWeight: '600',
    letterSpacing: 0.4,
    marginTop: 2,
  },
  // Section header
  section: {
    fontSize: 11,
    letterSpacing: 1.0,
    fontWeight: '600',
    marginTop: 6,
    marginLeft: 4,
  },
  // Role cards
  roleCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    borderRadius: 16,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 16,
  },
  roleIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  roleInfo: {
    flex: 1,
    gap: 2,
  },
  roleTitle: {
    fontSize: 15,
  },
  roleSubtitle: {
    fontSize: 12,
    lineHeight: 17,
  },
  // Payout card
  payoutCard: {
    borderRadius: 16,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 16,
  },
  payoutInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  payoutIcon: {
    width: 36,
    height: 36,
    borderRadius: 18,
    alignItems: 'center',
    justifyContent: 'center',
  },
  payoutInfo: {
    flex: 1,
    gap: 4,
  },
  payoutBank: {
    fontSize: 15,
  },
  verifyRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
  },
  verifyText: {
    fontSize: 12,
    fontWeight: '600',
  },
  accountName: {
    fontSize: 12,
  },
  payoutHint: {
    fontSize: 12,
    lineHeight: 17,
  },
  change: {
    fontSize: 14,
    fontWeight: '600',
  },
  // Generic card + row
  card: {
    borderRadius: 16,
    borderWidth: StyleSheet.hairlineWidth,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 14,
    paddingHorizontal: 16,
    minHeight: 52,
  },
  rowLeft: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    flex: 1,
  },
  rowLabel: {
    fontSize: 15,
    fontWeight: '500',
  },
  rowRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  trailingHint: {
    fontSize: 13,
  },
  divider: {
    height: StyleSheet.hairlineWidth,
    marginLeft: 46,
  },
  // Theme segmented
  segmented: {
    flexDirection: 'row',
    margin: 12,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 3,
    gap: 3,
  },
  segment: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 6,
    borderRadius: 9,
    alignItems: 'center',
    justifyContent: 'center',
  },
  segmentLabel: {
    fontSize: 13,
  },
  // Language grid
  langGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    padding: 12,
  },
  langPill: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 999,
    borderWidth: StyleSheet.hairlineWidth,
  },
  langLabel: {
    fontSize: 13,
  },
  // Sign out
  signOut: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingVertical: 14,
    borderRadius: 14,
    marginTop: 18,
  },
  signOutText: {
    fontSize: 15,
  },
  // Footer
  footer: {
    alignItems: 'center',
    paddingTop: 18,
    gap: 6,
  },
  footerText: {
    fontSize: 12,
    letterSpacing: 0.2,
  },
  // Referral
  referralCard: {
    borderRadius: 16,
    borderWidth: StyleSheet.hairlineWidth,
    padding: 16,
    gap: 10,
  },
  referralHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  referralTitle: {
    fontSize: 16,
  },
  referralSubtitle: {
    fontSize: 13,
    lineHeight: 18,
  },
  codeBox: {
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
    paddingVertical: 12,
    alignItems: 'center',
  },
  codeText: {
    fontSize: 20,
    letterSpacing: 2,
  },
  generateBtn: {
    paddingVertical: 12,
    borderRadius: 12,
    alignItems: 'center',
  },
  generateText: {
    fontSize: 14,
    fontWeight: '700',
  },
  actionBtn: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingVertical: 10,
    borderRadius: 12,
    borderWidth: StyleSheet.hairlineWidth,
  },
  actionText: {
    fontSize: 13,
    fontWeight: '600',
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingTop: 10,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#e5e5e5',
    marginTop: 4,
  },
  stat: {
    alignItems: 'center',
    gap: 2,
  },
  statValue: {
    fontSize: 18,
    fontWeight: '700',
  },
  statLabel: {
    fontSize: 11,
  },
});