import { apiFetch, parseApiError } from "@/src/shared/api/client";

export type WalletBalance = {
  service_points_sp: number;
  cashable_balance_cb_kobo: number;
  points_balance_legacy: number;
  sp_per_naira: number;
  study_unlock_default_points: number;
};

export type LedgerEntry = {
  id: number;
  currency: "SP" | "CB" | string;
  direction: "credit" | "debit" | string;
  amount: number;
  balance_after: number;
  source: string;
  reference_type: string | null;
  reference_id: string | null;
  created_at: string;
};

export type LedgerListResponse = {
  items: LedgerEntry[];
  next_cursor: number | null;
};

export async function fetchWalletBalance(): Promise<WalletBalance> {
  const res = await apiFetch("/wallet/balance");
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load wallet balance"));
  return (await res.json()) as WalletBalance;
}

export async function fetchWalletTransactions(limit = 1): Promise<LedgerListResponse> {
  const res = await apiFetch(`/wallet/transactions?limit=${limit}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load transactions"));
  return (await res.json()) as LedgerListResponse;
}

export function formatKoboAsNaira(kobo: number): string {
  const naira = kobo / 100;
  return `₦${naira.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatTransactionSource(source: string): string {
  return source.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatTransactionAmount(entry: LedgerEntry): string {
  const sign = entry.direction === "credit" ? "+" : entry.direction === "debit" ? "-" : "";
  if (entry.currency === "CB") return `${sign}${formatKoboAsNaira(entry.amount)}`;
  return `${sign}${entry.amount.toLocaleString()} SP`;
}
