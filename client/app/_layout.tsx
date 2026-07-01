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
  anchor: '(tabs)',
};

function useAuthGate() {
  const segments = useSegments();
  const router = useRouter();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    (async () => {
      // Hydrate user prefs before we render — avoids the dark/light
      // flip a frame after first paint.
      await bootstrapPreferences();
      const token = await getToken();
      const inAuthGroup = segments[0] === '(auth)';
      const inTabsGroup = segments[0] === '(tabs)';

      if (!token && !inAuthGroup) {
        router.replace('/(auth)/login');
      } else if (token && inAuthGroup) {
        router.replace('/(tabs)');
      }
      setIsReady(true);
    })();
  }, [segments, router]);

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
          <Stack.Screen name="modal" options={{ presentation: 'modal', title: 'Modal' }} />
        </Stack>
        <StatusBar style="auto" />
      </ThemeProvider>
    </QueryClientProvider>
  );
}
