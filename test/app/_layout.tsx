import { Stack, useRouter, useSegments } from 'expo-router';
import { useEffect, useState } from 'react';
import { useFonts, SpaceGrotesk_500Medium, SpaceGrotesk_700Bold } from '@expo-google-fonts/space-grotesk';
import 'react-native-reanimated';

import { SplashOverlay } from '@/components/SplashOverlay';
import { bootstrapPreferences, usePreferences } from '@/src/shared/lib/preferences';

export default function RootLayout() {
  const segments = useSegments();
  const router = useRouter();
  const [splashDismissed, setSplashDismissed] = useState(false);
  const [isReady, setIsReady] = useState(false);
  const onboardingCompleted = usePreferences((s) => s.onboardingCompleted);
  const hydrated = usePreferences((s) => s.hydrated);
  
  const [fontsLoaded] = useFonts({
    SpaceGrotesk_500Medium,
    SpaceGrotesk_700Bold,
  });

  // Boot preferences once
  useEffect(() => {
    bootstrapPreferences();
  }, []);

  // Route based on onboarding status
  useEffect(() => {
    if (!hydrated) return;
    
    (async () => {
      const inOnboardingGroup = segments[0] === '(onboarding)';
      
      if (!onboardingCompleted && !inOnboardingGroup) {
        // First time user → show onboarding
        router.replace('/(onboarding)');
      } else if (onboardingCompleted && inOnboardingGroup) {
        // Already completed → go to home
        router.replace('/');
      }
      
      await new Promise((r) => setTimeout(r, 50));
      setIsReady(true);
    })();
  }, [hydrated, segments, router, onboardingCompleted]);

  if (!fontsLoaded || !isReady) {
    if (!splashDismissed) {
      return <SplashOverlay onDone={() => setSplashDismissed(true)} />;
    }
    return null;
  }

  return (
    <Stack>
      <Stack.Screen name="(onboarding)" options={{ headerShown: false }} />
      <Stack.Screen name="index" options={{ headerShown: false }} />
    </Stack>
  );
}
