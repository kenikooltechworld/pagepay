import { View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { ScrollView } from "react-native";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { PagePay } from "@/constants/theme";
import { fetchAuditLogs } from "@/src/shared/api/profile";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function AuditLogsScreen() {
  const router = useRouter();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;

  const q = useQuery({
    queryKey: ["auth", "audit-logs"],
    queryFn: () => fetchAuditLogs(50, 0),
  });

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Audit logs" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-3 pb-8">
          {q.isLoading ? (
            <Card><CardContent className="gap-2 pt-2"><Skeleton className="h-5 w-40" /><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></CardContent></Card>
          ) : q.error ? (
            <Card><CardContent className="gap-3 pt-2">
              <Text className="text-sm text-destructive">{(q.error as Error).message}</Text>
              <Button variant="outline" onPress={() => q.refetch()}>Retry</Button>
            </CardContent></Card>
          ) : (
            <>
              <Text className="text-xs text-muted-foreground">
                {q.data?.total ?? 0} total • showing up to {q.data?.logs.length ?? 0}
              </Text>
              {(q.data?.logs ?? []).length === 0 ? (
                <Card><CardContent className="pt-2"><Text className="text-sm text-muted-foreground">No audit activity yet.</Text></CardContent></Card>
              ) : (
                (q.data?.logs ?? []).map((log) => (
                  <Card key={log.id}>
                    <CardContent className="gap-1 pt-2">
                      <View className="flex-row items-center justify-between gap-2">
                        <Text className="text-sm font-semibold text-foreground" numberOfLines={1}>{log.action}</Text>
                        <Text className="text-xs text-muted-foreground">{new Date(log.created_at).toLocaleString()}</Text>
                      </View>
                      {log.ip_address ? <Text className="text-xs text-muted-foreground">IP: {log.ip_address}</Text> : null}
                      {log.user_agent ? <Text className="text-xs text-muted-foreground" numberOfLines={2}>UA: {log.user_agent}</Text> : null}
                      {log.extra_data ? <Text className="text-xs text-muted-foreground" numberOfLines={3}>Data: {log.extra_data}</Text> : null}
                    </CardContent>
                  </Card>
                ))
              )}
            </>
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
