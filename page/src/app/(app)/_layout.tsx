import { Redirect, Tabs } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { PagePay } from "@/constants/theme";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";
import { useAuthStore } from "@/src/shared/store/auth";

export default function AppLayout() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const hydrated = useAuthStore((s) => s.hydrated);
  const token = useAuthStore((s) => s.token);

  if (!hydrated) return null;
  if (!token) return <Redirect href="/(auth)" />;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: tokens.mint,
        tabBarInactiveTintColor: tokens.inkMuted,
        tabBarStyle: {
          backgroundColor: tokens.card,
          borderTopColor: tokens.border,
        },
        sceneStyle: { backgroundColor: tokens.paper },
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: "Home",
          tabBarIcon: ({ color, size }) => <Ionicons name="home-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="study"
        options={{
          title: "Study",
          tabBarIcon: ({ color, size }) => <Ionicons name="book-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="wallet"
        options={{
          title: "Wallet",
          tabBarIcon: ({ color, size }) => <Ionicons name="wallet-outline" size={size} color={color} />,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, size }) => <Ionicons name="person-outline" size={size} color={color} />,
        }}
      />
    </Tabs>
  );
}