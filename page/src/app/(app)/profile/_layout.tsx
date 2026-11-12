import { Stack } from "expo-router";
import { PagePay } from "@/constants/theme";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function ProfileLayout() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: tokens.paper },
      }}
    />
  );
}
