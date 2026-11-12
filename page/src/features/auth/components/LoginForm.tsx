import { useCallback, useState } from "react";
import { Modal, Platform, Pressable, View } from "react-native";
import { useRouter } from "expo-router";
import Constants from "expo-constants";
import * as WebBrowser from "expo-web-browser";
import { Text } from "@/components/ui/text";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { googleLoginRequest, loginRequest } from "@/src/shared/api/auth";
import { fetchCurrentUser } from "@/src/shared/lib/current-user";
import { useAuthStore } from "@/src/shared/store/auth";
import { registerFcmToken } from "@/src/features/auth/lib/register-fcm";

WebBrowser.maybeCompleteAuthSession();

type FieldErrors = Partial<Record<"identity" | "password", string>>;

export function LoginForm({ onSwitchToRegister }: { onSwitchToRegister?: () => void }) {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [verifyEmail, setVerifyEmail] = useState("");
  const [showGoogleModal, setShowGoogleModal] = useState(false);
  const [googleIdToken, setGoogleIdToken] = useState("");
  const [googleLoading, setGoogleLoading] = useState(false);

  const googleClientId =
    ((Constants.expoConfig?.extra as { googleClientId?: string } | undefined)?.googleClientId ||
      process.env.EXPO_PUBLIC_GOOGLE_CLIENT_ID ||
      "") as string;

  const onChangeIdentity = useCallback((v: string) => {
    setIdentity(v);
    setErrors((p) => (p.identity ? { ...p, identity: undefined } : p));
  }, []);
  const onChangePassword = useCallback((v: string) => {
    setPassword(v);
    setErrors((p) => (p.password ? { ...p, password: undefined } : p));
  }, []);

  const submit = async () => {
    setFormError(null);
    const e: FieldErrors = {};
    if (!identity.trim()) e.identity = "Enter your email, phone, or username.";
    if (!password) e.password = "Enter your password.";
    setErrors(e);
    if (Object.keys(e).length) return;

    setLoading(true);
    try {
      // Backend: POST /api/v1/auth/login (form: username+password, X-Device-Fingerprint) -> TokenResponse
      const data = await loginRequest({ username: identity.trim(), password });
      await setSession(data.access_token, data.refresh_token);

      // Backend: GET /api/v1/auth/me (Bearer) -> UserMe incl. email_verified
      const user = await fetchCurrentUser();
      await registerFcmToken().catch(() => {});

      if (user?.email_verified === false && user?.email) {
        setVerifyEmail(user.email);
        setShowVerifyModal(true);
        return;
      }
      router.replace("/(app)/home" as any);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Login failed";
      if (/invalid credentials/i.test(msg)) {
        setFormError("Incorrect email, phone, username, or password.");
      } else {
        setFormError(msg);
      }
    } finally {
      setLoading(false);
    }
  };

  const completeGoogleSignIn = async (idToken: string) => {
    const data = await googleLoginRequest(idToken);
    await setSession(data.access_token, data.refresh_token);
    const user = await fetchCurrentUser();
    await registerFcmToken().catch(() => {});
    setShowGoogleModal(false);
    setGoogleIdToken("");
    if (user?.email_verified === false && user?.email) {
      setVerifyEmail(user.email);
      setShowVerifyModal(true);
      return;
    }
    router.replace("/(app)/home" as any);
  };

  const startGoogleSignIn = async () => {
    if (!googleClientId) {
      setShowGoogleModal(true);
      return;
    }
    setFormError(null);
    setGoogleLoading(true);
    try {
      const redirectUri =
        Platform.OS === "web" && typeof window !== "undefined"
          ? window.location.origin
          : "https://auth.expo.io/@kenzola/pagepay";
      const nonce = Math.random().toString(36).slice(2) + Date.now().toString(36);
      const authUrl =
        "https://accounts.google.com/o/oauth2/v2/auth" +
        `?client_id=${encodeURIComponent(googleClientId)}` +
        `&redirect_uri=${encodeURIComponent(redirectUri)}` +
        "&response_type=id_token" +
        "&scope=openid%20email%20profile" +
        `&nonce=${encodeURIComponent(nonce)}` +
        "&prompt=select_account";
      // In-app auth session (Custom Tabs on Android, ASWebAuthenticationSession on iOS) - no external browser app.
      const result = await WebBrowser.openAuthSessionAsync(authUrl, redirectUri, {
        preferEphemeralSession: false,
        showInRecents: false,
      });
      if (result.type !== "success" || !result.url) {
        if (result.type !== "cancel" && result.type !== "dismiss") {
          throw new Error("Google sign-in was not completed.");
        }
        return;
      }
      const fragment = result.url.includes("#") ? result.url.split("#")[1] : "";
      const params = new URLSearchParams(fragment || (result.url.includes("?") ? result.url.split("?")[1] : ""));
      const idToken = params.get("id_token");
      if (!idToken) throw new Error("Google did not return an ID token. Check redirect URI/client configuration.");
      await completeGoogleSignIn(idToken);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Google sign-in failed");
    } finally {
      setGoogleLoading(false);
    }
  };

  const submitGoogle = async () => {
    const token = googleIdToken.trim();
    if (!token) return;
    setFormError(null);
    setGoogleLoading(true);
    try {
      await completeGoogleSignIn(token);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Google sign-in failed");
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <View className="bg-card rounded-2xl p-6 shadow-sm gap-4 border border-border/50">
      <View className="gap-1 mb-1">
        <Text className="text-2xl font-bold text-foreground tracking-tight">Welcome back</Text>
        <Text className="text-muted-foreground text-sm">Sign in to continue to PagePay</Text>
      </View>

      {formError ? (
        <View className="rounded-xl border border-destructive/40 bg-destructive/10 p-3">
          <Text className="text-destructive text-sm">{formError}</Text>
        </View>
      ) : null}

      <View className="gap-2">
        <Label>Email, phone, or username</Label>
        <Input
          value={identity}
          onChangeText={onChangeIdentity}
          autoCapitalize="none"
          autoCorrect={false}
          placeholder="you@example.com"
          returnKeyType="next"
        />
        {errors.identity ? <Text className="text-destructive text-xs">{errors.identity}</Text> : null}
      </View>

      <View className="gap-2">
        <Label>Password</Label>
        <PasswordInput
          value={password}
          onChangeText={onChangePassword}
          placeholder="••••••••"
          returnKeyType="go"
          onSubmitEditing={() => void submit()}
        />
        {errors.password ? <Text className="text-destructive text-xs">{errors.password}</Text> : null}
      </View>

      <Pressable
        onPress={() => router.push("/(auth)/forgot-password" as any)}
        hitSlop={8}
        className="self-end"
      >
        <Text className="text-primary text-sm font-medium">Forgot password?</Text>
      </Pressable>

      <Button
        onPress={() => void submit()}
        disabled={loading || googleLoading}
        icon={loading ? <PagePaySpinner size={20} /> : undefined}
        className="mt-1 w-full"
      >
        {loading ? "Signing in..." : "Sign in"}
      </Button>

      <View className="flex-row items-center gap-3">
        <View className="flex-1 h-px bg-border" />
        <Text className="text-muted-foreground text-xs">or</Text>
        <View className="flex-1 h-px bg-border" />
      </View>

      <Button
        variant="outline"
        onPress={() => void startGoogleSignIn()}
        disabled={loading || googleLoading}
        icon={googleLoading ? <PagePaySpinner size={20} /> : undefined}
        className="w-full"
      >
        {googleLoading ? "Signing in..." : "Continue with Google"}
      </Button>

      {!googleClientId ? (
        <Pressable onPress={() => setShowGoogleModal(true)} hitSlop={6} className="self-center">
          <Text className="text-muted-foreground text-xs underline">Paste Google ID token manually</Text>
        </Pressable>
      ) : null}

      <View className="flex-row justify-center items-center gap-1 pt-1">
        <Text className="text-muted-foreground text-sm">New to PagePay?</Text>
        <Pressable onPress={onSwitchToRegister} hitSlop={6} disabled={!onSwitchToRegister}>
          <Text className="text-primary text-sm font-semibold">Create account</Text>
        </Pressable>
      </View>

      <Modal visible={showVerifyModal} transparent animationType="fade" onRequestClose={() => setShowVerifyModal(false)}>
        <View className="flex-1 bg-black/60 items-center justify-center p-6">
          <View className="w-full max-w-[420px] rounded-2xl bg-card border border-border p-6 gap-4">
            <Text className="text-foreground text-xl font-bold text-center">Email not verified</Text>
            <Text className="text-muted-foreground text-sm text-center leading-5">
              Please verify your email address before continuing. Check your inbox for the verification code.
            </Text>
            <View className="flex-row gap-3">
              <Button variant="outline" className="flex-1" onPress={() => setShowVerifyModal(false)}>
                Cancel
              </Button>
              <Button
                className="flex-1"
                onPress={() => {
                  setShowVerifyModal(false);
                  router.replace({
                    pathname: "/(auth)/verify-email-code",
                    params: { email: verifyEmail || identity.trim() },
                  } as never);
                }}
              >
                Verify email
              </Button>
            </View>
          </View>
        </View>
      </Modal>

      <Modal visible={showGoogleModal} transparent animationType="fade" onRequestClose={() => setShowGoogleModal(false)}>
        <View className="flex-1 bg-black/60 items-center justify-center p-6">
          <View className="w-full max-w-[420px] rounded-2xl bg-card border border-border p-6 gap-4">
            <Text className="text-foreground text-xl font-bold text-center">Continue with Google</Text>
            <Text className="text-muted-foreground text-sm text-center leading-5">
              Paste a Google ID token to sign in (POST /auth/google). Use this if automatic Google sign-in is unavailable.
            </Text>
            <Input
              value={googleIdToken}
              onChangeText={setGoogleIdToken}
              placeholder="Google ID token"
              autoCapitalize="none"
              autoCorrect={false}
              multiline
            />
            <View className="flex-row gap-3">
              <Button variant="outline" className="flex-1" onPress={() => setShowGoogleModal(false)} disabled={googleLoading}>
                Cancel
              </Button>
              <Button
                className="flex-1"
                onPress={() => void submitGoogle()}
                disabled={googleLoading || !googleIdToken.trim()}
                icon={googleLoading ? <PagePaySpinner size={20} /> : undefined}
              >
                {googleLoading ? "Signing in..." : "Sign in"}
              </Button>
            </View>
          </View>
        </View>
      </Modal>
    </View>
  );
}
