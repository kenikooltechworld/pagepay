import { useCallback, useState } from 'react';
import {
  Alert,
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
import { useLocalSearchParams, useRouter } from 'expo-router';
import { apiFetch } from '@/src/shared/api/client';
import { AnimatedInput } from '@/components/AnimatedInput';
import { Field, PasswordToggle } from '@/components/Field';
import { PrimaryButton } from '@/components/PrimaryButton';
import { AuthScreenEntrance, AnimatedSubmitButton, ErrorShake, SuccessRedirect } from '@/components/animations';
import { PagePay } from '@/constants/theme';
import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';

export default function ResetPasswordScreen() {
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme];
  const params = useLocalSearchParams<{ token?: string }>();

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [errorTrigger, setErrorTrigger] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [errors, setErrors] = useState<{ password?: string; confirm?: string }>({});

  const validate = useCallback(() => {
    const e: typeof errors = {};
    if (!password) e.password = 'Enter a password.';
    else if (password.length < 8) e.password = 'Use at least 8 characters.';
    if (!confirm) e.confirm = 'Re-enter your password.';
    else if (confirm !== password) e.confirm = "Passwords don't match.";
    return e;
  }, [password, confirm]);

  const handleReset = useCallback(async () => {
    setFormError(null);
    const v = validate();
    setErrors(v);
    if (Object.keys(v).length > 0) {
      setErrorTrigger(true);
      setTimeout(() => setErrorTrigger(false), 600);
      return;
    }

    const token = params.token;
    if (!token) {
      setFormError('Missing reset token. Use the link from your email or SMS.');
      return;
    }

    setLoading(true);
    try {
      const res = await apiFetch('/api/v1/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setFormError(typeof data?.detail === 'string' ? data.detail : 'Could not reset password. Try again.');
        setErrorTrigger(true);
        setTimeout(() => setErrorTrigger(false), 600);
        return;
      }

      setSuccess(true);
      setTimeout(() => router.replace('/(auth)/login'), 1500);
    } catch {
      setFormError("Can't reach the server. Check your connection.");
      setErrorTrigger(true);
      setTimeout(() => setErrorTrigger(false), 600);
    } finally {
      setLoading(false);
    }
  }, [password, confirm, router, params.token, validate]);

  return (
    <View style={[styles.root, { backgroundColor: tokens.paper }]}>
      <StatusBar style={scheme === 'dark' ? 'light' : 'dark'} />
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
                    title="Choose a new password."
                    subtitle="Make it strong and unique."
                  />

                  {formError ? (
                    <View
                      style={[
                        styles.banner,
                        { backgroundColor: tokens.signalSoft, borderColor: tokens.signal },
                      ]}
                    >
                      <Text style={[styles.bannerText, { color: tokens.signal }]}>
                        {formError}
                      </Text>
                    </View>
                  ) : null}

                  <View style={{ gap: 14 }}>
                    <View style={{ gap: 8 }}>
                      <Field
                        label="New password"
                        value={password}
                        onChangeText={setPassword}
                        placeholder="At least 8 characters"
                        secureTextEntry={!showPassword}
                        autoCapitalize="none"
                        autoCorrect={false}
                        returnKeyType="next"
                        error={errors.password}
                        rightIcon={
                          <PasswordToggle
                            visible={showPassword}
                            onToggle={() => setShowPassword((s) => !s)}
                          />
                        }
                      />
                    </View>

                    <Field
                      label="Confirm password"
                      value={confirm}
                      onChangeText={setConfirm}
                      placeholder="Re-enter new password"
                      secureTextEntry={!showPassword}
                      autoCapitalize="none"
                      autoCorrect={false}
                      returnKeyType="go"
                      onSubmitEditing={handleReset}
                      error={errors.confirm}
                    />
                  </View>

                  <AnimatedSubmitButton
                    title={loading ? 'Resetting...' : 'Reset password'}
                    onPress={handleReset}
                    isLoading={loading}
                  />

                  <View style={styles.tertiaryRow}>
                    <Pressable onPress={() => router.back()} hitSlop={6}>
                      <Text style={[styles.tertiaryLink, { color: tokens.mint }]}>
                        ← Back to sign in
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
  tertiaryRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    alignItems: 'center',
    gap: 6,
    marginTop: 8,
    flexWrap: 'wrap',
  },
  tertiaryLink: {
    fontSize: 14,
    fontWeight: '600',
  },
});
