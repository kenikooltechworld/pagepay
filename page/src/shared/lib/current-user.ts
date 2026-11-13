import { create } from "zustand";
import { apiFetch } from "@/src/shared/api/client";

/** Matches `app/backend/app/schemas/auth.py` UserMe response. */
export type CurrentUser = {
  id: number;
  email: string | null;
  phone: string | null;
  username: string | null;
  tier?: string;
  role: string;
  status: string;
  created_at: string;
  email_verified: boolean;
  avatar_url: string | null;
  transaction_pin_set: boolean;
  referral_code: string | null;
  referred_by: string | null;
  service_credit_balance?: number;
  cashable_balance?: number;
  points_balance?: number;
};

type CurrentUserState = {
  user: CurrentUser | null;
  loaded: boolean;
  loading: boolean;
  error: string | null;
  setUser: (user: CurrentUser | null) => void;
  fetch: () => Promise<CurrentUser | null>;
  clear: () => void;
};

export const useCurrentUserStore = create<CurrentUserState>((set, get) => ({
  user: null,
  loaded: false,
  loading: false,
  error: null,
  setUser: (user) => set({ user, loaded: true }),
  clear: () => set({ user: null, loaded: false, error: null }),
  fetch: async () => {
    if (get().loading) return get().user;
    set({ loading: true, error: null });
    try {
      const res = await apiFetch("/auth/me");
      if (!res.ok) {
        set({ user: null, loaded: true, loading: false });
        return null;
      }
      const user = (await res.json()) as CurrentUser;
      set({ user, loaded: true, loading: false });
      return user;
    } catch (e: any) {
      set({ loaded: true, loading: false, error: e?.message || "Failed to load user" });
      return null;
    }
  },
}));

export function useCurrentUser() {
  return useCurrentUserStore((s) => s.user);
}

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  return useCurrentUserStore.getState().fetch();
}