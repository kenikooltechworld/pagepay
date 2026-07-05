import { useCallback, useMemo, useState } from 'react';
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { StatusBar } from 'expo-status-bar';
import { Ionicons } from '@expo/vector-icons';
import { useRouter } from 'expo-router';

import { apiFetch } from '@/src/shared/api/client';
import { saveToken } from '@/src/shared/lib/storage';
import { PageMark } from '@/components/PageMark';
import { AnimatedInput } from '@/components/AnimatedInput';
import { Field, PasswordToggle } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { AuthScreenEntrance, AnimatedSubmitButton, ErrorShake, SuccessRedirect, PasswordStrengthBar } from '@/components/animations';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

type FieldErrors = Partial<Record<'email' | 'password' | 'confirm' | 'referralCode', string>>;

/**
 * Returns 0..4 — strength of a password. Used to fill the 4-segment bar.
 * 0: empty/short; 1: 8+ chars; 2: 10+ chars OR mixed case; 3: mixed case + digits;
 * 4: mixed case + digits + symbols, 12+ chars.
 */
function passwordStrength(p: string): number {
  if (!p) return 0;
  let score = 0;
  if (p.length >= 8) score++;
  if (p.length >= 10) score++;
  const hasLower = /[a-z]/.test(p);
  const hasUpper = /[A-Z]/.test(p);
  const hasDigit = /\d/.test(p);
  const hasSym = /[^A-Za-z0-9]/.test(p);
  if (hasLower && hasUpper) score++;
  if (hasLower && hasUpper && hasDigit) score++;
  if (hasLower && hasUpper && hasDigit && hasSym && p.length >= 12) score++;
  return Math.min(4, score);
}

export default function RegisterScreen() {
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorTrigger, setErrorTrigger] = useState(false);

  const strength = useMemo(() => passwordStrength(password), [password]);
  const strengthLabel = ['', 'Too weak', 'Weak', 'Good', 'Strong'][strength];
  const strengthColor =
    strength <= 1
      ? tokens.signal
      : strength === 2
        ? tokens.inkMuted
        : tokens.mint;

  // Stable change handlers. Each one only clears its own field error after
  // the first keystroke — never `formError` and never in `onFocus`. Clearing
  // state from `onFocus` was the cause of the focus-jumping loop on Android:
  // focus → setState → layout pass → focus stolen → next field grabs focus.
  const onChangeEmail = useCallback((v: string) => {
    setEmail(v);
    setErrors((p) => (p.email ? { ...p, email: undefined } : p));
  }, []);
  const onChangePassword = useCallback((v: string) => {
    setPassword(v);
    setErrors((p) => (p.password ? { ...p, password: undefined } : p));
  }, []);
  const onChangeConfirm = useCallback((v: string) => {
    setConfirm(v);
    setErrors((p) => (p.confirm ? { ...p, confirm: undefined } : p));
  }, []);
  const onChangeReferralCode = useCallback((v: string) => {
    setReferralCode(v.toUpperCase());
    setErrors((p) => (p.referralCode ? { ...p, referralCode: undefined } : p));
  }, []);

  const validate = useCallback((): FieldErrors => {
    const e: FieldErrors = {};
    if (!email.trim()) e.email = 'Enter your email or phone.';
    if (!password) e.password = 'Enter a password.';
    else if (password.length < 8) e.password = 'Use at least 8 characters.';
    if (!confirm) e.confirm = 'Re-enter your password.';
    else if (confirm !== password) e.confirm = "Passwords don't match.";
    if (referralCode && referralCode.length !== 6) {
      e.referralCode = 'Referral code must be 6 characters.';
    }
    return e;
  }, [email, password, confirm, referralCode]);

  const isEmail = useCallback((v: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v), []);

  const handleRegister = useCallback(async () => {
    setFormError(null);
    const v = validate();
    setErrors(v);
    if (Object.keys(v).length > 0) {
      setErrorTrigger(true);
      setTimeout(() => setErrorTrigger(false), 600);
      return;
    }
    if (!agreed) {
      setFormError('Please agree to the Terms and Privacy Policy to continue.');
      setErrorTrigger(true);
      setTimeout(() => setErrorTrigger(false), 600);
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, string | undefined> = {
        password,
        referral_code: referralCode || undefined,
      };
      if (isEmail(email)) {
        payload.email = email.trim();
      } else if (email.trim().length >= 10) {
        payload.phone = email.trim();
      } else {
        setFormError('Enter a valid email address or phone number.');
        setErrorTrigger(true);
        setTimeout(() => setErrorTrigger(false), 600);
        setLoading(false);
        return;
      }

      const res = await apiFetch('/api/v1/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const status = res.status;
        let detail = '';
        try {
          const data = await res.json();
          detail = typeof data?.detail === 'string' ? data.detail : '';
        } catch {
          /* non-JSON response */
        }
        if (status === 409) {
          setFormError('An account with that email already exists. Sign in instead.');
        } else if (status === 400 && detail.includes('referral')) {
          setErrors({ referralCode: 'Invalid or expired referral code. Check the code and try again.' });
        } else {
          setFormError(detail || "Couldn't create your account. Try again.");
        }
        setErrorTrigger(true);
        setTimeout(() => setErrorTrigger(false), 600);
        return;
      }

      const data = await res.json();
      await saveToken(data.access_token);
      setSuccess(true);
      setTimeout(() => router.replace('/(tabs)'), 1000);
    } catch {
      setFormError("Can't reach the server. Check your connection and try again.");
      setErrorTrigger(true);
      setTimeout(() => setErrorTrigger(false), 600);
    } finally {
      setLoading(false);
    }
  }, [agreed, email, password, router, validate]);

  return (
    <View style={[styles.root, { backgroundColor: tokens.paper }]}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
      
      {/* Success redirect overlay */}
      <SuccessRedirect visible={success} />

      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={styles.flex}
      >
        <ScrollView
          contentContainerStyle={styles.scroll}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          <SafeAreaView edges={['top', 'bottom']}>
            <ErrorShake trigger={errorTrigger}>
              <View style={styles.cardWrap}>
              <View style={[styles.card, { backgroundColor: tokens.card }]}>
                <AuthScreenEntrance 
                  title="Create your PagePay account."
                  subtitle="Earn for reading. Prep for exams. Free to start."
                />

                {formError ? (
                  <View style={[styles.banner, { backgroundColor: tokens.signalSoft, borderColor: tokens.signal }]}>
                    <Text style={[styles.bannerText, { color: tokens.signal }]}>{formError}</Text>
                  </View>
                ) : null}

                <View style={{ gap: 14 }}>
                  <Field
                    label="Email or phone"
                    value={email}
                    onChangeText={onChangeEmail}
                    placeholder="you@example.com"
                    autoCapitalize="none"
                    autoCorrect={false}
                    keyboardType="email-address"
                    textContentType="username"
                    returnKeyType="next"
                    error={errors.email}
                  />

                  <View style={{ gap: 8 }}>
                    <Field
                      label="Password"
                      value={password}
                      onChangeText={onChangePassword}
                      placeholder="At least 8 characters"
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      textContentType="newPassword"
                      returnKeyType="next"
                      error={errors.password}
                      rightIcon={
                        <PasswordToggle
                          visible={showPassword}
                          onToggle={() => setShowPassword((s) => !s)}
                        />
                      }
                    />
                    {password.length > 0 ? (
                      <PasswordStrengthBar
                        strength={strength}
                        label={strengthLabel}
                        color={strengthColor}
                        mutedColor={tokens.border}
                        inkMuted={tokens.inkMuted}
                      />
                    ) : (
                      <Text style={[styles.helper, { color: tokens.inkMuted }]}>
                        At least 8 characters. Mix letters, numbers, and symbols.
                      </Text>
                    )}
                  </View>

                  <Field
                    label="Confirm password"
                    value={confirm}
                    onChangeText={onChangeConfirm}
                    placeholder="Re-enter your password"
                    secureTextEntry={!showPassword}
                    autoCapitalize="none"
                    autoCorrect={false}
                    textContentType="newPassword"
                    returnKeyType="next"
                    error={errors.confirm}
                  />

                  <Field
                    label="Referral code (optional)"
                    value={referralCode}
                    onChangeText={onChangeReferralCode}
                    placeholder="ABC123"
                    autoCapitalize="characters"
                    autoCorrect={false}
                    maxLength={6}
                    returnKeyType="go"
                    onSubmitEditing={handleRegister}
                    error={errors.referralCode}
                  />
                  <Text style={[styles.helper, { color: tokens.inkMuted, marginTop: -8 }]}>
                    Have an invitation code? Enter it here to connect with your referrer.
                  </Text>
                </View>

                  <Pressable
                    onPress={() => setAgreed((a) => !a)}
                    hitSlop={6}
                    style={styles.termsRow}
                    accessibilityRole="checkbox"
                    accessibilityState={{ checked: agreed }}
                  >
                    <View
                      style={[
                        styles.checkbox,
                        {
                          borderColor: agreed ? tokens.mint : tokens.border,
                          backgroundColor: agreed ? tokens.mint : 'transparent',
                        },
                      ]}
                    >
                      {agreed ? (
                        <Ionicons name="checkmark" size={14} color={tokens.mintText} />
                      ) : null}
                    </View>
                    <Text style={[styles.termsText, { color: tokens.inkMuted }]}>
                      I agree to the{' '}
                      <Pressable onPress={() => router.push({ pathname: '/legal', params: { slug: 'terms' } })}>
                        <Text style={{ color: tokens.mint, fontWeight: '600' }}>Terms</Text>
                      </Pressable>
                      {' '}and{' '}
                      <Pressable onPress={() => router.push({ pathname: '/legal', params: { slug: 'privacy' } })}>
                        <Text style={{ color: tokens.mint, fontWeight: '600' }}>Privacy Policy</Text>
                      </Pressable>
                      .
                    </Text>
                  </Pressable>

                <AnimatedSubmitButton
                  title="Create account"
                  isLoading={loading}
                  isSuccess={success}
                  disabled={!agreed}
                  onPress={handleRegister}
                />

                <View style={styles.tertiaryRow}>
                  <Text style={[styles.tertiaryMuted, { color: tokens.inkMuted }]}>
                    Already have an account?
                  </Text>
                  <Pressable onPress={() => router.back()} hitSlop={6}>
                    <Text style={[styles.tertiaryLink, { color: tokens.mint }]}>
                      Sign in  →
                    </Text>
                  </Pressable>
                </View>
              </View>
            </View>
          </ErrorShake>
        </SafeAreaView>
      </ScrollView>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  flex: { flex: 1 },
  scroll: {
    flexGrow: 1,
    paddingHorizontal: 16,
    paddingVertical: 24,
  },
  cardWrap: {
    flex: 1,
    justifyContent: 'center',
  },
  card: {
    borderRadius: 20,
    padding: 24,
    gap: 12,
    shadowColor: '#000',
    shadowOpacity: 0.06,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 12 },
    elevation: 4,
  },
  brand: {
    fontSize: 18,
    letterSpacing: 2,
    textTransform: 'uppercase',
  },
  headline: {
    fontSize: 28,
    lineHeight: 34,
    letterSpacing: -0.5,
    marginTop: 4,
  },
  subline: {
    fontSize: 15,
    lineHeight: 22,
    marginBottom: 8,
  },
  banner: {
    borderRadius: 10,
    borderWidth: 1,
    padding: 12,
    marginTop: 4,
  },
  bannerText: {
    fontSize: 13,
    lineHeight: 18,
  },
  helper: {
    fontSize: 12,
    lineHeight: 16,
  },
  termsRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    marginTop: 6,
  },
  checkbox: {
    width: 20,
    height: 20,
    borderRadius: 6,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 1,
  },
  termsText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 19,
  },
  tertiaryRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
    flexWrap: 'wrap',
  },
  tertiaryMuted: {
    fontSize: 14,
  },
  tertiaryLink: {
    fontSize: 14,
    fontWeight: '600',
  },
});