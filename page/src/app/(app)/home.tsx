import { useCallback, useMemo, useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useQuery } from "@tanstack/react-query";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { useLogout } from "@/src/shared/api/auth";
import {
  fetchWalletBalance,
  fetchWalletTransactions,
  formatKoboAsNaira,
  formatTransactionAmount,
  formatTransactionSource,
  type LedgerEntry,
} from "@/src/shared/api/wallet";
import { fetchCurrentUser } from "@/src/shared/lib/current-user";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";

function greetingForHour(h: number) {
  if (h < 5) return "Still up";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  if (h < 21) return "Good evening";
  return "Good night";
}

function formatCompactSp(sp: number) {
  if (sp >= 1_000_000) return `${(sp / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
  if (sp >= 1_000) return `${(sp / 1_000).toFixed(1).replace(/\.0$/, "")}K`;
  return `${sp}`;
}

function displayName(user: { username?: string | null; email?: string | null; phone?: string | null } | null | undefined) {
  return user?.username || user?.email || user?.phone || "there";
}

function lastTxLabel(entry: LedgerEntry) {
  const sign = entry.direction === "credit" ? "Credit" : "Debit";
  return `${sign} • ${formatTransactionSource(entry.source)}`;
}

export default function Home() {
  const router = useRouter();
  const logout = useLogout();
  const { toast } = useToast();
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const [refreshing, setRefreshing] = useState(false);

  const userQuery = useQuery({
    queryKey: ["auth", "me"],
    queryFn: fetchCurrentUser,
  });
  const balanceQuery = useQuery({
    queryKey: ["wallet", "balance"],
    queryFn: fetchWalletBalance,
  });
  const txQuery = useQuery({
    queryKey: ["wallet", "transactions", "last"],
    queryFn: () => fetchWalletTransactions(1),
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    try {
      await Promise.all([userQuery.refetch(), balanceQuery.refetch(), txQuery.refetch()]);
    } finally {
      setRefreshing(false);
    }
  }, [userQuery, balanceQuery, txQuery]);

  const loadingWallet = balanceQuery.isLoading || txQuery.isLoading;
  const walletError = balanceQuery.error || txQuery.error;
  const lastTx = txQuery.data?.items?.[0] ?? null;
  const name = displayName(userQuery.data);
  const greeting = useMemo(() => greetingForHour(new Date().getHours()), []);
  const sp = balanceQuery.data?.service_points_sp ?? 0;
  const cbKobo = balanceQuery.data?.cashable_balance_cb_kobo ?? 0;
  const initial = (name.trim()[0] || "P").toUpperCase();

  return (
    <SafeAreaView edges={["top"]} style={[styles.root, { backgroundColor: tokens.paper }]}>
      <StatusBar style="auto" />
      <View style={styles.header}>
        <View style={styles.iconsRow}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Profile"
            onPress={() => toast({ title: "Profile", description: "Profile screen coming soon." })}
            style={[styles.avatar, { backgroundColor: tokens.mintSoft, borderColor: tokens.border }]}
          >
            <Text style={[styles.avatarText, { color: tokens.mint }]}>{initial}</Text>
          </Pressable>

          <Pressable
            onPress={() => toast({ title: "Wallet", description: "Wallet details coming soon." })}
            accessibilityRole="button"
            accessibilityLabel={`Wallet: ${sp} SP, ${formatKoboAsNaira(cbKobo)} cash`}
            style={[styles.balanceChip, { backgroundColor: tokens.card, borderColor: tokens.border }]}
          >
            <View style={[styles.balanceDot, { backgroundColor: tokens.mint }]} />
            <Text style={[styles.balanceAmountCompact, { color: tokens.ink }]} numberOfLines={1}>
              {formatCompactSp(sp)} SV
            </Text>
            <Text style={[styles.balanceSeparator, { color: tokens.inkMuted }]}>·</Text>
            <Text style={[styles.balanceAmountCompact, { color: tokens.mint }]} numberOfLines={1}>
              {formatKoboAsNaira(cbKobo)} C
            </Text>
          </Pressable>

          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Notifications"
            onPress={() => toast({ title: "Notifications", description: "Notifications coming soon." })}
            hitSlop={8}
            style={styles.bellBtn}
          >
            <Ionicons name="notifications-outline" size={22} color={tokens.ink} />
          </Pressable>
        </View>

        <View style={styles.greetingRow}>
          <Text style={[styles.greeting, { color: tokens.inkMuted }]}>{greeting},</Text>
          <Text style={[styles.username, { color: tokens.ink }]} numberOfLines={1}>
            {name}
          </Text>
        </View>
      </View>

      <ScrollView
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={tokens.mint} />}
      >
        <Card className="border-border bg-card">
          <CardContent className="gap-4 pt-2">
            <View className="flex-row items-center justify-between">
              <View className="gap-0.5">
                <Text className="text-base font-semibold text-foreground">Wallet</Text>
                <Text className="text-xs text-muted-foreground">Balances and recent activity</Text>
              </View>
              {loadingWallet && !refreshing ? <PagePaySpinner size={18} /> : null}
            </View>

            {loadingWallet && !balanceQuery.data && !txQuery.data ? (
              <View className="gap-3">
                <Skeleton className="h-10 w-44" />
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-20 w-full rounded-xl" />
                <Skeleton className="h-11 w-full rounded-lg" />
              </View>
            ) : walletError && !balanceQuery.data ? (
              <View className="gap-3">
                <Text className="text-sm text-destructive">
                  {(walletError as Error).message || "Could not load wallet."}
                </Text>
                <Button variant="outline" onPress={() => void onRefresh()}>
                  Retry
                </Button>
              </View>
            ) : (
              <View className="gap-4">
                <View className="gap-2">
                  <View className="flex-row items-end justify-between">
                    <View className="gap-1">
                      <Text className="text-xs text-muted-foreground">Cash balance</Text>
                      <Text className="text-3xl font-bold text-foreground">{formatKoboAsNaira(cbKobo)}</Text>
                      <Text className="text-xs text-muted-foreground">Cashable (CB)</Text>
                    </View>
                    <View className="items-end gap-1">
                      <Text className="text-xs text-muted-foreground">Service points</Text>
                      <Text className="text-xl font-semibold text-foreground">{formatCompactSp(sp)} SV</Text>
                      <Text className="text-xs text-muted-foreground">{sp.toLocaleString()} SP</Text>
                    </View>
                  </View>
                </View>

                <View className="rounded-xl border border-border bg-muted/30 p-3 gap-1.5">
                  <Text className="text-xs font-medium text-muted-foreground">Last transaction</Text>
                  {lastTx ? (
                    <>
                      <View className="flex-row items-center justify-between gap-2">
                        <Text className="flex-1 text-sm font-medium text-foreground" numberOfLines={1}>
                          {lastTxLabel(lastTx)}
                        </Text>
                        <Text
                          className={`text-sm font-semibold ${
                            lastTx.direction === "credit" ? "text-green-600" : "text-foreground"
                          }`}
                        >
                          {formatTransactionAmount(lastTx)}
                        </Text>
                      </View>
                      <Text className="text-xs text-muted-foreground">
                        {formatTransactionSource(lastTx.currency)} · {new Date(lastTx.created_at).toLocaleString()}
                      </Text>
                    </>
                  ) : (
                    <Text className="text-sm text-muted-foreground">No transactions yet</Text>
                  )}
                </View>

                <Button
                  onPress={() =>
                    toast({
                      title: "Add money / Purchase SP",
                      description: "Funding flow coming soon.",
                    })
                  }
                >
                  Add money / Purchase SP
                </Button>
              </View>
            )}
          </CardContent>
        </Card>

        <Button
          variant="outline"
          onPress={() => logout.mutate(undefined, { onSuccess: () => router.replace("/(auth)") })}
          disabled={logout.isPending}
          icon={logout.isPending ? <PagePaySpinner size={20} /> : undefined}
        >
          Log out
        </Button>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  header: {
    paddingHorizontal: 16,
    paddingTop: 4,
    paddingBottom: 16,
  },
  scroll: {
    paddingHorizontal: 16,
    paddingBottom: 24,
    gap: 16,
  },
  iconsRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  avatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
  },
  avatarText: {
    fontSize: 13,
    fontWeight: "700",
  },
  bellBtn: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
  },
  greetingRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 6,
    marginTop: 10,
  },
  greeting: {
    fontSize: 13,
    lineHeight: 18,
    letterSpacing: 0.2,
  },
  username: {
    fontSize: 15,
    lineHeight: 20,
    letterSpacing: -0.2,
    fontWeight: "700",
    flexShrink: 1,
  },
  balanceChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
    borderRadius: 999,
    borderWidth: 1,
    maxWidth: "68%",
  },
  balanceDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
  },
  balanceAmountCompact: {
    fontSize: 12,
    lineHeight: 14,
    letterSpacing: -0.2,
    fontWeight: "700",
  },
  balanceSeparator: {
    fontSize: 12,
    lineHeight: 14,
    marginHorizontal: 2,
  },
});