import { useState } from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { deleteAccount } from "@/src/shared/api/account";
import { useAuthStore } from "@/src/shared/store/auth";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function DeleteAccountScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const logout = useAuthStore((s) => s.logout);
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  const mutation = useMutation({
    mutationFn: () => deleteAccount(password),
    onSuccess: async () => {
      qc.clear();
      await logout();
      toast({ title: "Account deleted", variant: "success" });
      router.replace("/(auth)");
    },
    onError: (e: Error) => toast({ title: "Delete failed", description: e.message, variant: "destructive" }),
  });

  const valid = password.length >= 6 && confirm === "DELETE";

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Delete account" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4" keyboardShouldPersistTaps="handled">
          <Card className="border-destructive/30">
            <CardContent className="gap-3 pt-2">
              <Text className="text-sm text-foreground">This permanently deletes your account. This action cannot be undone.</Text>
              <PasswordInput value={password} onChangeText={setPassword} placeholder="Current password" autoCapitalize="none" />
              <Input value={confirm} onChangeText={setConfirm} placeholder='Type "DELETE" to confirm' autoCapitalize="characters" autoCorrect={false} />
              <Button variant="destructive" onPress={() => mutation.mutate()} disabled={!valid || mutation.isPending}
                icon={mutation.isPending ? <PagePaySpinner size={20} /> : undefined}>
                Delete my account
              </Button>
            </CardContent>
          </Card>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
