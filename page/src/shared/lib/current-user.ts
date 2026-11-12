import { apiFetch } from "@/src/shared/api/client";

/** Matches `app/backend/app/schemas/auth.py` UserMe response. */
export type CurrentUser = {
  id: number;
  email: string | null;
  phone: string | null;
  username: string | null;
  tier: string;
  role: string;
  status: string;
  created_at: string;
  email_verified: boolean;
  avatar_url: string | null;
  transaction_pin_set: boolean;
  referral_code: string | null;
  referred_by: string | null;
};

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  try {
    const res = await apiFetch("/auth/me");
    if (!res.ok) return null;
    return (await res.json()) as CurrentUser;
  } catch {
    return null;
  }
}
