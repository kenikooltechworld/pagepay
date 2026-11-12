import { useCallback, useMemo, useState } from "react";
import { Pressable, View } from "react-native";
import { useRouter } from "expo-router";
import { Text } from "@/components/ui/text";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { registerRequest, type RegisterInput } from "@/src/shared/api/auth";
import { useAuthStore } from "@/src/shared/store/auth";
import { registerFcmToken } from "@/src/features/auth/lib/register-fcm";

type FieldErrors = Partial<Record<"identity" | "username" | "password" | "confirm" | "referralCode", string>>;

function isEmail(v: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v);
}

function passwordScore(p: string): number {
  let s = 0;
  if (p.length >= 8) s++;
  if (/[A-Z]/.test(p) && /[a-z]/.test(p)) s++;
  if (/\d/.test(p)) s++;
  if (/[^A-Za-z0-9]/.test(p)) s++;
  return s;
}

const strengthLabel = ["Too weak", "Weak", "Fair", "Good", "Strong"] as const;

export function RegisterForm({ onSwitchToLogin }: { onSwitchToLogin?: () => void }) {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);
  const [identity, setIdentity] = useState(""); // email or phone (backend accepts either)
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [referralCode, setReferralCode] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const strength = useMemo(() => passwordScore(password), [password]);

  const clearField = useCallback(<K extends keyof FieldErrors>(k: K) => {
    setErrors((p) => (p[k] ? { ...p, [k]: undefined } : p));
  }, []);

  const validate = (): FieldErrors => {
    const e: FieldErrors = {};
    const id = identity.trim();
    if (!id) e.identity = "Enter your email or phone number.";
    else if (!isEmail(id) && id.replace(/\D/g, "").length < 10)
      e.identity = "Enter a valid email address or phone number.";
    if (username.trim().length > 12) e.username = "Username must be 12 characters or less.";
    if (!password) e.password = "Enter a password.";
    else if (password.length < 8) e.password = "Password must be at least 8 characters.";
    else if (!/[A-Z]/.test(password)) e.password = "Password must contain an uppercase letter.";
    else if (!/\d/.test(password)) e.password = "Password must contain a digit.";
    else if (!/[^A-Za-z0-9]/.test(password)) e.password = "Password must contain a special character.";
    if (!confirm) e.confirm = "Confirm your password.";
    else if (confirm !== password) e.confirm = "Passwords do not match.";
    if (referralCode && referralCode.length !== 6) e.referralCode = "Referral code must be 6 characters.";
    return e;
  };

  const submit = async () => {
    setFormError(null);
    const e = validate();
    setErrors(e);
    if (Object.keys(e).length) return;
    if (!agreed) {
      setFormError("You must agree to the Terms and Privacy Policy.");
      return;
    }

    const id = identity.trim();
    const payload: RegisterInput = { password };
    if (isEmail(id)) payload.email = id;
    else payload.phone = id;
    if (username.trim()) payload.username = username.trim().toLowerCase();
    if (referralCode.trim()) payload.referral_code = referralCode.trim().toUpperCase();

    setLoading(true);
    try {
      // Backend: POST /api/v1/auth/register (JSON, X-Device-Fingerprint) -> TokenResponse
      // Schema: email|phone required, password min 8 + upper+digit+special, username [a-z0-9_] max 12
      const data = await registerRequest(payload);
      await setSession(data.access_token, data.refresh_token);
      await registerFcmToken().catch(() => {});

      router.replace({
        pathname: "/(auth)/verify-email-code",
        params: { email: payload.email || id },
      } as never);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Could not create account.";
      if (/invalid referral/i.test(msg)) {
        setErrors((p) => ({ ...p, referralCode: "Invalid referral code. Check and try again." }));
      } else if (/username already taken/i.test(msg)) {
        setErrors((p) => ({ ...p, username: "Username already taken." }));
      } else if (/user already exists|already exists/i.test(msg)) {
        setFormError("An account with this email or phone already exists.");
      } else {
        setFormError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <View className="bg-card rounded-2xl p-6 shadow-sm gap-4 border border-border/50">
      <View className="gap-1 mb-1">
        <Text className="text-2xl font-bold text-foreground tracking-tight">Create account</Text>
        <Text className="text-muted-foreground text-sm">Join PagePay to get started</Text>
      </View>

      {formError ? (
        <View className="rounded-xl border border-destructive/40 bg-destructive/10 p-3">
          <Text className="text-destructive text-sm">{formError}</Text>
        </View>
      ) : null}

      <View className="gap-2">
        <Label>Email or phone number</Label>
        <Input
          value={identity}
          onChangeText={(v) => {
            setIdentity(v);
            clearField("identity");
          }}
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          placeholder="you@example.com or 080..."
        />
        {errors.identity ? <Text className="text-destructive text-xs">{errors.identity}</Text> : null}
      </View>

      <View className="gap-2">
        <Label>Username (optional)</Label>
        <Input
          value={username}
          onChangeText={(v) => {
            setUsername(v.toLowerCase().replace(/[^a-z0-9_]/g, "").slice(0, 12));
            clearField("username");
          }}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="username"
          maxLength={12}
        />
        {errors.username ? <Text className="text-destructive text-xs">{errors.username}</Text> : null}
      </View>

      <View className="gap-2">
        <Label>Password</Label>
        <PasswordInput
          value={password}
          onChangeText={(v) => {
            setPassword(v);
            clearField("password");
          }}
          placeholder="Min 8 chars, upper, digit, symbol"
          showStrength
        />
        {password ? (
          <Text className="text-muted-foreground text-xs">
            {strengthLabel[Math.min(strength, 4)]} — use 8+ chars with uppercase, digit, and symbol.
          </Text>
        ) : null}
        {errors.password ? <Text className="text-destructive text-xs">{errors.password}</Text> : null}
      </View>

      <View className="gap-2">
        <Label>Confirm password</Label>
        <PasswordInput
          value={confirm}
          onChangeText={(v) => {
            setConfirm(v);
            clearField("confirm");
          }}
          placeholder="Repeat password"
        />
        {errors.confirm ? <Text className="text-destructive text-xs">{errors.confirm}</Text> : null}
      </View>

      <View className="gap-2">
        <Label>Referral code (optional)</Label>
        <Input
          value={referralCode}
          onChangeText={(v) => {
            setReferralCode(v.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 6));
            clearField("referralCode");
          }}
          autoCapitalize="characters"
          autoCorrect={false}
          placeholder="ABC123"
          maxLength={6}
        />
        {errors.referralCode ? <Text className="text-destructive text-xs">{errors.referralCode}</Text> : null}
      </View>

      <View className="flex-row items-start gap-3 mt-1">
        <Pressable onPress={() => setAgreed((a) => !a)} hitSlop={4} className="mt-0.5">
          <Checkbox checked={agreed} onCheckedChange={setAgreed} />
        </Pressable>
        <Text className="text-muted-foreground flex-1 text-sm leading-5">
          I agree to the{" "}
          <Text
            className="text-primary font-semibold"
            onPress={() => router.push({ pathname: "/(auth)/legal", params: { type: "terms" } } as any)}
          >
            Terms
          </Text>{" "}
          and{" "}
          <Text
            className="text-primary font-semibold"
            onPress={() => router.push({ pathname: "/(auth)/legal", params: { type: "privacy" } } as any)}
          >
            Privacy Policy
          </Text>
          .
        </Text>
      </View>

      <Button
        onPress={() => void submit()}
        disabled={loading}
        icon={loading ? <PagePaySpinner size={20} /> : undefined}
        className="mt-2 w-full"
      >
        {loading ? "Creating account..." : "Create account"}
      </Button>

      <View className="flex-row justify-center items-center gap-1 pt-1">
        <Text className="text-muted-foreground text-sm">Already have an account?</Text>
        <Pressable onPress={onSwitchToLogin} hitSlop={6} disabled={!onSwitchToLogin}>
          <Text className="text-primary text-sm font-semibold">Sign in</Text>
        </Pressable>
      </View>
    </View>
  );
}
