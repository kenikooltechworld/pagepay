import * as SecureStore from "expo-secure-store";
import * as Device from "expo-device";
import * as Crypto from "expo-crypto";

const KEY = "pagepay_device_fingerprint_v1";

export async function getDeviceFingerprint(): Promise<string> {
  try {
    const existing = await SecureStore.getItemAsync(KEY);
    if (existing) return existing;
  } catch {}

  const seed = [
    Device.modelName ?? "unknown-model",
    Device.manufacturer ?? "unknown-mfr",
    Device.osVersion ?? "unknown-os",
    String(Device.deviceType ?? "unknown-type"),
    Crypto.randomUUID(),
  ].join("|");

  const hash = await Crypto.digestStringAsync(Crypto.CryptoDigestAlgorithm.SHA256, seed);
  try {
    await SecureStore.setItemAsync(KEY, hash);
  } catch {}
  return hash;
}
