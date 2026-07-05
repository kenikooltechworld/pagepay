import Constants from 'expo-constants';
import { getToken, saveToken, clearToken } from '@/src/shared/lib/storage';

// Read API URL from expo-constants (loaded from app.config.js -> .env).
const API_URL =
  Constants.expoConfig?.extra?.apiUrl ||
  process.env.EXPO_PUBLIC_API_URL ||
  'http://localhost:8000';

/** Global callback the layout registers so apiFetch can redirect
 *  to the login screen when the server rejects a token (401).
 *  Set from _layout.tsx via setOnUnauthenticated. */
let _onUnauthenticated: (() => void) | null = null;
export function setOnUnauthenticated(cb: () => void) {
  _onUnauthenticated = cb;
}

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
    // Redirect to login so the user isn't left stranded on a
    // broken authenticated screen.
    _onUnauthenticated?.();
  }

  return res;
}
