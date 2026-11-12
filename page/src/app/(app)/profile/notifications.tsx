import { useEffect, useState } from "react";
import { ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { fetchNotificationPrefs, saveNotificationPrefs, type NotificationPrefs } from "@/src/shared/api/notifications";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

const KEYS: { key: keyof Omit<NotificationPrefs, "quiet_hours_start" | "quiet_hours_end" | "created_at" | "updated_at">; label: string }[] = [
  { key: "push_enabled", label: "Push notifications" },
  { key: "study_reminders", label: "Study reminders" },
  { key: "task_alerts", label: "Task alerts" },
  { key: "referral_bonuses", label: "Referral bonuses" },
  { key: "wallet_updates", label: "Wallet updates" },
  { key: "ad_rewards", label: "Ad rewards" },
];

export default function NotificationPreferencesScreen() {
  const router = useRouter();
  const { toast } = useToast();
  const qc = useQueryClient();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [draft, setDraft] = useState<NotificationPrefs | null>(null);

  const q = useQuery({ queryKey: ["notifications", "preferences"], queryFn: fetchNotificationPrefs });
  useEffect(() => { if (q.data) setDraft(q.data); }, [q.data]);

  const m = useMutation({
    mutationFn: (p: NotificationPrefs) => saveNotificationPrefs(p),
    onSuccess: (saved) => {
      setDraft(saved);
      qc.setQueryData(["notifications", "preferences"], saved);
      toast({ title: "Preferences saved", variant: "success" });
    },
    onError: (e: Error) => toast({ title: "Failed", description: e.message, variant: "destructive" }),
  });

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Notification preferences" showBack onBack={() => router.back()} tokens={tokens} />
        <ScrollView className="flex-1" contentContainerClassName="px-4 py-4 gap-4">
          <Card>
            <CardContent className="gap-3 pt-2">
              {q.isLoading || !draft ? (
                <View className="gap-2"><Skeleton className="h-6 w-48" /><Skeleton className="h-6 w-40" /><Skeleton className="h-6 w-44" /></View>
              ) : q.error ? (
                <View className="gap-2"><Text className="text-sm text-destructive">{(q.error as Error).message}</Text><Button variant="outline" onPress={() => q.refetch()}>Retry</Button></View>
              ) : (
                <>
                  {KEYS.map(({ key, label }) => (
                    <View key={key} className="flex-row items-center justify-between py-1">
                      <Text className="text-sm text-foreground">{label}</Text>
                      <Checkbox checked={!!draft[key]} onCheckedChange={(v) => setDraft((d) => d ? { ...d, [key]: !!v } : d)} />
                    </View>
                  ))}
                  <Button onPress={() => draft && m.mutate(draft)} disabled={m.isPending} icon={m.isPending ? <PagePaySpinner size={20} /> : undefined}>Save preferences</Button>
                </>
              )}
            </CardContent>
          </Card>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
