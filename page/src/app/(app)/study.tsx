import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { PageHeader } from "@/components/PageHeader";
import { Text } from "@/components/ui/text";
import { PagePay } from "@/constants/theme";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function StudyScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Study" tokens={tokens} />
        <View className="flex-1 items-center justify-center px-6">
          <Text className="text-base text-muted-foreground text-center">
            Study materials and tools coming soon.
          </Text>
        </View>
      </SafeAreaView>
    </View>
  );
}
