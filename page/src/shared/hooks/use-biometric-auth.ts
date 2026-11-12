import { useCallback, useEffect, useState } from "react";
import { Platform } from "react-native";
import * as LocalAuthentication from "expo-local-authentication";

export type BiometricState = {
  supported: boolean;
  enrolled: boolean;
  loading: boolean;
};

export async function getBiometricState(): Promise<BiometricState> {
  try {
    const [supported, enrolled] = await Promise.all([
      LocalAuthentication.hasHardwareAsync(),
      LocalAuthentication.isEnrolledAsync(),
    ]);
    return { supported, enrolled, loading: false };
  } catch {
    return { supported: false, enrolled: false, loading: false };
  }
}

export async function authenticateBiometric(reason = "Authenticate to continue"): Promise<boolean> {
  try {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: reason,
      cancelLabel: "Cancel",
      fallbackLabel: Platform.OS === "ios" ? "Use passcode" : undefined,
      disableDeviceFallback: false,
    });
    return result.success;
  } catch {
    return false;
  }
}

export function useBiometricCapability() {
  const [state, setState] = useState<BiometricState>({ supported: false, enrolled: false, loading: true });

  const refresh = useCallback(async () => {
    setState((s) => ({ ...s, loading: true }));
    const next = await getBiometricState();
    setState(next);
    return next;
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { ...state, refresh };
}
