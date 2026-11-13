import { useState } from "react";
import { Pressable, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { changePin } from "@/src/shared/api/pin";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function PinChangeScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const mutation = useMutation({
    mutationFn: () => changePin(current, next),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pin", "status"] });
      toast({ title: "PIN changed", variant: "success" });
      router.back();
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const valid = /^\d{4,6}$/.test(current) && /^\d{4,6}$/.test(next) && next === confirm;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Change PIN" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4" keyboardShouldPersistTaps="handled">
          <Card>
            <CardContent className="gap-3 pt-2">
              <Text className="text-sm text-muted-foreground">Enter your current PIN and a new 4–6 digit PIN.</Text>
              <Input value={current} onChangeText={(v) => setCurrent(v.replace(/\D/g, "").slice(0, 6))} placeholder="Current PIN" keyboardType="number-pad" secureTextEntry maxLength={6} />
              <Input value={next} onChangeText={(v) => setNext(v.replace(/\D/g, "").slice(0, 6))} placeholder="New PIN" keyboardType="number-pad" secureTextEntry maxLength={6} />
              <Input value={confirm} onChangeText={(v) => setConfirm(v.replace(/\D/g, "").slice(0, 6))} placeholder="Confirm new PIN" keyboardType="number-pad" secureTextEntry maxLength={6} />
              {confirm.length > 0 && next !== confirm ? <Text className="text-xs text-destructive">PINs do not match.</Text> : null}
              <Button onPress={() => mutation.mutate()} disabled={!valid || mutation.isPending}
                icon={mutation.isPending ? <PagePaySpinner size={20} /> : undefined}>
                Update PIN
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
