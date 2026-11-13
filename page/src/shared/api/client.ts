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

export async function parseApiError(res: Response, fallback = "Request failed"): Promise<string> {
  let data: any = {};
  const raw = await res.text().catch(() => "");
  try {
    data = raw ? JSON.parse(raw) : {};
  } catch {
    data = { detail: raw || res.statusText || fallback };
  }
  const detail = data?.detail;
  if (Array.isArray(detail)) {
    const msg = detail.map((d: any) => d?.msg || d?.message || JSON.stringify(d)).filter(Boolean).join("; ");
    if (msg) return msg;
  }
  if (typeof detail === "string" && detail) return detail;
  if (typeof data?.message === "string" && data.message) return data.message;
  if (!res.ok) return res.statusText || fallback;
  return fallback;
}

export async function authJson<T>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json().catch(() => ({}))) as T;
}

export type ApiUploadOptions = {
  onProgress?: (loaded: number, total: number) => void;
  timeoutMs?: number;
};

export type ApiUploadResult = {
  ok: boolean;
  status: number;
  statusText: string;
  json: () => Promise<any>;
  text: () => Promise<string>;
};

export async function apiUpload(
  path: string,
  formData: FormData,
  options: ApiUploadOptions = {},
): Promise<ApiUploadResult> {
  const { onProgress, timeoutMs = 120_000 } = options;
  const token = await getToken();

  return new Promise<ApiUploadResult>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}${path}`, true);
    xhr.timeout = timeoutMs;

    if (token) {
      xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    }

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable && e.total > 0) {
          onProgress(e.loaded, e.total);
        }
      };
    }

    xhr.onerror = () => {
      if (xhr.status > 0) {
        const body = xhr.responseText || "";
        let detail = body;
        try { const p = JSON.parse(body); detail = p?.detail || body; } catch {}
        reject(new Error(detail || `HTTP ${xhr.status}`));
        return;
      }
      reject(new Error("Network error during upload"));
    };
    xhr.ontimeout = () => reject(new Error("Upload timed out"));
    xhr.onload = async () => {
      if (xhr.status === 401) {
        try {
          await clearTokens();
        } catch {}
        _onUnauthenticated?.();
      }
      resolve({
        ok: xhr.status >= 200 && xhr.status < 300,
        status: xhr.status,
        statusText: xhr.statusText || "",
        json: () => Promise.resolve().then(() => JSON.parse(xhr.responseText || "null")),
        text: () => Promise.resolve(xhr.responseText || ""),
      });
    };

    try {
      xhr.send(formData);
    } catch (e: any) {
      reject(new Error(e?.message || "Upload failed"));
    }
  });
}