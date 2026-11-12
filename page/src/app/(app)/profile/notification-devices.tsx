import { useState } from "react";
import { RefreshControl, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { deleteFcmToken, fetchFcmTokens } from "@/src/shared/api/notifications";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

function shortToken(token: string) {
  if (token.length <= 18) return token;
  return `${token.slice(0, 10)}…${token.slice(-6)}`;
}

export default function NotificationDevicesScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [refreshing, setRefreshing] = useState(false);

  const q = useQuery({ queryKey: ["notifications", "fcm-tokens"], queryFn: fetchFcmTokens });

  const onRefresh = async () => {
    setRefreshing(true);
    try { await q.refetch(); } finally { setRefreshing(false); }
  };

  const del = useMutation({
    mutationFn: (token: string) => deleteFcmToken(token),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications", "fcm-tokens"] });
      toast({ title: "Token removed", variant: "success" });
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const items = q.data ?? [];

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Notification devices" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView
          className="flex-1"
          contentContainerClassName="px-4 py-4 gap-3 pb-8"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={tokens.mint} />}
        >
          <Text className="text-sm text-muted-foreground">Registered FCM tokens for this account.</Text>

          {q.isLoading && !q.data ? (
            <Card><CardContent className="gap-2 pt-2"><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></CardContent></Card>
          ) : q.error ? (
            <Card><CardContent className="gap-3 pt-2">
              <Text className="text-sm text-destructive">{(q.error as Error).message}</Text>
              <Button variant="outline" onPress={() => q.refetch()}>Retry</Button>
            </CardContent></Card>
          ) : items.length === 0 ? (
            <Card><CardContent className="pt-2"><Text className="text-sm text-muted-foreground">No registered devices/tokens.</Text></CardContent></Card>
          ) : (
            items.map((t) => (
              <Card key={t.id}>
                <CardContent className="gap-2 pt-2">
                  <View className="flex-row items-center justify-between gap-2">
                    <Text className="text-sm font-semibold text-foreground">{t.platform.toUpperCase()}</Text>
                    <Text className="text-xs text-muted-foreground">{t.is_active ? "Active" : "Inactive"}</Text>
                  </View>
                  <Text className="text-xs text-muted-foreground">Token: {shortToken(t.token)}</Text>
                  {t.device_id ? <Text className="text-xs text-muted-foreground">Device: {t.device_id}</Text> : null}
                  <Text className="text-xs text-muted-foreground">Registered: {new Date(t.created_at).toLocaleString()}</Text>
                  <Button
                    variant="outline"
                    size="sm"
                    onPress={() => del.mutate(t.token)}
                    disabled={del.isPending}
                    icon={del.isPending ? <PagePaySpinner size={16} /> : undefined}
                  >
                    Remove token
                  </Button>
                </CardContent>
              </Card>
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
