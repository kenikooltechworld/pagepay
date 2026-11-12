import { useState } from "react";
import { KeyboardAvoidingView, Platform, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useMutation } from "@tanstack/react-query";
import { Text } from "@/components/ui/text";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { apiFetch, parseApiError } from "@/src/shared/api/client";

/**
 * Backend (app/backend):
 * - POST /api/v1/auth/forgot-password  {email?|phone?|username?} -> {ok, dev_otp?, message}
 * - POST /api/v1/auth/forgot-password/verify-otp {email?|phone?|username?, otp} -> {ok, reset_token}
 * - POST /api/v1/auth/reset-password {token, new_password} -> {ok, message}
 * Password rules match backend schema: min 8, uppercase, digit, special char.
 */
type IdentityKind = "email" | "phone" | "username";

function classifyIdentity(v: string): { kind: IdentityKind; payload: Record<string, string> } {
  const s = v.trim();
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)) return { kind: "email", payload: { email: s } };
  if (/^\+?[\d\s()-]{10,}$/.test(s)) return { kind: "phone", payload: { phone: s } };
  return { kind: "username", payload: { username: s.toLowerCase() } };
}

function validateNewPassword(pw: string): string | null {
  if (pw.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Z]/.test(pw)) return "Password must contain an uppercase letter.";
  if (!/\d/.test(pw)) return "Password must contain a digit.";
  if (!/[^A-Za-z0-9]/.test(pw)) return "Password must contain a special character.";
  return null;
}

export default function ForgotPasswordScreen() {
  const router = useRouter();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [identity, setIdentity] = useState("");
  const [identityPayload, setIdentityPayload] = useState<Record<string, string>>({});
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  const requestReset = useMutation({
    mutationFn: async () => {
      const id = identity.trim();
      if (!id) throw new Error("Enter your email, phone number, or username.");
      const { payload } = classifyIdentity(id);
      // Backend keys OTP by (email|phone|username) value; keep exact payload for verify step.
      setIdentityPayload(payload);
      setOtp("");
      setResetToken("");
      const res = await apiFetch("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await parseApiError(res, "Could not send reset code"));
      return (await res.json()) as { ok?: boolean; message?: string };
    },
    onSuccess: (data) => {
      setError(null);
      setInfo(data.message || "If that account exists, a reset code has been sent.");
      setStep(2);
    },
    onError: (e) => {
      setInfo(null);
      setError(e instanceof Error ? e.message : "Could not send reset code");
    },
  });

  const verifyOtp = useMutation({
    mutationFn: async () => {
      const code = otp.replace(/\D/g, "").trim();
      if (code.length !== 6) throw new Error("Enter the 6-digit code.");
      if (!Object.keys(identityPayload).length) {
        throw new Error("Missing account details. Request a new reset code.");
      }
      const res = await apiFetch("/auth/forgot-password/verify-otp", {
        method: "POST",
        body: JSON.stringify({ ...identityPayload, otp: code }),
      });
      if (!res.ok) throw new Error(await parseApiError(res, "Invalid code"));
      return (await res.json()) as { ok?: boolean; reset_token?: string | null };
    },
    onSuccess: (data) => {
      if (!data.reset_token) {
        setError("Could not verify code. Try again.");
        return;
      }
      setResetToken(data.reset_token);
      setError(null);
      setInfo("Code verified. Set a new password.");
      setStep(3);
    },
    onError: (e) => {
      setInfo(null);
      setError(e instanceof Error ? e.message : "Invalid code");
    },
  });

  const resetPassword = useMutation({
    mutationFn: async () => {
      const pwErr = validateNewPassword(newPassword);
      if (pwErr) throw new Error(pwErr);
      if (newPassword !== confirmPassword) throw new Error("Passwords do not match.");
      if (!resetToken) throw new Error("Missing reset token. Start over.");
      const res = await apiFetch("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token: resetToken, new_password: newPassword }),
      });
      if (!res.ok) throw new Error(await parseApiError(res, "Could not reset password"));
      return (await res.json()) as { ok?: boolean; message?: string };
    },
    onSuccess: () => {
      setError(null);
      router.replace("/(auth)" as any);
    },
    onError: (e) => setError(e.message),
  });

  const busy = requestReset.isPending || verifyOtp.isPending || resetPassword.isPending;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} style={{ flex: 1 }}>
          <ScrollView contentContainerClassName="flex-grow justify-center p-6" keyboardShouldPersistTaps="handled">
            <View className="gap-4">
              <Text className="text-foreground text-2xl font-bold">
                {step === 1 ? "Reset password" : step === 2 ? "Enter code" : "New password"}
              </Text>
              <Text className="text-muted-foreground">
                {step === 1
                  ? "Enter the email, phone number, or username on your account."
                  : step === 2
                    ? `Enter the 6-digit code sent for ${identity.trim() || "your account"}.`
                    : "Choose a strong new password."}
              </Text>

              {error ? (
                <View className="rounded-xl border border-destructive/40 bg-destructive/10 p-3">
                  <Text className="text-destructive text-sm">{error}</Text>
                </View>
              ) : null}
              {info ? <Text className="text-primary text-sm">{info}</Text> : null}

              {step === 1 ? (
                <View className="gap-2">
                  <Label>Email, phone, or username</Label>
                  <Input
                    value={identity}
                    onChangeText={(v) => {
                      setIdentity(v);
                      setError(null);
                    }}
                    autoCapitalize="none"
                    autoCorrect={false}
                    placeholder="you@example.com"
                  />
                  <Button
                    onPress={() => requestReset.mutate()}
                    disabled={busy}
                    icon={requestReset.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    {requestReset.isPending ? "Sending..." : "Send reset code"}
                  </Button>
                </View>
              ) : null}

              {step === 2 ? (
                <View className="gap-2">
                  <Label>Reset code</Label>
                  <Input
                    value={otp}
                    onChangeText={(v) => {
                      setOtp(v.replace(/\D/g, "").slice(0, 6));
                      setError(null);
                    }}
                    keyboardType="number-pad"
                    placeholder="123456"
                    maxLength={6}
                    autoComplete="one-time-code"
                  />
                  <Button
                    onPress={() => verifyOtp.mutate()}
                    disabled={busy || otp.replace(/\D/g, "").length !== 6}
                    icon={verifyOtp.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    {verifyOtp.isPending ? "Verifying..." : "Verify code"}
                  </Button>
                  <Button
                    variant="outline"
                    onPress={() => requestReset.mutate()}
                    disabled={busy}
                    icon={requestReset.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    Resend code
                  </Button>
                  <Text className="text-muted-foreground text-xs">
                    Use the same account identity you entered. Codes expire quickly; request a new one if needed.
                  </Text>
                </View>
              ) : null}

              {step === 3 ? (
                <View className="gap-3">
                  <View className="gap-2">
                    <Label>New password</Label>
                    <PasswordInput
                      value={newPassword}
                      onChangeText={(v) => {
                        setNewPassword(v);
                        setError(null);
                      }}
                      placeholder="Min 8 chars, upper, digit, symbol"
                      showStrength
                    />
                  </View>
                  <View className="gap-2">
                    <Label>Confirm new password</Label>
                    <PasswordInput
                      value={confirmPassword}
                      onChangeText={(v) => {
                        setConfirmPassword(v);
                        setError(null);
                      }}
                      placeholder="Repeat password"
                    />
                  </View>
                  <Button
                    onPress={() => resetPassword.mutate()}
                    disabled={busy}
                    icon={resetPassword.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    {resetPassword.isPending ? "Saving..." : "Reset password"}
                  </Button>
                </View>
              ) : null}

              <Button variant="ghost" onPress={() => router.back()} disabled={busy}>
                Back to sign in
              </Button>
            </View>
          </ScrollView>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}
