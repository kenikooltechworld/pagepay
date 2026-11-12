import { apiFetch, parseApiError } from "@/src/shared/api/client";
import type { CurrentUser } from "@/src/shared/lib/current-user";

export type UpdateProfileInput = {
  username?: string | null;
  avatar_url?: string | null;
};

export async function updateProfile(input: UpdateProfileInput): Promise<CurrentUser> {
  const res = await apiFetch("/auth/me", {
    method: "PATCH",
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to update profile"));
  return (await res.json()) as CurrentUser;
}

export type AuditLog = {
  id: number;
  action: string;
  ip_address: string | null;
  user_agent: string | null;
  device_fingerprint: string | null;
  extra_data: string | null;
  created_at: string;
};

export type AuditLogsResponse = { logs: AuditLog[]; total: number };

export async function fetchAuditLogs(limit = 50, offset = 0): Promise<AuditLogsResponse> {
  const res = await apiFetch(`/auth/audit-logs?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load audit logs"));
  return (await res.json()) as AuditLogsResponse;
}

export async function uploadAvatarBase64(image: string): Promise<{ avatar_url: string | null }> {
  const res = await apiFetch("/auth/me/avatar", {
    method: "POST",
    body: JSON.stringify({ image }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to upload avatar"));
  return (await res.json()) as { avatar_url: string | null };
}
