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
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { requestPinReset, resetPin, verifyPinResetOtp } from "@/src/shared/api/pin";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

type Step = 1 | 2 | 3;

export default function PinForgotScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [step, setStep] = useState<Step>(1);
  const [otp, setOtp] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [pin, setPin] = useState("");
  const [confirm, setConfirm] = useState("");

  const request = useMutation({
    mutationFn: requestPinReset,
    onSuccess: (data) => {
      toast({ title: "Code sent", description: data.message, variant: "success" });
      setStep(2);
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const verify = useMutation({
    mutationFn: () => verifyPinResetOtp(otp),
    onSuccess: (data) => {
      if (!data.reset_token) {
        toast({ title: "Failed", description: "Could not verify code.", variant: "destructive" });
        return;
      }
      setResetToken(data.reset_token);
      toast({ title: "Code verified", variant: "success" });
      setStep(3);
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const reset = useMutation({
    mutationFn: () => resetPin(resetToken, pin),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pin", "status"] });
      qc.invalidateQueries({ queryKey: ["auth", "me"] });
      toast({ title: "PIN reset", variant: "success" });
      router.back();
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const canVerify = /^\d{6}$/.test(otp);
  const canReset = !!resetToken && /^\d{4,6}$/.test(pin) && pin === confirm;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Reset PIN" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4" keyboardShouldPersistTaps="handled">
          <Card>
            <CardContent className="gap-3 pt-2">
              {step === 1 ? (
                <>
                  <Text className="text-sm text-muted-foreground">
                    We will send a 6-digit code to your account email or phone to reset your transaction PIN.
                  </Text>
                  <Button
                    onPress={() => request.mutate()}
                    disabled={request.isPending}
                    icon={request.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    Send reset code
                  </Button>
                </>
              ) : step === 2 ? (
                <>
                  <Text className="text-sm text-muted-foreground">Enter the 6-digit code sent to your account.</Text>
                  <Input
                    value={otp}
                    onChangeText={(v) => setOtp(v.replace(/\D/g, "").slice(0, 6))}
                    placeholder="123456"
                    keyboardType="number-pad"
                    maxLength={6}
                    autoComplete="one-time-code"
                  />
                  <Button
                    onPress={() => verify.mutate()}
                    disabled={!canVerify || verify.isPending}
                    icon={verify.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    Verify code
                  </Button>
                  <Button variant="outline" onPress={() => request.mutate()} disabled={request.isPending}>
                    Resend code
                  </Button>
                </>
              ) : (
                <>
                  <Text className="text-sm text-muted-foreground">Set a new 4–6 digit transaction PIN.</Text>
                  <Input
                    value={pin}
                    onChangeText={(v) => setPin(v.replace(/\D/g, "").slice(0, 6))}
                    placeholder="New PIN"
                    keyboardType="number-pad"
                    secureTextEntry
                    maxLength={6}
                  />
                  <Input
                    value={confirm}
                    onChangeText={(v) => setConfirm(v.replace(/\D/g, "").slice(0, 6))}
                    placeholder="Confirm new PIN"
                    keyboardType="number-pad"
                    secureTextEntry
                    maxLength={6}
                  />
                  {confirm.length > 0 && pin !== confirm ? (
                    <Text className="text-xs text-destructive">PINs do not match.</Text>
                  ) : null}
                  <Button
                    onPress={() => reset.mutate()}
                    disabled={!canReset || reset.isPending}
                    icon={reset.isPending ? <PagePaySpinner size={20} /> : undefined}
                  >
                    Reset PIN
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
