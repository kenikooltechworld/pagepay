import { useState } from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useMutation } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/ui/password-input";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { changePassword } from "@/src/shared/api/account";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function ChangePasswordScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const mutation = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      toast({ title: "Password changed", variant: "success" });
      router.back();
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const valid = current.length >= 8 && next.length >= 8 && next === confirm;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Change password" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4" keyboardShouldPersistTaps="handled">
          <Card>
            <CardContent className="gap-3 pt-2">
              <Text className="text-sm text-muted-foreground">Enter your current password and a new password.</Text>
              <PasswordInput value={current} onChangeText={setCurrent} placeholder="Current password" autoCapitalize="none" />
              <PasswordInput value={next} onChangeText={setNext} placeholder="New password" autoCapitalize="none" />
              <PasswordInput value={confirm} onChangeText={setConfirm} placeholder="Confirm new password" autoCapitalize="none" />
              {confirm.length > 0 && next !== confirm ? (
                <Text className="text-xs text-destructive">Passwords do not match.</Text>
              ) : null}
              <Button onPress={() => mutation.mutate()} disabled={!valid || mutation.isPending}
                icon={mutation.isPending ? <PagePaySpinner size={20} /> : undefined}>
                Update password
              </Button>
            </CardContent>
          </Card>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
