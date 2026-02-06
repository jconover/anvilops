/**
 * Axios-based API client for the AnvilOps FastAPI backend.
 *
 * - Base URL is read from NEXT_PUBLIC_API_URL env var; falls back to "/api/v1".
 * - Automatically attaches the auth token from localStorage on every request.
 * - On 401 responses, clears the stored token and redirects to /login.
 */

import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
});

// ---------------------------------------------------------------------------
// Request interceptor: attach auth token
// ---------------------------------------------------------------------------

apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    if (typeof window !== 'undefined') {
      const token = localStorage.getItem('anvilops_token');
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error: AxiosError) => Promise.reject(error),
);

// ---------------------------------------------------------------------------
// Response interceptor: centralised error handling
// ---------------------------------------------------------------------------

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // On 401 Unauthorized, clear stored credentials and redirect to login.
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('anvilops_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default apiClient;
