import { Redirect, Stack } from "expo-router";
import { useThemeColors } from "@/components/ui/theme-provider";
import { useAuthStore } from "@/src/shared/store/auth";

export default function AuthLayout() {
  const { background } = useThemeColors();
  const hydrated = useAuthStore((s) => s.hydrated);
  const token = useAuthStore((s) => s.token);

  if (!hydrated) return null;
  if (token) return <Redirect href="/(app)/home" />;

  return (
    <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: background } }}>
      <Stack.Screen name="index" />
      <Stack.Screen name="verify-email-code" />
      <Stack.Screen name="forgot-password" />
      <Stack.Screen name="legal" />
    </Stack>
  );
}
