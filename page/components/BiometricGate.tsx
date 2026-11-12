import { useEffect, useRef, useState } from "react";
import { AppState, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Ionicons } from "@expo/vector-icons";
import { Button } from "@/components/ui/button";
import { Text } from "@/components/ui/text";
import { PagePay } from "@/constants/theme";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";
import { useAuthStore } from "@/src/shared/store/auth";
import { usePreferences } from "@/src/shared/lib/preferences";
import { authenticateBiometric } from "@/src/shared/hooks/use-biometric-auth";

export function BiometricGate({ children }: { children: React.ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const hydrated = useAuthStore((s) => s.hydrated);
  const prefsHydrated = usePreferences((s) => s.hydrated);
  const biometricEnabled = usePreferences((s) => s.biometricEnabled);
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [unlocked, setUnlocked] = useState(false);
  const [prompting, setPrompting] = useState(false);
  const appState = useRef(AppState.currentState);

  const locked = hydrated && prefsHydrated && !!token && biometricEnabled && !unlocked;

  useEffect(() => {
    if (!token || !biometricEnabled) {
      setUnlocked(false);
    }
  }, [token, biometricEnabled]);

  useEffect(() => {
    const sub = AppState.addEventListener("change", (next) => {
      if (appState.current.match(/active/) && next.match(/inactive|background/) && token && biometricEnabled) {
        setUnlocked(false);
      }
      appState.current = next;
    });
    return () => sub.remove();
  }, [token, biometricEnabled]);

  const unlock = async () => {
    if (prompting) return;
    setPrompting(true);
    try {
      const ok = await authenticateBiometric("Unlock PagePay");
      if (ok) setUnlocked(true);
    } finally {
      setPrompting(false);
    }
  };

  useEffect(() => {
    if (locked) void unlock();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [locked]);

  if (locked) {
    return (
      <SafeAreaView style={{ flex: 1, backgroundColor: tokens.paper }} edges={["top", "bottom"]}>
        <View className="flex-1 items-center justify-center px-8 gap-4">
          <View className="h-16 w-16 items-center justify-center rounded-full border border-border" style={{ backgroundColor: tokens.mintSoft }}>
            <Ionicons name="finger-print-outline" size={28} color={tokens.mint} />
          </View>
          <Text className="text-xl font-semibold text-foreground text-center">App locked</Text>
          <Text className="text-sm text-muted-foreground text-center">
            Use biometrics or your device passcode to unlock.
          </Text>
          <Button onPress={() => void unlock()} disabled={prompting} className="min-w-[180px]">
            {prompting ? "Unlocking..." : "Unlock"}
          </Button>
        </View>
      </SafeAreaView>
    );
  }

  return <>{children}</>;
}
