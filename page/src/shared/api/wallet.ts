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

export type WalletTransactionsParams = {
  currency?: "SP" | "CB";
  limit?: number;
  cursor?: number | null;
};

export type DepositInitResponse = {
  authorization_url: string;
  access_code: string;
  reference: string;
  amount_kobo: number;
  credit_amount_kobo: number;
  currency: string;
};

export type PaymentStatusResponse = {
  reference: string;
  status: string;
  purpose?: string | null;
  amount_kobo: number;
  credit_amount_kobo?: number | null;
  currency?: string | null;
  webhook_confirmed: boolean;
  created_at?: string | null;
  confirmed_at?: string | null;
};

export type VerifyPaymentResponse = {
  received: boolean;
  handled: boolean;
  reference: string;
  credited?: boolean | null;
  reason?: string | null;
  status?: string | null;
  payment_status?: string | null;
  balance_cb_kobo?: number | null;
};

export type ConvertCbToSpResponse = {
  converted_cb_kobo: number;
  credited_sp: number;
  balance_cb_kobo: number;
  balance_sp: number;
};

export type AdRewardResponse = {
  applied: boolean;
  balance_sp: number;
  ledger_id: number;
};

export async function fetchWalletBalance(): Promise<WalletBalance> {
  const res = await apiFetch("/wallet/balance");
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load wallet balance"));
  return (await res.json()) as WalletBalance;
}

export async function fetchWalletTransactions(
  params: number | WalletTransactionsParams = 20,
): Promise<LedgerListResponse> {
  const p: WalletTransactionsParams = typeof params === "number" ? { limit: params } : params;
  const q = new URLSearchParams();
  if (p.currency) q.set("currency", p.currency);
  if (p.limit != null) q.set("limit", String(p.limit));
  if (p.cursor != null) q.set("cursor", String(p.cursor));
  const suffix = q.toString() ? `?${q.toString()}` : "";
  const res = await apiFetch(`/wallet/transactions${suffix}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load transactions"));
  return (await res.json()) as LedgerListResponse;
}

export async function initiateWalletDeposit(
  amount_naira: number,
  opts?: { callback_url?: string },
): Promise<DepositInitResponse> {
  const body: any = { amount_naira: Math.round(amount_naira) };
  if (opts?.callback_url) body.callback_url = opts.callback_url;
  const res = await apiFetch("/wallet/deposit", {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to initiate deposit"));
  return (await res.json()) as DepositInitResponse;
}

export async function fetchPaymentStatus(reference: string): Promise<PaymentStatusResponse> {
  const res = await apiFetch(`/payments/paystack/status/${encodeURIComponent(reference)}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to fetch payment status"));
  return (await res.json()) as PaymentStatusResponse;
}

export async function verifyPayment(reference: string): Promise<VerifyPaymentResponse> {
  const res = await apiFetch(`/payments/paystack/verify/${encodeURIComponent(reference)}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to verify payment"));
  return (await res.json()) as VerifyPaymentResponse;
}

export async function convertCbToSp(amount_cb_kobo: number): Promise<ConvertCbToSpResponse> {
  const res = await apiFetch("/wallet/cb/convert-to-sp", {
    method: "POST",
    body: JSON.stringify({ amount_cb_kobo: Math.round(amount_cb_kobo) }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to convert balance"));
  return (await res.json()) as ConvertCbToSpResponse;
}

export async function claimAdReward(claim_id: string, amount_sp: number): Promise<AdRewardResponse> {
  const res = await apiFetch("/wallet/sp/ad-reward", {
    method: "POST",
    body: JSON.stringify({ claim_id, amount_sp }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to claim ad reward"));
  return (await res.json()) as AdRewardResponse;
}

export function formatKoboAsNaira(kobo: number): string {
  const naira = kobo / 100;
  return `?${naira.toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatTransactionSource(source: string): string {
  return source.replace(/[_-]+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function formatTransactionAmount(entry: LedgerEntry): string {
  const sign = entry.direction === "credit" ? "+" : entry.direction === "debit" ? "-" : "";
  if (entry.currency === "CB") return `${sign}${formatKoboAsNaira(entry.amount)}`;
  return `${sign}${Number(entry.amount).toLocaleString()} SP`;
}

export function paymentStatusLabel(status: string): string {
  const s = (status || "").toLowerCase();
  if (s === "success") return "Successful";
  if (s === "pending") return "Pending";
  if (s === "failed") return "Failed";
  if (s === "refunded") return "Refunded";
  if (s === "refund_pending") return "Refund pending";
  if (s === "refund_failed") return "Refund failed";
  if (s === "amount_mismatch") return "Amount mismatch";
  return formatTransactionSource(status || "unknown");
}
