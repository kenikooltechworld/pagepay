import { apiFetch, parseApiError } from "@/src/shared/api/client";

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  const res = await apiFetch("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to change password"));
}

export async function deleteAccount(password: string): Promise<void> {
  const res = await apiFetch("/auth/me", {
    method: "DELETE",
    body: JSON.stringify({ password, confirmation: "DELETE" }),
  });
  if (!res.ok) throw new Error(await parseApiError(res, "Failed to delete account"));
}
