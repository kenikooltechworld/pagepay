import { apiFetch, parseApiError } from "@/src/shared/api/client";

export type NotificationPrefs = {
  push_enabled: boolean;
  study_reminders: boolean;
  task_alerts: boolean;
  referral_bonuses: boolean;
  wallet_updates: boolean;
  ad_rewards: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  created_at?: string;
  updated_at?: string;
};

export type NotificationItem = {
  id: number;
  user_id: number;
  title: string;
  body: string;
  category: string | null;
  data: Record<string, unknown> | null;
  read: boolean;
  created_at: string;
};

export type NotificationsListResponse = {
  notifications: NotificationItem[];
  unread_count: number;
};

export type FcmToken = {
  id: number;
  token: string;
  platform: string;
  device_id: string | null;
  is_active: boolean;
  created_at: string;
};

export async function fetchNotifications(limit = 50, offset = 0): Promise<NotificationsListResponse> {
  const res = await apiFetch(`/notifications?limit=${limit}&offset=${offset}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load notifications"));
  return (await res.json()) as NotificationsListResponse;
}

export async function fetchNotification(id: number): Promise<NotificationItem> {
  const res = await apiFetch(`/notifications/${id}`);
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load notification"));
  return (await res.json()) as NotificationItem;
}

export async function markNotificationRead(id: number): Promise<void> {
  const res = await apiFetch(`/notifications/${id}/read`, { method: "POST" });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to mark notification read"));
}

export async function markAllNotificationsRead(): Promise<void> {
  const res = await apiFetch("/notifications/read-all", { method: "POST" });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to mark all read"));
}

export async function fetchFcmTokens(): Promise<FcmToken[]> {
  const res = await apiFetch("/notifications/fcm-tokens");
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load FCM tokens"));
  return (await res.json()) as FcmToken[];
}

export async function deleteFcmToken(token: string): Promise<void> {
  const res = await apiFetch(`/notifications/fcm-token/${encodeURIComponent(token)}`, { method: "DELETE" });
  if (!res.ok && res.status !== 204) throw new Error(await parseApiError(res, "Failed to remove token"));
}

export async function fetchNotificationPrefs(): Promise<NotificationPrefs> {
  const res = await apiFetch("/notifications/preferences");
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to load preferences"));
  return (await res.json()) as NotificationPrefs;
}

export async function saveNotificationPrefs(p: NotificationPrefs): Promise<NotificationPrefs> {
  const res = await apiFetch("/notifications/preferences", { method: "PUT", body: JSON.stringify(p) });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to save preferences"));
  return (await res.json()) as NotificationPrefs;
}
