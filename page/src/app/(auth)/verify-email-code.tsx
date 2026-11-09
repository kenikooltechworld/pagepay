import { useState } from "react";
import { KeyboardAvoidingView, Platform, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useMutation } from "@tanstack/react-query";
import { Text } from "@/components/ui/text";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { authJson } from "@/src/shared/api/client";

export default function VerifyEmailCode() {
  const router = useRouter();
  const { toast } = useToast();
  const { email } = useLocalSearchParams<{ email?: string }>();
  const [code, setCode] = useState("");

  const verify = useMutation({
    mutationFn: () => authJson<{ ok: boolean }>("/auth/verify-email-code", { email, code: code.trim() }),
    onSuccess: () => {
      toast({ title: "Email verified", variant: "success" });
      router.replace("/(app)/home");
    },
    onError: (e) => toast({ title: "Verification failed", description: e.message, variant: "destructive" }),
  });

  return (
    <SafeAreaView className="flex-1 bg-background">
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} className="flex-1 justify-center bg-background p-6">
        <View className="gap-4">
          <Text className="text-foreground text-2xl font-bold">Verify your email</Text>
          <Text className="text-muted-foreground">
            Enter the 6-digit code sent to {email || "your email"}.
          </Text>
          <View className="gap-2">
            <Label>Verification code</Label>
            <Input
              value={code}
              onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, 6))}
              keyboardType="number-pad"
              placeholder="123456"
              maxLength={6}
            />
          </View>
          <Button onPress={() => verify.mutate()} disabled={verify.isPending || code.length !== 6}>
            {verify.isPending ? "Verifying..." : "Verify email"}
          </Button>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
