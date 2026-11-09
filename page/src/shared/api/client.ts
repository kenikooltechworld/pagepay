import Constants from "expo-constants";
import { clearTokens, getRefreshToken, getToken, setTokens } from "@/src/shared/lib/storage";

const BASE_URL =
  Constants.expoConfig?.extra?.apiUrl || process.env.EXPO_PUBLIC_API_URL;

if (!BASE_URL) {
  throw new Error("EXPO_PUBLIC_API_URL is not set");
}

export const API_URL = `${BASE_URL.replace(/\/$/, "")}/api/v1`;

let _onUnauthenticated: (() => void) | null = null;
export function setOnUnauthenticated(cb: (() => void) | null) {
  _onUnauthenticated = cb;
}

export type TokenPair = { access_token: string; refresh_token: string };

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  const headers: HeadersInit = {
    ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };
  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status !== 401) return res;

  const refreshToken = await getRefreshToken();
  if (!refreshToken) {
    await clearTokens();
    _onUnauthenticated?.();
    return res;
  }
  const refreshRes = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  if (!refreshRes.ok) {
    await clearTokens();
    _onUnauthenticated?.();
    return res;
  }
  const pair = (await refreshRes.json()) as TokenPair;
  await setTokens(pair.access_token, pair.refresh_token);
  return fetch(`${API_URL}${path}`, {
    ...options,
    headers: { ...headers, Authorization: `Bearer ${pair.access_token}` },
  });
}

export async function authJson<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail || "Request failed");
  return data as T;
}
