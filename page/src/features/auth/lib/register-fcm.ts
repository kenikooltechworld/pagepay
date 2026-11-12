export async function registerFcmToken() {
  const mod = await import("@/src/lib/firebase");
  return mod.registerFcmToken();
}