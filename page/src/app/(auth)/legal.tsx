import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Text } from "@/components/ui/text";
import { Button } from "@/components/ui/button";

const CONTENT: Record<string, { title: string; body: string }> = {
  terms: {
    title: "Terms of Service",
    body:
      "By using PagePay, you agree to use the service lawfully and to provide accurate account information.\n\n" +
      "You are responsible for maintaining the confidentiality of your login credentials and for activity under your account.\n\n" +
      "PagePay may update these terms as the product evolves. Continued use of the service after updates means you accept the revised terms.\n\n" +
      "For questions about these terms, contact PagePay support through the official support channels.",
  },
  privacy: {
    title: "Privacy Policy",
    body:
      "PagePay collects information you provide (such as account identifiers) and technical data needed to operate the app securely (such as device/session signals).\n\n" +
      "We use this information to authenticate you, protect accounts, provide features, and improve the service.\n\n" +
      "We do not sell your personal information. Data handling may change as features are added; we will update this policy accordingly.\n\n" +
      "For privacy questions, contact PagePay support through the official support channels.",
  },
};

export default function LegalScreen() {
  const router = useRouter();
  const { type } = useLocalSearchParams<{ type?: string }>();
  const key = type === "privacy" ? "privacy" : "terms";
  const doc = CONTENT[key];

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <ScrollView contentContainerClassName="p-6 gap-4">
          <Text className="text-foreground text-2xl font-bold">{doc.title}</Text>
          <Text className="text-muted-foreground leading-6">{doc.body}</Text>
          <Button variant="outline" onPress={() => router.back()}>
            Back
          </Button>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
