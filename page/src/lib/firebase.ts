import { Platform } from "react-native";
import Constants from "expo-constants";
import { apiFetch } from "@/src/shared/api/client";

export async function registerFcmToken(): Promise<string | null> {
  if (Platform.OS === "web") return null;
  try {
    const Device = await import("expo-device");
    if (!Device.isDevice) return null;

    const Notifications = await import("expo-notifications");
    const { status: existing } = await Notifications.getPermissionsAsync();
    let status = existing;
    if (status !== "granted") {
      status = (await Notifications.requestPermissionsAsync()).status;
    }
    if (status !== "granted") return null;

    const messagingMod = await import("@react-native-firebase/messaging");
    const messaging = messagingMod.getMessaging();
    const token = await messagingMod.getToken(messaging);
    if (!token) return null;

    await apiFetch("/notifications/fcm-token", {
      method: "POST",
      body: JSON.stringify({
        token,
        platform: Platform.OS,
        device_id: Constants.sessionId ?? undefined,
      }),
    });
    return token;
  } catch {
    return null;
  }
}

