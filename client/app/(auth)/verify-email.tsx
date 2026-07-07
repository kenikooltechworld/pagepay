import { useCallback, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { useRouter } from 'expo-router';
import * as Linking from 'expo-linking';
import { useTranslation } from 'react-i18next';

import { apiFetch } from '@/src/shared/api/client';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { PrimaryButton } from '@/components/PrimaryButton';

type Props = {
  email?: string;
};

export default function VerifyEmailScreen({ email }: Props) {
  const { t } = useTranslation();
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleResend = useCallback(async () => {
    setSending(true);
    setError(null);
    setMessage(null);
    try {
      const res = await apiFetch('/api/v1/auth/resend-verification', {
        method: 'POST',
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(typeof data?.detail === 'string' ? data.detail : t('verify_email.error_resend'));
      } else {
        setMessage(t('verify_email.success'));
      }
    } catch {
      setError(t('verify_email.error_connection'));
    } finally {
      setSending(false);
    }
  }, [t]);

  const handleOpenEmail = useCallback(async () => {
    const emailUrl = Linking.createURL('/');
    const mailtoUrl = `mailto:?subject=Verify%20your%20email&body=Check%20your%20inbox%20for%20the%20verification%20link.`;
    await Linking.openURL(mailtoUrl);
  }, []);

  return (
    <SafeAreaView edges={['top']} style={{ flex: 1, backgroundColor: tokens.paper }}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
      <ScrollView contentContainerStyle={styles.scroll}>
        <View style={styles.iconWrap}>
          <Text style={styles.icon}>📧</Text>
        </View>

        <Text style={[styles.title, { color: tokens.ink }]}>{t('verify_email.title')}</Text>
        <Text style={[styles.subtitle, { color: tokens.inkMuted }]}>
          {t('verify_email.subtitle')}{'\n'}
          <Text style={{ fontWeight: '600', color: tokens.ink }}>{email || t('verify_email.your_email')}</Text>
        </Text>

        {error ? (
          <View style={[styles.banner, { backgroundColor: tokens.signalSoft, borderColor: tokens.signal }]}>
            <Text style={[styles.bannerText, { color: tokens.signal }]}>{error}</Text>
          </View>
        ) : null}

        {message ? (
          <View style={[styles.banner, { backgroundColor: tokens.mintSoft, borderColor: tokens.mint }]}>
            <Text style={[styles.bannerText, { color: tokens.mint }]}>{message}</Text>
          </View>
        ) : null}

        <View style={{ gap: 12, marginTop: 24 }}>
          <TouchableOpacity
            onPress={handleOpenEmail}
            style={[styles.secondaryButton, { backgroundColor: tokens.card, borderColor: tokens.border }]}
          >
            <Text style={[styles.secondaryButtonText, { color: tokens.ink }]}>{t('verify_email.open_email')}</Text>
          </TouchableOpacity>
          <PrimaryButton
            title={sending ? t('verify_email.sending') : t('verify_email.resend')}
            onPress={handleResend}
            disabled={sending}
          />
          <TouchableOpacity onPress={() => router.replace('/(tabs)')}>
            <Text style={[styles.hint, { color: tokens.inkMuted }]}>
              {t('verify_email.later')}
            </Text>
          </TouchableOpacity>
        </View>

        <Text style={[styles.hint, { color: tokens.inkMuted }]}>
          {t('verify_email.spam_hint')}
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingHorizontal: 24,
    paddingBottom: 48,
    gap: 16,
  },
  iconWrap: {
    alignItems: 'center',
    marginTop: 48,
    marginBottom: 8,
  },
  icon: {
    fontSize: 64,
  },
  title: {
    fontSize: 24,
    fontWeight: '700',
    textAlign: 'center',
  },
  subtitle: {
    fontSize: 14,
    lineHeight: 20,
    textAlign: 'center',
  },
  banner: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
  },
  bannerText: {
    fontSize: 13,
    textAlign: 'center',
  },
  hint: {
    fontSize: 12,
    textAlign: 'center',
    marginTop: 8,
  },
  secondaryButton: {
    borderRadius: 14,
    borderWidth: 1,
    paddingVertical: 14,
    alignItems: 'center',
    justifyContent: 'center',
  },
  secondaryButtonText: {
    fontSize: 15,
    fontWeight: '600',
  },
});
