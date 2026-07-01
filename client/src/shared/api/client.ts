import Constants from 'expo-constants';
import { getToken, saveToken, clearToken } from '@/src/shared/lib/storage';

// Read API URL from expo-constants (loaded from app.config.js -> .env).
// Mirrors Earn9ja/services/api/client.ts:17-18.
const API_URL =
  Constants.expoConfig?.extra?.apiUrl ||
  process.env.EXPO_PUBLIC_API_URL ||
  'http://localhost:8000';

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const token = await getToken();
  const isFormData = options.body instanceof FormData;
  const headers: HeadersInit = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...options.headers,
  };

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (e) {
    console.error(`[apiFetch] network error: ${API_URL}${path}`, e);
    throw new Error(
      `Can't reach the server at ${API_URL}. Check your connection and try again.`,
    );
  }

  if (res.status === 401) {
    await clearToken();
  }

  return res;
}
