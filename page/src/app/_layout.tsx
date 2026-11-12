import * as SplashScreen from "expo-splash-screen";
import { useEffect, useState } from "react";
import { View } from "react-native";
import { Slot } from "expo-router";
import { PortalHost } from "@rn-primitives/portal";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PaystackProvider } from "expo-paystack";
import Constants from "expo-constants";
import { SafeAreaProvider } from "react-native-safe-area-context"; // add
import { ThemeProvider } from "@/components/ui/theme-provider";
import { ToastProvider } from "@/components/ui/toast";
import { SplashOverlay } from "@/components/SplashOverlay";
import { BiometricGate } from "@/components/BiometricGate";
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
  const [splashDone, setSplashDone] = useState(false);
  const themePref = usePreferences((s) => s.theme);
  const bootstrapAuth = useAuthStore((s) => s.bootstrap);

  useEffect(() => {
    void bootstrapPreferences();
    void bootstrapAuth();
    bindAuthUnauthenticated();
  }, [bootstrapAuth]);

  const theme =
    themePref === "sepia" ? "light" : themePref === "system" ? "system" : themePref;

  return (
    <SafeAreaProvider>
      <QueryClientProvider client={queryClient}>
        <PaystackProvider publicKey={PAYSTACK_PUBLIC_KEY}>
          <ThemeProvider defaultTheme={theme} key={theme}>
            <ToastProvider>
              <BiometricGate>
                <View className="flex-1 bg-background">
                  <Slot />
                  {!splashDone ? <SplashOverlay onDone={() => setSplashDone(true)} /> : null}
                  <PortalHost />
                </View>
              </BiometricGate>
            </ToastProvider>
          </ThemeProvider>
        </PaystackProvider>
      </QueryClientProvider>
    </SafeAreaProvider>
  );
}