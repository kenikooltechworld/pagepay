import { apiFetch, parseApiError } from "@/src/shared/api/client";

export type PinStatus = { has_pin: boolean };

export async function fetchPinStatus(): Promise<PinStatus> {
  const res = await apiFetch("/pin/status");
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load PIN status"));
  return (await res.json()) as PinStatus;
}

export async function setupPin(password: string, pin: string): Promise<void> {
  const res = await apiFetch("/pin/setup", {
    method: "POST",
    body: JSON.stringify({ password, pin }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to set PIN"));
}

export async function changePin(currentPin: string, newPin: string): Promise<void> {
  const res = await apiFetch("/pin/change", {
    method: "POST",
    body: JSON.stringify({ current_pin: currentPin, new_pin: newPin }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to change PIN"));
}

export async function verifyPin(pin: string): Promise<{ valid: boolean }> {
  const res = await apiFetch("/pin/verify", {
    method: "POST",
    body: JSON.stringify({ pin }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "PIN verification failed"));
  return (await res.json()) as { valid: boolean };
}

export async function requestPinReset(): Promise<{ ok: boolean; message?: string }> {
  const res = await apiFetch("/pin/forgot", { method: "POST" });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to request PIN reset"));
  return (await res.json()) as { ok: boolean; message?: string };
}

export async function verifyPinResetOtp(otp: string): Promise<{ ok: boolean; reset_token?: string | null }> {
  const res = await apiFetch("/pin/forgot/verify-otp", {
    method: "POST",
    body: JSON.stringify({ otp }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Invalid or expired code"));
  return (await res.json()) as { ok: boolean; reset_token?: string | null };
}

export async function resetPin(token: string, newPin: string): Promise<void> {
  const res = await apiFetch("/pin/reset", {
    method: "POST",
    body: JSON.stringify({ token, new_pin: newPin }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to reset PIN"));
}
