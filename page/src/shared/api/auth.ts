import { useMutation, useQueryClient } from "@tanstack/react-query";
import { API_URL, apiFetch, authJson, parseApiError, setOnUnauthenticated, type TokenPair } from "@/src/shared/api/client";
import { getDeviceFingerprint } from "@/src/shared/lib/device-fingerprint";
import { useAuthStore } from "@/src/shared/store/auth";

export type RegisterInput = {
  email?: string;
  phone?: string;
  username?: string;
  password: string;
  referral_code?: string;
};

export type LoginInput = { username: string; password: string };

/** POST /api/v1/auth/login — OAuth2 form, X-Device-Fingerprint (matches backend). */
export async function loginRequest(input: LoginInput): Promise<TokenPair> {
  const fingerprint = await getDeviceFingerprint().catch(() => undefined);
  const body = new URLSearchParams();
  body.set("username", input.username);
  body.set("password", input.password);
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      ...(fingerprint ? { "X-Device-Fingerprint": fingerprint } : {}),
    },
    body: body.toString(),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Login failed"));
  return (await res.json()) as TokenPair;
}

/** POST /api/v1/auth/google — { id_token } -> TokenResponse */
export async function googleLoginRequest(idToken: string): Promise<TokenPair> {
  const res = await fetch(`${API_URL}/auth/google`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id_token: idToken }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Google sign-in failed"));
  return (await res.json()) as TokenPair;
}

/** POST /api/v1/auth/register — JSON, X-Device-Fingerprint (matches backend). */
export async function registerRequest(input: RegisterInput): Promise<TokenPair> {
  const fingerprint = await getDeviceFingerprint().catch(() => undefined);
  const res = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(fingerprint ? { "X-Device-Fingerprint": fingerprint } : {}),
    },
    body: JSON.stringify(input),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Registration failed"));
  return (await res.json()) as TokenPair;
}

export function useRegister() {
  const setSession = useAuthStore((s) => s.setSession);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: registerRequest,
    onSuccess: async (data) => {
      await setSession(data.access_token, data.refresh_token);
      qc.invalidateQueries();
    },
  });
}

export function useLogin() {
  const setSession = useAuthStore((s) => s.setSession);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: loginRequest,
    onSuccess: async (data) => {
      await setSession(data.access_token, data.refresh_token);
      qc.invalidateQueries();
    },
  });
}

export function useGoogleLogin() {
  const setSession = useAuthStore((s) => s.setSession);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: googleLoginRequest,
    onSuccess: async (data) => {
      await setSession(data.access_token, data.refresh_token);
      qc.invalidateQueries();
    },
  });
}

export function useLogout() {
  const logout = useAuthStore((s) => s.logout);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      try {
        await apiFetch("/auth/logout", { method: "POST" });
      } finally {
        await logout();
      }
    },
    onSuccess: () => qc.clear(),
    onError: () => qc.clear(),
  });
}

export function bindAuthUnauthenticated() {
  setOnUnauthenticated(() => {
    void useAuthStore.getState().logout();
  });
}
