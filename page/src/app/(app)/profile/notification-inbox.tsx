import { useState } from "react";
import { Pressable, RefreshControl, ScrollView, View } from "react-native";
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
import {
  fetchNotification,
  fetchNotifications,
  markAllNotificationsRead,
  markNotificationRead,
  type NotificationItem,
} from "@/src/shared/api/notifications";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

export default function NotificationsInboxScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [refreshing, setRefreshing] = useState(false);
  const [selected, setSelected] = useState<NotificationItem | null>(null);

  const listQuery = useQuery({
    queryKey: ["notifications", "inbox"],
    queryFn: () => fetchNotifications(50, 0),
  });

  const onRefresh = async () => {
    setRefreshing(true);
    try {
      await listQuery.refetch();
    } finally {
      setRefreshing(false);
    }
  };

  const openMutation = useMutation({
    mutationFn: async (item: NotificationItem) => {
      const detail = await fetchNotification(item.id);
      if (!detail.read) await markNotificationRead(item.id);
      return detail;
    },
    onSuccess: (detail) => {
      setSelected(detail);
      qc.invalidateQueries({ queryKey: ["notifications", "inbox"] });
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const markAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["notifications", "inbox"] });
      toast({ title: "All marked as read", variant: "success" });
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  const items = listQuery.data?.notifications ?? [];
  const unread = listQuery.data?.unread_count ?? 0;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Inbox" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView
          className="flex-1"
          contentContainerClassName="px-4 py-4 gap-3 pb-8"
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={tokens.mint} />}
        >
          <View className="flex-row items-center justify-between">
            <Text className="text-sm text-muted-foreground">{unread} unread</Text>
            <Button
              size="sm"
              variant="outline"
              onPress={() => markAllMutation.mutate()}
              disabled={markAllMutation.isPending || unread === 0}
              icon={markAllMutation.isPending ? <PagePaySpinner size={16} /> : undefined}
            >
              Mark all read
            </Button>
          </View>

          {selected ? (
            <Card>
              <CardContent className="gap-2 pt-2">
                <View className="flex-row items-center justify-between">
                  <Text className="text-base font-semibold text-foreground flex-1" numberOfLines={2}>{selected.title}</Text>
                  <Button size="sm" variant="ghost" onPress={() => setSelected(null)}>Close</Button>
                </View>
                <Text className="text-xs text-muted-foreground">
                  {selected.category ? `${selected.category} · ` : ""}{new Date(selected.created_at).toLocaleString()}
                </Text>
                <Text className="text-sm text-foreground">{selected.body}</Text>
                {selected.data ? (
                  <Text className="text-xs text-muted-foreground">{JSON.stringify(selected.data, null, 2)}</Text>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {listQuery.isLoading && !listQuery.data ? (
            <Card><CardContent className="gap-2 pt-2"><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /><Skeleton className="h-14 w-full" /></CardContent></Card>
          ) : listQuery.error ? (
            <Card><CardContent className="gap-3 pt-2">
              <Text className="text-sm text-destructive">{(listQuery.error as Error).message}</Text>
              <Button variant="outline" onPress={() => listQuery.refetch()}>Retry</Button>
            </CardContent></Card>
          ) : items.length === 0 ? (
            <Card><CardContent className="pt-2"><Text className="text-sm text-muted-foreground">No notifications yet.</Text></CardContent></Card>
          ) : (
            items.map((item) => (
              <Pressable key={item.id} onPress={() => openMutation.mutate(item)} disabled={openMutation.isPending}>
                <Card className={item.read ? "" : "border-primary/40"}>
                  <CardContent className="gap-1 pt-2">
                    <View className="flex-row items-center justify-between gap-2">
                      <Text className={`text-sm flex-1 ${item.read ? "text-foreground" : "font-semibold text-foreground"}`} numberOfLines={1}>{item.title}</Text>
                      {!item.read ? <View className="h-2 w-2 rounded-full bg-primary" /> : null}
                    </View>
                    <Text className="text-xs text-muted-foreground" numberOfLines={2}>{item.body}</Text>
                    <Text className="text-xs text-muted-foreground">{new Date(item.created_at).toLocaleString()}</Text>
                  </CardContent>
                </Card>
              </Pressable>
            ))
          )}
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
