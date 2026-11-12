import { useCallback, useState } from "react";
import { Image, Pressable, RefreshControl, ScrollView, Share, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import * as Clipboard from "expo-clipboard";
import * as ImagePicker from "expo-image-picker";
import { Ionicons } from "@expo/vector-icons";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { useTheme } from "@/components/ui/theme-provider";
import { PagePay } from "@/constants/theme";
import { useLogout } from "@/src/shared/api/auth";
import { apiFetch, parseApiError } from "@/src/shared/api/client";
import { updateProfile, uploadAvatarBase64 } from "@/src/shared/api/profile";
import { fetchPinStatus } from "@/src/shared/api/pin";
import { fetchCurrentUser } from "@/src/shared/lib/current-user";
import { authenticateBiometric, useBiometricCapability } from "@/src/shared/hooks/use-biometric-auth";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";
import { persistBiometricEnabled, persistLanguage, persistTheme, usePreferences, type LanguagePref, type ThemePref } from "@/src/shared/lib/preferences";

const THEMES: { value: ThemePref; label: string }[] = [
  { value: "system", label: "System" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "sepia", label: "Sepia" },
];
const LANGS: { value: LanguagePref; label: string }[] = [
  { value: "en", label: "English" },
  { value: "pcm", label: "Pidgin" },
  { value: "yo", label: "Yoruba" },
  { value: "ha", label: "Hausa" },
  { value: "ig", label: "Igbo" },
];

function SettingRow({
  icon, label, value, onPress, destructive,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value?: string;
  onPress?: () => void;
  destructive?: boolean;
}) {
  return (
    <Pressable
      onPress={onPress}
      disabled={!onPress}
      accessibilityRole={onPress ? "button" : undefined}
      className="flex-row items-center justify-between py-3"
      style={({ pressed }) => ({ opacity: pressed && onPress ? 0.7 : 1 })}
    >
      <View className="flex-row items-center gap-3 flex-1">
        <Ionicons name={icon} size={18} color={destructive ? "#dc2626" : undefined} />
        <Text className={`text-sm font-medium ${destructive ? "text-destructive" : "text-foreground"}`}>{label}</Text>
      </View>
      <View className="flex-row items-center gap-1">
        {value ? <Text className="text-sm text-muted-foreground">{value}</Text> : null}
        {onPress ? <Ionicons name="chevron-forward" size={18} color="#9CA3AF" /> : null}
      </View>
    </Pressable>
  );
}

export default function ProfileIndex() {
  const router = useRouter();
  const logout = useLogout();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const { setTheme: setUniwindTheme } = useTheme();
  const theme = usePreferences((s) => s.theme);
  const language = usePreferences((s) => s.language);
  const setThemePref = usePreferences((s) => s.setTheme);
  const setLanguagePref = usePreferences((s) => s.setLanguage);
  const [refreshing, setRefreshing] = useState(false);
  const [username, setUsername] = useState("");
  const [editingUsername, setEditingUsername] = useState(false);
  const biometricEnabled = usePreferences((s) => s.biometricEnabled);
  const setBiometricEnabled = usePreferences((s) => s.setBiometricEnabled);
  const { supported: bioSupported, enrolled: bioEnrolled } = useBiometricCapability();

  const meQuery = useQuery({ queryKey: ["auth", "me"], queryFn: fetchCurrentUser });
  const pinQuery = useQuery({ queryKey: ["pin", "status"], queryFn: fetchPinStatus });

  const user = meQuery.data;
  const display = user?.username || user?.email || user?.phone || "User";
  const initial = (display.trim()[0] || "P").toUpperCase();
  const dirty = (username.trim() || "") !== (user?.username || "");

  if (!editingUsername && user && username === "" && user.username) {
    setUsername(user.username);
  }

  const saveUsername = useMutation({
    mutationFn: (next: string) => updateProfile({ username: next.trim() ? next.trim() : null }),
    onSuccess: (u) => {
      qc.setQueryData(["auth", "me"], u);
      setEditingUsername(false);
      toast({ title: "Profile updated", variant: "success" });
    },
    onError: (e: Error) => toast({ title: "Update failed", description: e.message, variant: "destructive" }),
  });

  const avatarMutation = useMutation({
    mutationFn: async () => {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        allowsEditing: true,
        aspect: [1, 1],
        quality: 0.8,
        base64: true,
      });
      if (result.canceled || !result.assets?.[0]?.base64) throw new Error("No image selected");
      const asset = result.assets[0];
      const mime = asset.mimeType || "image/jpeg";
      const image = `data:${mime};base64,${asset.base64}`;
      return uploadAvatarBase64(image);
    },
    onSuccess: (res) => {
      qc.setQueryData(["auth", "me"], (prev: any) => (prev ? { ...prev, avatar_url: res.avatar_url ?? prev.avatar_url } : prev));
      void meQuery.refetch();
      toast({ title: "Avatar updated", variant: "success" });
    },
    onError: (e: Error) => {
      if (e.message !== "No image selected") toast({ title: "Upload failed", description: e.message, variant: "destructive" });
    },
  });

  const resendVerify = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/auth/resend-verification", { method: "POST" });
      if (!res.ok) throw new Error(await parseApiError(res, "Failed to resend verification"));
    },
    onSuccess: () => toast({ title: "Verification sent", description: "Check your email for the code.", variant: "success" }),
    onError: (e: Error) => toast({ title: "Could not resend", description: e.message, variant: "destructive" }),
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try { await Promise.all([meQuery.refetch(), pinQuery.refetch()]); } finally { setRefreshing(false); }
  }, [meQuery, pinQuery]);

  const applyTheme = (next: ThemePref) => {
    setThemePref(next);
    void persistTheme(next);
    setUniwindTheme(next === "sepia" ? "light" : next);
  };
  const applyLanguage = (next: LanguagePref) => {
    setLanguagePref(next);
    void persistLanguage(next);
    toast({ title: "Language saved", description: `${next.toUpperCase()} (translations coming soon).` });
  };

  const copyReferral = async () => {
    if (!user?.referral_code) return;
    await Clipboard.setStringAsync(user.referral_code);
    toast({ title: "Copied", description: "Referral code copied.", variant: "success" });
  };
  const shareReferral = async () => {
    if (!user?.referral_code) return;
    await Share.share({ message: `Join me on PagePay. Use my referral code: ${user.referral_code}` });
  };
  const toggleBiometric = async () => {
    if (biometricEnabled) {
      setBiometricEnabled(false);
      await persistBiometricEnabled(false);
      toast({ title: "Biometric unlock disabled", variant: "success" });
      return;
    }
    if (!bioSupported) {
      toast({ title: "Not supported", description: "Biometric hardware is not available on this device.", variant: "destructive" });
      return;
    }
    if (!bioEnrolled) {
      toast({ title: "Not enrolled", description: "Set up fingerprint/face/passcode in device settings first.", variant: "destructive" });
      return;
    }
    const ok = await authenticateBiometric("Confirm to enable biometric unlock");
    if (!ok) {
      toast({ title: "Authentication failed", description: "Biometric unlock was not enabled.", variant: "destructive" });
      return;
    }
    setBiometricEnabled(true);
    await persistBiometricEnabled(true);
    toast({ title: "Biometric unlock enabled", description: "App will lock when you leave and require biometrics to unlock.", variant: "success" });
  };
  const signOut = () => {
    logout.mutate(undefined, { onSuccess: () => { qc.clear(); router.replace("/(auth)"); } });
  };

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Profile" tokens={tokens} />
        <ScrollView
          className="flex-1"
          contentContainerClassName="px-4 py-4 gap-4 pb-10"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={tokens.mint} />}
          showsVerticalScrollIndicator={false}
        >
          {meQuery.isLoading && !user ? (
            <Card><CardContent className="gap-3 pt-2"><Skeleton className="h-16 w-16 rounded-full" /><Skeleton className="h-5 w-40" /><Skeleton className="h-4 w-56" /></CardContent></Card>
          ) : meQuery.error && !user ? (
            <Card><CardContent className="gap-3 pt-2"><Text className="text-sm text-destructive">{(meQuery.error as Error).message}</Text><Button variant="outline" onPress={() => void onRefresh()}>Retry</Button></CardContent></Card>
          ) : user ? (
            <>
              <Card>
                <CardContent className="gap-4 pt-2">
                  <View className="flex-row items-center gap-3">
                    <Pressable onPress={() => avatarMutation.mutate()} disabled={avatarMutation.isPending} accessibilityRole="button" accessibilityLabel="Change avatar">
                      <View className="h-14 w-14 items-center justify-center rounded-full border border-border overflow-hidden" style={{ backgroundColor: tokens.mintSoft }}>
                        {user.avatar_url ? (
                          <Image source={{ uri: user.avatar_url }} style={{ width: 56, height: 56 }} />
                        ) : (
                          <Text className="text-lg font-bold" style={{ color: tokens.mint }}>{initial}</Text>
                        )}
                      </View>
                      <View className="absolute -bottom-1 -right-1 h-6 w-6 rounded-full items-center justify-center" style={{ backgroundColor: tokens.mint }}>
                        {avatarMutation.isPending ? <PagePaySpinner size={12} /> : <Ionicons name="camera" size={12} color={tokens.mintText} />}
                      </View>
                    </Pressable>
                    <View className="flex-1 gap-0.5">
                      <Text className="text-lg font-semibold text-foreground" numberOfLines={1}>{display}</Text>
                      <Text className="text-xs text-muted-foreground">{user.email || user.phone || "No contact"}</Text>
                      <Text className="text-xs font-medium" style={{ color: tokens.mint }}>{user.tier} · {user.role}</Text>
                    </View>
                  </View>
                </CardContent>
              </Card>

              {user.email && user.email_verified === false ? (
                <Card className="border-amber-500/40">
                  <CardContent className="gap-2 pt-2">
                    <View className="flex-row items-center gap-2">
                      <Ionicons name="mail-outline" size={18} color={tokens.signal} />
                      <Text className="text-sm font-semibold text-foreground">Verify your email</Text>
                    </View>
                    <Text className="text-xs text-muted-foreground">Your email is not verified. Verify to unlock your account.</Text>
                    <View className="flex-row gap-2">
                      <Button size="sm" onPress={() => router.push({ pathname: "/(auth)/verify-email-code", params: { email: user.email! } })}>Verify</Button>
                      <Button size="sm" variant="outline" onPress={() => resendVerify.mutate()} disabled={resendVerify.isPending} icon={resendVerify.isPending ? <PagePaySpinner size={16} /> : undefined}>Resend</Button>
                    </View>
                  </CardContent>
                </Card>
              ) : null}

              <Card>
                <CardContent className="pt-2">
                  <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Username</Text>
                  {editingUsername ? (
                    <View className="gap-2">
                      <Input value={username} onChangeText={(v) => setUsername(v.replace(/[^a-zA-Z0-9_]/g, "").slice(0, 12).toLowerCase())} autoCapitalize="none" autoCorrect={false} placeholder="username" />
                      <Text className="text-xs text-muted-foreground">Max 12 chars. Letters, numbers, underscores.</Text>
                      <View className="flex-row gap-2">
                        <Button size="sm" onPress={() => saveUsername.mutate(username)} disabled={!dirty || saveUsername.isPending} icon={saveUsername.isPending ? <PagePaySpinner size={16} /> : undefined}>Save</Button>
                        <Button size="sm" variant="outline" onPress={() => { setEditingUsername(false); setUsername(user.username || ""); }}>Cancel</Button>
                      </View>
                    </View>
                  ) : (
                    <Pressable onPress={() => { setUsername(user.username || ""); setEditingUsername(true); }} className="flex-row items-center justify-between py-2">
                      <View>
                        <Text className="text-sm font-medium text-foreground">{user.username || "Not set"}</Text>
                        <Text className="text-xs text-muted-foreground">Tap to edit username</Text>
                      </View>
                      <Ionicons name="create-outline" size={18} color={tokens.inkMuted} />
                    </Pressable>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-2">
                  <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Referral</Text>
                  {user.referral_code ? (
                    <View className="gap-2">
                      <View className="flex-row items-center justify-between rounded-lg border border-border bg-muted/30 px-3 py-2">
                        <Text className="text-base font-bold" style={{ color: tokens.mint }}>{user.referral_code}</Text>
                        <View className="flex-row gap-3">
                          <Pressable onPress={copyReferral}><Ionicons name="copy-outline" size={18} color={tokens.ink} /></Pressable>
                          <Pressable onPress={shareReferral}><Ionicons name="share-social-outline" size={18} color={tokens.ink} /></Pressable>
                        </View>
                      </View>
                      <Text className="text-xs text-muted-foreground">Share your code to invite others.</Text>
                    </View>
                  ) : (
                    <Text className="text-sm text-muted-foreground py-1">No referral code available.</Text>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-1">
                  <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-2 mb-1">Notifications</Text>
                  <SettingRow icon="mail-unread-outline" label="Inbox" onPress={() => router.push("/(app)/profile/notification-inbox")} />
                  <Separator />
                  <SettingRow icon="options-outline" label="Notification preferences" onPress={() => router.push("/(app)/profile/notifications")} />
                  <Separator />
                  <SettingRow icon="phone-portrait-outline" label="Registered devices (FCM)" onPress={() => router.push("/(app)/profile/notification-devices")} />
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-1">
                  <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-2 mb-1">Account</Text>
                  <SettingRow icon="lock-closed-outline" label="Change password" onPress={() => router.push("/(app)/profile/change-password")} />
                  <Separator />
                  <SettingRow icon="key-outline" label="Transaction PIN" value={pinQuery.data?.has_pin ? "Set" : "Not set"} onPress={() => router.push(pinQuery.data?.has_pin ? "/(app)/profile/pin-change" : "/(app)/profile/pin-setup")} />
                  {pinQuery.data?.has_pin ? (<><Separator /><SettingRow icon="shield-checkmark-outline" label="Verify PIN" onPress={() => router.push("/(app)/profile/pin-verify")} /></>) : null}
                  <Separator />
                  <SettingRow icon="refresh-outline" label="Forgot / Reset PIN" onPress={() => router.push("/(app)/profile/pin-forgot")} />
                  <Separator />
                  <SettingRow
                    icon="finger-print-outline"
                    label="Biometric unlock"
                    value={biometricEnabled ? "On" : "Off"}
                    onPress={toggleBiometric}
                  />
                  <Separator />
                  <SettingRow icon="time-outline" label="Audit logs" onPress={() => router.push("/(app)/profile/audit-logs")} />
                  <Separator />
                  <SettingRow icon="shield-checkmark-outline" label="Account status" value={user.status} />
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-1 gap-3">
                  <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-2">Appearance</Text>
                  <View className="flex-row flex-wrap gap-2">
                    {THEMES.map((opt) => {
                      const active = theme === opt.value;
                      return (
                        <Pressable key={opt.value} onPress={() => applyTheme(opt.value)} className={`px-3 py-2 rounded-full border ${active ? "border-transparent" : "border-border"}`} style={{ backgroundColor: active ? tokens.mint : tokens.card }}>
                          <Text className="text-xs font-semibold" style={{ color: active ? tokens.mintText : tokens.ink }}>{opt.label}</Text>
                        </Pressable>
                      );
                    })}
                  </View>
                  <Separator />
                  <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Language</Text>
                  <View className="flex-row flex-wrap gap-2">
                    {LANGS.map((opt) => {
                      const active = language === opt.value;
                      return (
                        <Pressable key={opt.value} onPress={() => applyLanguage(opt.value)} className={`px-3 py-2 rounded-full border ${active ? "border-transparent" : "border-border"}`} style={{ backgroundColor: active ? tokens.mint : tokens.card }}>
                          <Text className="text-xs font-semibold" style={{ color: active ? tokens.mintText : tokens.ink }}>{opt.label}</Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-1">
                  <Text className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mt-2 mb-1">Support & legal</Text>
                  <SettingRow icon="help-circle-outline" label="Help & support" onPress={() => toast({ title: "Help", description: "Support center coming soon." })} />
                  <Separator />
                  <SettingRow icon="document-text-outline" label="Terms of service" onPress={() => router.push({ pathname: "/(auth)/legal", params: { type: "terms" } })} />
                  <Separator />
                  <SettingRow icon="shield-outline" label="Privacy policy" onPress={() => router.push({ pathname: "/(auth)/legal", params: { type: "privacy" } })} />
                  <Separator />
                  <SettingRow icon="information-circle-outline" label="About" value="PagePay" />
                </CardContent>
              </Card>

              <Card className="border-destructive/30">
                <CardContent className="pt-1">
                  <Text className="text-xs font-semibold uppercase tracking-wide text-destructive mt-2 mb-1">Danger zone</Text>
                  <SettingRow icon="trash-outline" label="Delete account" destructive onPress={() => router.push("/(app)/profile/delete-account")} />
                </CardContent>
              </Card>

              <Button variant="outline" onPress={signOut} disabled={logout.isPending} icon={logout.isPending ? <PagePaySpinner size={20} /> : undefined}>
                Sign out
              </Button>
            </>
          ) : null}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
