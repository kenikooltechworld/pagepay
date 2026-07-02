import axios from 'axios';
import type { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';

// When using httpOnly cookies, don't set VITE_API_URL - use proxy instead
// The proxy in vite.config.ts forwards /api/* to http://localhost:8000
export const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

export const adminApi: AxiosInstance = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
  withCredentials: true, // Required for httpOnly cookies
});

// No need to manually add Authorization header - httpOnly cookies are sent automatically
adminApi.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  return config;
});

adminApi.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      // Clear any client-side auth state
      localStorage.removeItem('admin_token'); // Clean up legacy token if exists
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
