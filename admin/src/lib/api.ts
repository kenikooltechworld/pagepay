import axios from 'axios';
import type { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';

// When using httpOnly cookies, don't set VITE_API_URL - use proxy instead
// The proxy in vite.config.ts forwards /api/* to http://localhost:8000
export const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export const adminApi: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
  withCredentials: true, // Required for httpOnly cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// No need to manually add Authorization header - httpOnly cookies are sent automatically
adminApi.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  return config;
});

adminApi.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    // Don't handle 401 here - let components handle auth errors
    return Promise.reject(error);
  }
);
