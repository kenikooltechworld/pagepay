import { Pressable, View } from "react-native";
import { Text } from "@/components/ui/text";
import { useThemeColors } from "@/components/ui/theme-provider";

export type AuthTab = "login" | "register";

export function AuthTabSwitch({
  activeTab,
  onTabChange,
}: {
  activeTab: AuthTab;
  onTabChange: (t: AuthTab) => void;
}) {
  const { primary } = useThemeColors();
  return (
    <View className="flex-row mb-6 border-b border-border">
      <Pressable onPress={() => onTabChange("login")} className="flex-1 py-4 items-center relative">
        <Text className={`font-semibold text-base ${activeTab === "login" ? "text-foreground" : "text-muted-foreground"}`}>
          Sign in
        </Text>
        {activeTab === "login" ? (
          <View className="absolute bottom-0 left-0 right-0 h-[3px] rounded-full" style={{ backgroundColor: primary }} />
        ) : null}
      </Pressable>
      <Pressable onPress={() => onTabChange("register")} className="flex-1 py-4 items-center relative">
        <Text className={`font-semibold text-base ${activeTab === "register" ? "text-foreground" : "text-muted-foreground"}`}>
          Create account
        </Text>
        {activeTab === "register" ? (
          <View className="absolute bottom-0 left-0 right-0 h-[3px] rounded-full" style={{ backgroundColor: primary }} />
        ) : null}
      </Pressable>
    </View>
  );
}