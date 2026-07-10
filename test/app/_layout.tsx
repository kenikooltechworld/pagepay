import { Stack } from 'expo-router';
import { useState } from 'react';
import { useFonts, SpaceGrotesk_500Medium, SpaceGrotesk_700Bold } from '@expo-google-fonts/space-grotesk';
import 'react-native-reanimated';

import { SplashOverlay } from '@/components/SplashOverlay';

export default function RootLayout() {
  const [splashDismissed, setSplashDismissed] = useState(false);
  
  const [fontsLoaded] = useFonts({
    SpaceGrotesk_500Medium,
    SpaceGrotesk_700Bold,
  });

  if (!fontsLoaded || !splashDismissed) {
    return <SplashOverlay onDone={() => setSplashDismissed(true)} />;
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="index" />
    </Stack>
  );
}
