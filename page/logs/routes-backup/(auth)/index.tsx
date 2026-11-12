import { useEffect, useRef, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useRouter } from "expo-router";
import Animated, { Easing, useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";
import { Text } from "@/components/ui/text";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/components/ui/toast";
import { useThemeColors } from "@/components/ui/theme-provider";
import { useLogin, useRegister } from "@/src/shared/api/auth";

async function registerFcmToken() {
  const mod = await import("@/src/lib/firebase");
  return mod.registerFcmToken();
}

function LoginForm() {
  const router = useRouter();
  const { toast } = useToast();
  const login = useLogin();
  const [identity, setIdentity] = useState("");
  const [password, setPassword] = useState("");

  const submit = () => {
    if (!identity.trim() || !password) {
      toast({ title: "Missing fields", description: "Enter your email/username and password.", variant: "default" });
      return;
    }
    login.mutate(
      { username: identity.trim(), password },
      {
        onSuccess: async () => {
          await registerFcmToken();
          router.replace("/(app)/home" as any);
        },
        onError: (e) => toast({ title: "Login failed", description: e.message, variant: "destructive" }),
      },
    );
  };

  return (
    <View className="bg-card rounded-2xl p-6 shadow-sm gap-4 border border-border/50">
      <View className="gap-1 mb-1">
        <Text className="text-2xl font-bold text-foreground tracking-tight">Welcome back</Text>
        <Text className="text-muted-foreground text-sm">Sign in to continue to PagePay</Text>
      </View>
      <View className="gap-2">
        <Label>Email, phone, or username</Label>
        <Input value={identity} onChangeText={setIdentity} autoCapitalize="none" autoCorrect={false} placeholder="you@example.com" />
      </View>
      <View className="gap-2">
        <Label>Password</Label>
        <PasswordInput value={password} onChangeText={setPassword} placeholder="••••••••" />
      </View>
      <Button onPress={submit} disabled={login.isPending} loading={login.isPending} className="mt-2 w-full">
        {login.isPending ? "Signing in..." : "Sign in"}
      </Button>
    </View>
  );
}

function RegisterForm() {
  const router = useRouter();
  const { toast } = useToast();
  const register = useRegister();
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [referral, setReferral] = useState("");
  const [agreed, setAgreed] = useState(false);

  const submit = () => {
    if (!email.trim() || !password) {
      toast({ title: "Missing fields", description: "Email and password are required.", variant: "default" });
      return;
    }
    if (password !== confirm) {
      toast({ title: "Passwords do not match", variant: "default" });
      return;
    }
    if (!agreed) {
      toast({ title: "Accept terms", description: "Agree to the terms to continue.", variant: "default" });
      return;
    }
    register.mutate(
      {
        email: email.trim(),
        username: username.trim() ? username.trim().toLowerCase() : undefined,
        password,
        referral_code: referral.trim() || undefined,
      },
      {
        onSuccess: async () => {
          await registerFcmToken();
          router.replace({ pathname: "/(auth)/verify-email-code", params: { email: email.trim() } } as never);
        },
        onError: (e) => toast({ title: "Registration failed", description: e.message, variant: "destructive" }),
      },
    );
  };

  return (
    <View className="bg-card rounded-2xl p-6 shadow-sm gap-4 border border-border/50">
      <View className="gap-1 mb-1">
        <Text className="text-2xl font-bold text-foreground tracking-tight">Create account</Text>
        <Text className="text-muted-foreground text-sm">Join PagePay to get started</Text>
      </View>
      <View className="gap-2">
        <Label>Email</Label>
        <Input value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" placeholder="you@example.com" />
      </View>
      <View className="gap-2">
        <Label>Username (optional)</Label>
        <Input value={username} onChangeText={(v) => setUsername(v.toLowerCase().replace(/[^a-z0-9_]/g, "").slice(0, 12))} autoCapitalize="none" placeholder="username" />
      </View>
      <View className="gap-2">
        <Label>Password</Label>
        <PasswordInput value={password} onChangeText={setPassword} placeholder="Min 8 chars, upper, digit, symbol" showStrength />
      </View>
      <View className="gap-2">
        <Label>Confirm password</Label>
        <PasswordInput value={confirm} onChangeText={setConfirm} placeholder="Repeat password" />
      </View>
      <View className="gap-2">
        <Label>Referral code (optional)</Label>
        <Input value={referral} onChangeText={(v) => setReferral(v.toUpperCase().slice(0, 12))} autoCapitalize="characters" placeholder="ABC123" />
      </View>
      <Pressable className="flex-row items-center gap-3 mt-1" onPress={() => setAgreed((a) => !a)}>
        <Checkbox checked={agreed} onCheckedChange={setAgreed} />
        <Text className="text-muted-foreground flex-1 text-sm">I agree to the Terms and Privacy Policy</Text>
      </Pressable>
      <Button onPress={submit} disabled={register.isPending || !agreed} loading={register.isPending} className="mt-2 w-full">
        {register.isPending ? "Creating account..." : "Create account"}
      </Button>
    </View>
  );
}

function AuthTabSwitch({ activeTab, onTabChange }: { activeTab: "login" | "register"; onTabChange: (t: "login" | "register") => void }) {
  const { primary } = useThemeColors();
  return (
    <View className="flex-row mb-6 border-b border-border">
      <Pressable onPress={() => onTabChange("login")} className="flex-1 py-4 items-center relative">
        <Text className={`font-semibold text-base ${activeTab === "login" ? "text-foreground" : "text-muted-foreground"}`}>Sign in</Text>
        {activeTab === "login" ? <View className="absolute bottom-0 left-0 right-0 h-[3px] rounded-full" style={{ backgroundColor: primary }} /> : null}
      </Pressable>
      <Pressable onPress={() => onTabChange("register")} className="flex-1 py-4 items-center relative">
        <Text className={`font-semibold text-base ${activeTab === "register" ? "text-foreground" : "text-muted-foreground"}`}>Create account</Text>
        {activeTab === "register" ? <View className="absolute bottom-0 left-0 right-0 h-[3px] rounded-full" style={{ backgroundColor: primary }} /> : null}
      </Pressable>
    </View>
  );
}

export default function AuthIndex() {
  const [activeTab, setActiveTab] = useState<"login" | "register">("login");
  const contentOpacity = useSharedValue(1);
  const pendingTab = useRef<typeof activeTab | null>(null);
  const isMounted = useRef(true);

  useEffect(() => () => { isMounted.current = false; }, []);

  const handleTabChange = (tab: "login" | "register") => {
    if (tab === activeTab) return;
    contentOpacity.value = withTiming(0, { duration: 80, easing: Easing.out(Easing.cubic) });
    pendingTab.current = tab;
    setTimeout(() => {
      if (!isMounted.current) return;
      if (pendingTab.current) setActiveTab(pendingTab.current);
      pendingTab.current = null;
      contentOpacity.value = withTiming(1, { duration: 150, easing: Easing.out(Easing.cubic) });
    }, 80);
  };

  const contentStyle = useAnimatedStyle(() => ({ opacity: contentOpacity.value }));

  return (
    <SafeAreaView className="flex-1 bg-background">
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} className="flex-1">
        <ScrollView contentContainerClassName="flex-grow justify-center px-4 py-6" keyboardShouldPersistTaps="handled">
          <View className="mb-2 px-1">
            <Text className="text-sm font-semibold tracking-[2px] uppercase text-muted-foreground">PagePay</Text>
          </View>
          <AuthTabSwitch activeTab={activeTab} onTabChange={handleTabChange} />
          <Animated.View style={contentStyle}>
            {activeTab === "login" ? <LoginForm /> : <RegisterForm />}
          </Animated.View>
          <View className="flex-row items-center gap-3 my-6 px-1">
            <Separator className="flex-1" />
            <Text className="text-muted-foreground text-xs font-medium">OR</Text>
            <Separator className="flex-1" />
          </View>
          <Button variant="outline" className="w-full" onPress={() => {}}>
            Continue with Google
          </Button>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}