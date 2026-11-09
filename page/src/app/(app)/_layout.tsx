import { Stack } from "expo-router";
import { useThemeColors } from "@/components/ui/theme-provider";

export default function AppLayout() {
  const { background } = useThemeColors();
  return <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: background } }} />;
}
