import * as SplashScreen from "expo-splash-screen";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { Slot } from "expo-router";
import { PortalHost } from "@rn-primitives/portal";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PaystackProvider } from "expo-paystack";
import Constants from "expo-constants";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { ToastProvider } from "@/components/ui/toast";
import { SplashOverlay } from "@/components/SplashOverlay";
import { bootstrapPreferences, usePreferences } from "@/src/shared/lib/preferences";
import { bindAuthUnauthenticated } from "@/src/shared/api/auth";
import { useAuthStore } from "@/src/shared/store/auth";
import "@/global.css";

SplashScreen.preventAutoHideAsync();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 0, refetchOnWindowFocus: false },
    mutations: { retry: 0 },
  },
});

const PAYSTACK_PUBLIC_KEY = __DEV__
  ? process.env.EXPO_PUBLIC_PAYSTACK_PUBLIC_KEY_TEST ||
    process.env.EXPO_PUBLIC_PAYSTACK_PUBLIC_KEY
  : Constants.expoConfig?.extra?.paystackPublicKey ||
    process.env.EXPO_PUBLIC_PAYSTACK_PUBLIC_KEY;

export default function RootLayout() {
  const [splashAnimDone, setSplashAnimDone] = useState(false);
  const themePref = usePreferences((s) => s.theme);
  const bootstrapAuth = useAuthStore((s) => s.bootstrap);
  const authHydrated = useAuthStore((s) => s.hydrated);

  useEffect(() => {
    void bootstrapPreferences();
    void bootstrapAuth();
    bindAuthUnauthenticated();
  }, [bootstrapAuth]);

  const theme =
    themePref === "sepia" ? "light" : themePref === "system" ? "system" : themePref;
  const showSplash = !splashAnimDone || !authHydrated;
  const ready = splashAnimDone && authHydrated;

  return (
    <QueryClientProvider client={queryClient}>
      <PaystackProvider publicKey={PAYSTACK_PUBLIC_KEY}>
        <ThemeProvider defaultTheme={theme} key={theme}>
          <ToastProvider>
            <View className="flex-1">
              {ready ? <Slot /> : null}
              {showSplash ? (
                <SplashOverlay onDone={() => setSplashAnimDone(true)} />
              ) : null}
              <PortalHost />
            </View>
          </ToastProvider>
        </ThemeProvider>
      </PaystackProvider>
    </QueryClientProvider>
  );
}
