import { Platform } from "react-native";
import * as Device from "expo-device";
import * as Notifications from "expo-notifications";
import Constants from "expo-constants";
import { getMessaging, getToken } from "@react-native-firebase/messaging";
import { apiFetch } from "@/src/shared/api/client";

export async function registerFcmToken(): Promise<string | null> {
  if (Platform.OS === "web") return null;
  if (!Device.isDevice) return null;

  const { status: existing } = await Notifications.getPermissionsAsync();
  let status = existing;
  if (status !== "granted") {
    status = (await Notifications.requestPermissionsAsync()).status;
  }
  if (status !== "granted") return null;

  try {
    const messaging = getMessaging();
    const token = await getToken(messaging);
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

