import { Stack } from "expo-router";
import { useThemeColors } from "@/components/ui/theme-provider";

export default function AuthLayout() {
  const { background } = useThemeColors();
  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: background } }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="verify-email-code" />
    </Stack>
  );
}
