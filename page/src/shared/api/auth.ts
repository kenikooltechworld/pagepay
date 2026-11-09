import { useMutation, useQueryClient } from "@tanstack/react-query";
import { API_URL, apiFetch, authJson, setOnUnauthenticated, type TokenPair } from "@/src/shared/api/client";
import { useAuthStore } from "@/src/shared/store/auth";

type RegisterInput = {
  email?: string;
  phone?: string;
  username?: string;
  password: string;
  referral_code?: string;
};

type LoginInput = { username: string; password: string };

async function loginRequest(input: LoginInput): Promise<TokenPair> {
  const body = new URLSearchParams();
  body.set("username", input.username);
  body.set("password", input.password);
  const res = await fetch(`${API_URL}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail || "Login failed");
  return data as TokenPair;
}

export function useRegister() {
  const setSession = useAuthStore((s) => s.setSession);
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: RegisterInput) => authJson<TokenPair>("/auth/register", input),
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
