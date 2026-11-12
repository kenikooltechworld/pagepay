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
import { setupPin } from "@/src/shared/api/pin";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function PinSetupScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [password, setPassword] = useState("");
  const [pin, setPin] = useState("");
  const [confirm, setConfirm] = useState("");

  const mutation = useMutation({
    mutationFn: () => setupPin(password, pin),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pin", "status"] });
      qc.invalidateQueries({ queryKey: ["auth", "me"] });
      toast({ title: "PIN set", variant: "success" });
      router.back();
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const valid = password.length >= 8 && /^\d{4,6}$/.test(pin) && pin === confirm;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Set transaction PIN" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4" keyboardShouldPersistTaps="handled">
          <Card>
            <CardContent className="gap-3 pt-2">
              <Text className="text-sm text-muted-foreground">Confirm your password and choose a 4–6 digit PIN.</Text>
              <PasswordInput value={password} onChangeText={setPassword} placeholder="Account password" autoCapitalize="none" />
              <Input value={pin} onChangeText={(v) => setPin(v.replace(/\D/g, "").slice(0, 6))} placeholder="New PIN" keyboardType="number-pad" secureTextEntry maxLength={6} />
              <Input value={confirm} onChangeText={(v) => setConfirm(v.replace(/\D/g, "").slice(0, 6))} placeholder="Confirm PIN" keyboardType="number-pad" secureTextEntry maxLength={6} />
              {confirm.length > 0 && pin !== confirm ? <Text className="text-xs text-destructive">PINs do not match.</Text> : null}
              <Button onPress={() => mutation.mutate()} disabled={!valid || mutation.isPending}
                icon={mutation.isPending ? <PagePaySpinner size={20} /> : undefined}>
                Set PIN
              </Button>
            </CardContent>
          </Card>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
