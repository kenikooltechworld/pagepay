import axios from 'axios';
import type { AxiosInstance, AxiosError, InternalAxiosRequestConfig, AxiosResponse } from 'axios';

// Production: use Render deployment URL
export const API_BASE = 'https://pagepay.onrender.com/api/v1';

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
