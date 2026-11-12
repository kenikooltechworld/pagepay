import { useEffect, useState } from "react";
import { KeyboardAvoidingView, Platform, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useMutation } from "@tanstack/react-query";
import { Text } from "@/components/ui/text";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/toast";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { apiFetch, authJson, parseApiError } from "@/src/shared/api/client";

export default function VerifyEmailCode() {
  const router = useRouter();
  const { toast } = useToast();
  const params = useLocalSearchParams<{ email?: string; token?: string }>();
  const emailValue = typeof params.email === "string" ? params.email : Array.isArray(params.email) ? params.email[0] : "";
  const tokenValue = typeof params.token === "string" ? params.token : Array.isArray(params.token) ? params.token[0] : "";
  const [code, setCode] = useState("");

  // Backend: POST /api/v1/auth/verify-email { email, token } (link/token flow)
  const verifyByToken = useMutation({
    mutationFn: async () => {
      if (!emailValue || !tokenValue) throw new Error("Verification link is invalid.");
      return authJson<{ ok: boolean; message?: string }>("/auth/verify-email", {
        email: emailValue,
        token: tokenValue,
      });
    },
    onSuccess: (data) => {
      toast({ title: "Email verified", description: data.message, variant: "success" });
      router.replace("/(app)/home" as any);
    },
    onError: (e) => toast({ title: "Verification failed", description: e.message, variant: "destructive" }),
  });

  useEffect(() => {
    if (emailValue && tokenValue) verifyByToken.mutate();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [emailValue, tokenValue]);

  // Backend: POST /api/v1/auth/verify-email-code { email, code }
  const verify = useMutation({
    mutationFn: async () => {
      if (!emailValue) throw new Error("Email is required for verification.");
      return authJson<{ ok: boolean; message?: string }>("/auth/verify-email-code", {
        email: emailValue,
        code: code.trim(),
      });
    },
    onSuccess: (data) => {
      toast({ title: "Email verified", description: data.message, variant: "success" });
      router.replace("/(app)/home" as any);
    },
    onError: (e) => toast({ title: "Verification failed", description: e.message, variant: "destructive" }),
  });

  // Backend: POST /api/v1/auth/resend-verification (Bearer)
  const resend = useMutation({
    mutationFn: async () => {
      const res = await apiFetch("/auth/resend-verification", { method: "POST" });
      if (!res.ok) throw new Error(await parseApiError(res, "Could not resend code"));
      return (await res.json().catch(() => ({}))) as { ok?: boolean; message?: string };
    },
    onSuccess: (data) => toast({ title: "Code sent", description: data.message || "Check your inbox.", variant: "success" }),
    onError: (e) => toast({ title: "Could not resend", description: e.message, variant: "destructive" }),
  });

  const busy = verify.isPending || resend.isPending || verifyByToken.isPending;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : "height"} className="flex-1 justify-center bg-background p-6">
          <View className="gap-4">
            <Text className="text-foreground text-2xl font-bold">Verify your email</Text>
            {tokenValue ? (
              <View className="gap-3 items-center py-4">
                {verifyByToken.isPending ? <PagePaySpinner size={28} /> : null}
                <Text className="text-muted-foreground text-center">
                  {verifyByToken.isPending ? "Verifying your email link..." : "Enter the 6-digit code if needed."}
                </Text>
              </View>
            ) : null}
            <Text className="text-muted-foreground">
              Enter the 6-digit code sent to {emailValue || "your email"}.
            </Text>
            <View className="gap-2">
              <Label>Verification code</Label>
              <Input value={code} onChangeText={(v) => setCode(v.replace(/\D/g, "").slice(0, 6))} keyboardType="number-pad" placeholder="123456" maxLength={6} autoComplete="one-time-code" />
            </View>
            <Button onPress={() => verify.mutate()} disabled={busy || code.length !== 6 || !emailValue} icon={verify.isPending ? <PagePaySpinner size={20} /> : undefined}>
              {verify.isPending ? "Verifying..." : "Verify email"}
            </Button>
            <Button variant="outline" onPress={() => resend.mutate()} disabled={busy} icon={resend.isPending ? <PagePaySpinner size={20} /> : undefined}>
              {resend.isPending ? "Sending..." : "Resend code"}
            </Button>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}
