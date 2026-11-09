import { Platform } from "react-native";
import * as SecureStore from "expo-secure-store";

const TOKEN_KEY = "pagepay_access_token";
const REFRESH_TOKEN_KEY = "pagepay_refresh_token";
const isWeb = Platform.OS === "web";

let _tokenCache: string | null | undefined = undefined;
let _refreshTokenCache: string | null | undefined = undefined;

async function readStore(key: string): Promise<string | null> {
  if (isWeb) {
    if (typeof localStorage === "undefined") return null;
    return localStorage.getItem(key);
  }
  return SecureStore.getItemAsync(key);
}

async function writeStore(key: string, value: string): Promise<void> {
  if (isWeb) {
    if (typeof localStorage !== "undefined") localStorage.setItem(key, value);
    return;
  }
  await SecureStore.setItemAsync(key, value);
}

async function removeStore(key: string): Promise<void> {
  if (isWeb) {
    if (typeof localStorage !== "undefined") localStorage.removeItem(key);
    return;
  }
  await SecureStore.deleteItemAsync(key);
}

export async function getToken(): Promise<string | null> {
  if (_tokenCache !== undefined) return _tokenCache;
  _tokenCache = await readStore(TOKEN_KEY);
  return _tokenCache;
}

export async function getRefreshToken(): Promise<string | null> {
  if (_refreshTokenCache !== undefined) return _refreshTokenCache;
  _refreshTokenCache = await readStore(REFRESH_TOKEN_KEY);
  return _refreshTokenCache;
}

export async function setTokens(
  accessToken: string,
  refreshToken?: string | null,
): Promise<void> {
  _tokenCache = accessToken;
  await writeStore(TOKEN_KEY, accessToken);
  if (refreshToken) {
    _refreshTokenCache = refreshToken;
    await writeStore(REFRESH_TOKEN_KEY, refreshToken);
  }
}

export async function clearTokens(): Promise<void> {
  _tokenCache = null;
  _refreshTokenCache = null;
  await removeStore(TOKEN_KEY);
  await removeStore(REFRESH_TOKEN_KEY);
}
