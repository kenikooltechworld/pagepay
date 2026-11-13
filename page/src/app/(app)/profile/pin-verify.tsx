import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useMutation } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { verifyPin } from "@/src/shared/api/pin";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function PinVerifyScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [pin, setPin] = useState("");

  const mutation = useMutation({
    mutationFn: () => verifyPin(pin),
    onSuccess: () => {
      toast({ title: "PIN verified", description: "Your transaction PIN is correct.", variant: "success" });
      setPin("");
    },
    onError: (e: Error) => toast({ title: "Verification failed", description: e.message, variant: "destructive" }),
  });

  const valid = /^\d{4,6}$/.test(pin);

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Verify PIN" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4" keyboardShouldPersistTaps="handled">
          <Card>
            <CardContent className="gap-3 pt-2">
              <Text className="text-sm text-muted-foreground">Enter your transaction PIN to verify it.</Text>
              <Input
                value={pin}
                onChangeText={(v) => setPin(v.replace(/\D/g, "").slice(0, 6))}
                placeholder="4–6 digit PIN"
                keyboardType="number-pad"
                secureTextEntry
                maxLength={6}
              />
              <Button
                onPress={() => mutation.mutate()}
                disabled={!valid || mutation.isPending}
                icon={mutation.isPending ? <PagePaySpinner size={20} /> : undefined}
              >
                Verify PIN
              </Button>
              <Pressable onPress={() => router.push("/(app)/profile/pin-forgot")} className="self-center pt-1">
                <Text className="text-sm text-primary font-medium">Forgot PIN?</Text>
              </Pressable>
            </CardContent>
          </Card>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
