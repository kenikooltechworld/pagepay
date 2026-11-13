import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AppState, Pressable, RefreshControl, ScrollView, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import * as WebBrowser from "expo-web-browser";
import * as Linking from "expo-linking";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { PageHeader } from "@/components/PageHeader";
import { PagePaySpinner } from "@/components/PagePaySpinner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Text } from "@/components/ui/text";
import { useToast } from "@/components/ui/toast";
import { PagePay } from "@/constants/theme";
import { useEffectiveScheme } from "@/src/shared/hooks/use-effective-scheme";
import {
  convertCbToSp,
  fetchPaymentStatus,
  fetchWalletBalance,
  fetchWalletTransactions,
  formatKoboAsNaira,
  formatTransactionAmount,
  formatTransactionSource,
  initiateWalletDeposit,
  paymentStatusLabel,
  verifyPayment,
  type LedgerEntry,
} from "@/src/shared/api/wallet";

type CurrencyFilter = "ALL" | "CB" | "SP";

function fmtDate(iso: string) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function TxRow({ entry, tokens }: { entry: LedgerEntry; tokens: any }) {
  const isCredit = entry.direction === "credit";
  return (
    <View className="flex-row items-start justify-between py-3 border-b border-border">
      <View className="flex-1 pr-3 gap-0.5">
        <Text className="text-sm font-medium text-foreground" numberOfLines={1}>
          {formatTransactionSource(entry.source)}
        </Text>
        <Text className="text-xs text-muted-foreground">
          {entry.currency} · {entry.reference_type ? formatTransactionSource(entry.reference_type) : "ledger"} · {fmtDate(entry.created_at)}
        </Text>
        {entry.reference_id ? (
          <Text className="text-[11px] text-muted-foreground" numberOfLines={1}>
            Ref: {entry.reference_id}
          </Text>
        ) : null}
      </View>
      <View className="items-end gap-0.5">
        <Text className={`text-sm font-semibold ${isCredit ? "text-green-600" : "text-foreground"}`}>
          {formatTransactionAmount(entry)}
        </Text>
        <Text className="text-[11px] text-muted-foreground">Bal: {entry.currency === "CB" ? formatKoboAsNaira(entry.balance_after) : `${Number(entry.balance_after).toLocaleString()} SP`}</Text>
      </View>
    </View>
  );
}

export default function WalletScreen() {
  const scheme = useEffectiveScheme();
  const tokens = PagePay[scheme] ?? PagePay.light;
  const { toast } = useToast();
  const qc = useQueryClient();

  const [currency, setCurrency] = useState<CurrencyFilter>("ALL");
  const [amountNaira, setAmountNaira] = useState("100");
  const [convertNaira, setConvertNaira] = useState("");
  const [pendingRef, setPendingRef] = useState<string | null>(null);
  const [pendingAuthUrl, setPendingAuthUrl] = useState<string | null>(null);
  const handledRef = useRef<string | null>(null);

  const extractReference = useCallback((url: string | null | undefined) => {
    if (!url) return null;
    try {
      const parsed = Linking.parse(url);
      const q: any = parsed?.queryParams || {};
      const ref = q.reference || q.trxref || q.ref;
      return typeof ref === "string" && ref ? ref : null;
    } catch {
      return null;
    }
  }, []);

  const balanceQuery = useQuery({
    queryKey: ["wallet", "balance"],
    queryFn: fetchWalletBalance,
  });

  const txQuery = useQuery({
    queryKey: ["wallet", "transactions", currency],
    queryFn: async () => {
      // fetch up to 100 most recent for current filter (cursor pagination can be added later)
      return fetchWalletTransactions({ limit: 100, currency: currency === "ALL" ? undefined : currency });
    },
  });

  const statusQuery = useQuery({
    queryKey: ["payments", "status", pendingRef],
    queryFn: () => fetchPaymentStatus(pendingRef!),
    enabled: !!pendingRef,
    refetchInterval: (q) => {
      const s = (q.state.data?.status || "").toLowerCase();
      return s && s !== "pending" ? false : 6000;
    },
  });

  const refreshAll = useCallback(async () => {
    await Promise.all([
      qc.invalidateQueries({ queryKey: ["wallet", "balance"] }),
      qc.invalidateQueries({ queryKey: ["wallet", "transactions"] }),
      pendingRef ? qc.invalidateQueries({ queryKey: ["payments", "status", pendingRef] }) : Promise.resolve(),
    ]);
    await Promise.all([balanceQuery.refetch(), txQuery.refetch()]);
  }, [qc, pendingRef, balanceQuery, txQuery]);

  const depositMutation = useMutation({
    mutationFn: async (naira: number) => {
      const callback_url = Linking.createURL("/(app)/wallet");
      return initiateWalletDeposit(naira, { callback_url });
    },
    onSuccess: async (data) => {
      setPendingRef(data.reference);
      setPendingAuthUrl(data.authorization_url);
      handledRef.current = null;
      toast({ title: "Deposit initialized", description: `Ref: ${data.reference}. Complete payment, then return to app.` });
      try {
        const redirectUrl = Linking.createURL("/(app)/wallet");
        const result = await WebBrowser.openAuthSessionAsync(data.authorization_url, redirectUrl);
        if (result.type === "success" && result.url) {
          const ref = extractReference(result.url) || data.reference;
          handledRef.current = ref;
          verifyMutation.mutate(ref);
        }
      } catch {
        try { await WebBrowser.openBrowserAsync(data.authorization_url); } catch {}
      }
    },
    onError: (e: any) => toast({ title: "Deposit failed", description: e?.message || "Could not start deposit", variant: "destructive" }),
  });

  const verifyMutation = useMutation({
    mutationFn: async (ref: string) => verifyPayment(ref),
    onSuccess: async (res) => {
      if (res.handled || res.credited || res.payment_status === "success" || res.reason === "duplicate") {
        toast({ title: "Payment verified", description: res.credited ? "Wallet credited." : (res.reason || res.payment_status || "Updated") , variant: "success" });
        if (res.payment_status === "success" || res.credited || res.reason === "duplicate") {
          setPendingRef(null);
          setPendingAuthUrl(null);
        }
      } else {
        toast({ title: "Not credited yet", description: res.reason || res.status || res.payment_status || "Payment not successful yet." });
      }
      await refreshAll();
    },
    onError: (e: any) => toast({ title: "Verify failed", description: e?.message || "Could not verify payment", variant: "destructive" }),
  });

  // Handle deep link return (e.g. Paystack/OPay callback_url -> client://...) and auto-verify
  useEffect(() => {
    const handleUrl = (url: string | null | undefined) => {
      const ref = extractReference(url);
      if (!ref || !pendingRef || ref !== pendingRef) return;
      if (handledRef.current === ref) return;
      handledRef.current = ref;
      verifyMutation.mutate(ref);
    };
    const sub = Linking.addEventListener("url", ({ url }) => handleUrl(url));
    void Linking.getInitialURL().then(handleUrl).catch(() => {});
    return () => sub.remove();
  }, [extractReference, pendingRef, verifyMutation]);

  // Auto-verify when app returns to foreground with a pending deposit (webhook fallback UX)
  useEffect(() => {
    if (!pendingRef) return;
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        void refreshAll();
        if (handledRef.current !== pendingRef) {
          handledRef.current = pendingRef;
          verifyMutation.mutate(pendingRef);
        }
      }
    });
    return () => sub.remove();
  }, [pendingRef, refreshAll, verifyMutation]);

  const convertMutation = useMutation({
    mutationFn: async (kobo: number) => convertCbToSp(kobo),
    onSuccess: async (res) => {
      toast({ title: "Converted", description: `+${res.credited_sp.toLocaleString()} SP`, variant: "success" });
      setConvertNaira("");
      await refreshAll();
    },
    onError: (e: any) => toast({ title: "Convert failed", description: e?.message || "Could not convert", variant: "destructive" }),
  });



  const sp = balanceQuery.data?.service_points_sp ?? 0;
  const cbKobo = balanceQuery.data?.cashable_balance_cb_kobo ?? 0;
  const spPerNaira = balanceQuery.data?.sp_per_naira ?? 10;
  const unlockDefault = balanceQuery.data?.study_unlock_default_points ?? 50;

  const parsedNaira = Math.max(0, Math.floor(Number(amountNaira.replace(/[^0-9.]/g, "")) || 0));
  const parsedConvertNaira = Math.max(0, Number(convertNaira.replace(/[^0-9.]/g, "")) || 0);
  const convertKobo = Math.round(parsedConvertNaira * 100);
  const convertPreviewSp = Math.floor((convertKobo * spPerNaira) / 100);

  const loading = balanceQuery.isLoading || txQuery.isLoading;
  const err = (balanceQuery.error || txQuery.error) as Error | null;
  const txItems = txQuery.data?.items ?? [];

  const pendingStatus = statusQuery.data?.status;

  return (
    <View className="flex-1 bg-background">
      <StatusBar style="auto" />
      <SafeAreaView style={{ flex: 1 }} edges={["top", "bottom"]}>
        <PageHeader title="Wallet" tokens={tokens} />
        <ScrollView
          contentContainerStyle={{ padding: 16, paddingBottom: 32, gap: 14 }}
          refreshControl={<RefreshControl refreshing={balanceQuery.isFetching || txQuery.isFetching} onRefresh={refreshAll} tintColor={tokens.mint} />}
          keyboardShouldPersistTaps="handled"
        >
          <Card className="border-border bg-card">
            <CardHeader className="pb-2">
              <View className="flex-row items-center justify-between">
                <CardTitle className="text-lg">Balances</CardTitle>
                {(loading || balanceQuery.isFetching) && !balanceQuery.data ? <PagePaySpinner size={18} /> : null}
              </View>
            </CardHeader>
            <CardContent className="gap-3 pt-0">
              {err && !balanceQuery.data ? (
                <View className="gap-2">
                  <Text className="text-sm text-destructive">{err.message || "Failed to load wallet"}</Text>
                  <Button variant="outline" onPress={refreshAll}>Retry</Button>
                </View>
              ) : balanceQuery.isLoading && !balanceQuery.data ? (
                <View className="gap-2">
                  <Skeleton className="h-10 w-48" />
                  <Skeleton className="h-6 w-36" />
                  <Skeleton className="h-4 w-56" />
                </View>
              ) : (
                <View className="gap-2">
                  <View className="flex-row items-end justify-between">
                    <View className="gap-0.5">
                      <Text className="text-xs text-muted-foreground">Cash balance (CB)</Text>
                      <Text className="text-3xl font-bold text-foreground">{formatKoboAsNaira(cbKobo)}</Text>
                      <Text className="text-xs text-muted-foreground">{cbKobo.toLocaleString()} kobo</Text>
                    </View>
                    <View className="items-end gap-0.5">
                      <Text className="text-xs text-muted-foreground">Service points (SP)</Text>
                      <Text className="text-2xl font-semibold text-foreground">{sp.toLocaleString()}</Text>
                      <Text className="text-xs text-muted-foreground">non-cashable</Text>
                    </View>
                  </View>
                  <Text className="text-xs text-muted-foreground">Rate: {spPerNaira} SP / ?1 · Unlock default: {unlockDefault} SP</Text>
                </View>
              )}
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Add money (Paystack)</CardTitle>
            </CardHeader>
            <CardContent className="gap-3 pt-0">
              <Text className="text-xs text-muted-foreground">Enter amount in Naira. You’ll complete payment in Paystack checkout, then verify to credit CB.</Text>
              <View className="flex-row gap-2 flex-wrap">
                {[100, 200, 500, 1000, 2000].map((v) => (
                  <Pressable key={v} onPress={() => setAmountNaira(String(v))} className={`px-3 py-2 rounded-full border ${String(v)===amountNaira?"border-primary bg-muted/40":"border-border"}`}>
                    <Text className="text-xs text-foreground">?{v}</Text>
                  </Pressable>
                ))}
              </View>
              <Input value={amountNaira} onChangeText={setAmountNaira} keyboardType="number-pad" placeholder="Amount (?)" />
              <Button
                onPress={() => {
                  if (parsedNaira < 1) return toast({ title: "Enter amount", description: "Enter a valid amount in Naira." });
                  depositMutation.mutate(parsedNaira);
                }}
                disabled={depositMutation.isPending}
                icon={depositMutation.isPending ? <PagePaySpinner size={18} /> : undefined}
              >
                {depositMutation.isPending ? "Starting checkout..." : `Pay ?${parsedNaira || 0}`}
              </Button>

              {pendingRef ? (
                <View className="rounded-xl border border-border bg-muted/20 p-3 gap-2">
                  <Text className="text-xs font-medium text-foreground">Pending deposit</Text>
                  <Text className="text-xs text-muted-foreground" selectable>Reference: {pendingRef}</Text>
                  <Text className="text-xs text-muted-foreground">Status: {paymentStatusLabel(statusQuery.data?.status || pendingStatus || "pending")}{statusQuery.data?.webhook_confirmed ? " (confirmed)" : ""}</Text>
                  <View className="flex-row gap-2 flex-wrap">
                    <Button variant="outline" size="sm" onPress={() => pendingAuthUrl && WebBrowser.openBrowserAsync(pendingAuthUrl)} disabled={!pendingAuthUrl}>Open checkout</Button>
                    <Button variant="outline" size="sm" onPress={() => verifyMutation.mutate(pendingRef)} disabled={verifyMutation.isPending} icon={verifyMutation.isPending ? <PagePaySpinner size={16} /> : undefined}>Verify payment</Button>
                    <Button variant="ghost" size="sm" onPress={() => { setPendingRef(null); setPendingAuthUrl(null); }}>Clear</Button>
                  </View>
                  <Text className="text-[11px] text-muted-foreground">After paying, tap “Verify payment” (webhook may also credit automatically). Status auto-refreshes while pending.</Text>
                </View>
              ) : null}
            </CardContent>
          </Card>

          <Card className="border-border bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Convert CB ? SP</CardTitle>
            </CardHeader>
            <CardContent className="gap-3 pt-0">
              <Text className="text-xs text-muted-foreground">Convert cashable balance to service points at {spPerNaira} SP/?. SP is used to unlock study assets.</Text>
              <Input value={convertNaira} onChangeText={setConvertNaira} keyboardType="decimal-pad" placeholder="Amount in Naira (e.g. 50)" />
              <Text className="text-xs text-muted-foreground">You’ll convert {formatKoboAsNaira(convertKobo)} ? ~{convertPreviewSp.toLocaleString()} SP</Text>
              <Button
                variant="secondary"
                onPress={() => {
                  if (convertKobo <= 0) return toast({ title: "Enter amount", description: "Enter amount in Naira to convert." });
                  convertMutation.mutate(convertKobo);
                }}
                disabled={convertMutation.isPending}
                icon={convertMutation.isPending ? <PagePaySpinner size={18} /> : undefined}
              >
                Convert to SP
              </Button>
            </CardContent>
          </Card>



          <Card className="border-border bg-card">
            <CardHeader className="pb-2">
              <View className="flex-row items-center justify-between">
                <CardTitle className="text-lg">Transactions</CardTitle>
                {txQuery.isFetching ? <PagePaySpinner size={16} /> : null}
              </View>
            </CardHeader>
            <CardContent className="gap-2 pt-0">
              <View className="flex-row gap-2">
                {(["ALL", "CB", "SP"] as CurrencyFilter[]).map((c) => (
                  <Pressable key={c} onPress={() => setCurrency(c)} className={`px-3 py-1.5 rounded-full border ${currency===c?"border-primary bg-muted/40":"border-border"}`}>
                    <Text className="text-xs text-foreground">{c === "ALL" ? "All" : c}</Text>
                  </Pressable>
                ))}
              </View>
              {txQuery.isLoading && txItems.length === 0 ? (
                <View className="gap-2 pt-2">
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                  <Skeleton className="h-14 w-full" />
                </View>
              ) : txItems.length === 0 ? (
                <Text className="text-sm text-muted-foreground py-4">No transactions yet.</Text>
              ) : (
                <View className="pt-1">
                  {txItems.map((entry) => (
                    <TxRow key={`${entry.currency}-${entry.id}`} entry={entry} tokens={tokens} />
                  ))}
                  {txQuery.data?.next_cursor ? (
                    <Text className="text-[11px] text-muted-foreground pt-2">Showing latest {txItems.length}. More available (pull to refresh for latest).</Text>
                  ) : null}
                </View>
              )}
            </CardContent>
          </Card>
        </ScrollView>
      </SafeAreaView>
    </View>
  );
}
