import * as Splash from "expo-splash-screen";
import { useState } from "react";
import { View, StyleSheet } from "react-native";
import { SplashOverlay } from "@/components/SplashOverlay";

Splash.preventAutoHideAsync();

export default function RootLayout() {
  const [splashDismissed, setSplashDismissed] = useState(false);

  return (
    <View style={styles.container}>
      {!splashDismissed && (
        <SplashOverlay onDone={() => setSplashDismissed(true)} />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#000",
  },
});
