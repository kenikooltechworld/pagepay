import { create } from "zustand";
import { clearTokens, getToken, setTokens } from "@/src/shared/lib/storage";

type AuthState = {
  token: string | null;
  hydrated: boolean;
  bootstrap: () => Promise<void>;
  setSession: (accessToken: string, refreshToken?: string | null) => Promise<void>;
  logout: () => Promise<void>;
};

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  hydrated: false,
  bootstrap: async () => {
    try {
      const token = await getToken();
      set({ token, hydrated: true });
    } catch {
      set({ token: null, hydrated: true });
    }
  },
  setSession: async (accessToken, refreshToken) => {
    await setTokens(accessToken, refreshToken);
    set({ token: accessToken, hydrated: true });
  },
  logout: async () => {
    await clearTokens();
    set({ token: null, hydrated: true });
  },
}));
