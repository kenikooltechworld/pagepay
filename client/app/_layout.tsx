import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useFonts, SpaceGrotesk_500Medium, SpaceGrotesk_700Bold } from '@expo-google-fonts/space-grotesk';
import 'react-native-reanimated';

import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { useAdsConfig } from '@/src/shared/hooks/use-ads-config';
import { bootstrapPreferences } from '@/src/shared/lib/preferences';
import { getToken } from '@/src/shared/lib/storage';
import { initializeAdMob } from '@/src/shared/lib/ads-native';
import { setOnUnauthenticated } from '@/src/shared/api/client';

const queryClient = new QueryClient();

import { DarkTheme, DefaultTheme, ThemeProvider } from '@react-navigation/native';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { useFonts, SpaceGrotesk_500Medium, SpaceGrotesk_700Bold } from '@expo-google-fonts/space-grotesk';
import 'react-native-reanimated';

import { useEffectiveScheme } from '@/src/shared/hooks/use-effective-scheme';
import { useAdsConfig } from '@/src/shared/hooks/use-ads-config';
import { bootstrapPreferences } from '@/src/shared/lib/preferences';
import { getToken } from '@/src/shared/lib/storage';
import { initializeAdMob } from '@/src/shared/lib/ads-native';

const queryClient = new QueryClient();

export const unstable_settings = {
  // Intentionally no anchor — the auth gate in useAuthGate controls
  // the initial route. Setting anchor here would let Expo Router
  // render the tabs layout before the auth check completes.
};

function useAuthGate() {
  const segments = useSegments();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    (async () => {
      await bootstrapPreferences();
      const token = await getToken();
      const inAuthGroup = segments[0] === '(auth)';

      if (!token && !inAuthGroup) {
        // No token and not on an auth screen → redirect to login.
        // Use replace so the back button doesn't return here.
        router.replace('/(auth)/login');
      } else if (token && inAuthGroup) {
        // Have a token and currently on an auth screen → go to tabs.
        router.replace('/(tabs)');
      }
      // else: have a token and on tabs (valid), OR no token and on auth (valid).

      // Small delay to let the scheduled navigation take effect before
      // we allow the layout to render. Prevents a flash of the wrong
      // screen when the initial route doesn't match the auth state.
      await new Promise((r) => setTimeout(r, 50));
      setIsReady(true);
    })();
  }, [segments, router]);

  // Register the global 401 → login redirect so apiFetch can
  // redirect the user when the server rejects their token.
  useEffect(() => {
    setOnUnauthenticated(() => router.replace('/(auth)/login'));
  }, [router]);

  return isReady;
}

/** Ad SDK bootstrap. Mounts the native AdMob SDK (via
 *  `react-native-google-mobile-ads`) and warms the
 *  `useAdsConfig` cache so the rest of the app can resolve
 *  unit IDs without a render-blocking fetch.
 *
 *  The init is fire-and-forget: a failed native init just
 *  means ads are disabled and the MockAdModal takes over.
 *  The config fetch is non-blocking too — the hooks return
 *  `data = undefined` until the request resolves and the
 *  ad components fall back to the placeholder.
 *
 *  This hook is mounted at the root so the SDK is warm by
 *  the time the catalog renders its first page. The AdMob
 *  SDK's `initialize()` is idempotent so re-mounts on
 *  theme / auth changes are safe. */
function AdsBootstrapComponent() {
  useAdsConfig();
  // Kick off the native init. We don't await — the layout
  // must render immediately and the SDK is happy to finish
  // initializing in the background.
  useEffect(() => {
    initializeAdMob().catch(() => undefined);
  }, []);
  return null;
}

export default function RootLayout() {
  const colorScheme = useEffectiveScheme();
  const isReady = useAuthGate();
  const [fontsLoaded] = useFonts({
    SpaceGrotesk_500Medium,
    SpaceGrotesk_700Bold,
  });

  if (!isReady || !fontsLoaded) {
    return null;
  }

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider value={colorScheme === 'dark' ? DarkTheme : DefaultTheme}>
        <AdsBootstrapComponent />
        <Stack>
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="reader/[id]" options={{ headerShown: false }} />
        <Stack.Screen name="book/[id]" options={{ headerShown: false, title: 'Book' }} />
        <Stack.Screen name="study/chat/[id]" options={{ headerShown: false, title: 'Study Chat' }} />
        <Stack.Screen name="tasks/[id]" options={{ headerShown: false, title: 'Task Detail' }} />
        <Stack.Screen name="tasks/[id]/complete" options={{ headerShown: false, title: 'Submit Proof' }} />
        <Stack.Screen name="tasks/profile" options={{ headerShown: false, title: 'Worker Profile' }} />
        <Stack.Screen name="tasks/history" options={{ headerShown: false, title: 'Submission History' }} />
        <Stack.Screen name="sponsor/register" options={{ headerShown: false, title: 'Become a Sponsor' }} />
        <Stack.Screen name="sponsor/kyc" options={{ headerShown: false, title: 'KYC Verification' }} />
        <Stack.Screen name="sponsor/dashboard" options={{ headerShown: false, title: 'Sponsor Dashboard' }} />
        <Stack.Screen name="sponsor/tasks/create" options={{ headerShown: false, title: 'Create Task' }} />
        <Stack.Screen name="sponsor/tasks/[id]" options={{ headerShown: false, title: 'Task Submissions' }} />
        <Stack.Screen name="forgot-password" options={{ headerShown: false, title: 'Reset Password' }} />
        <Stack.Screen name="reset-password" options={{ headerShown: false, title: 'New Password' }} />
        <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
        </Stack>
        <StatusBar style="auto" />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
