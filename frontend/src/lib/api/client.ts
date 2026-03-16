/**
 * Axios-based API client for the AnvilOps FastAPI backend.
 *
 * - Base URL is read from NEXT_PUBLIC_API_URL env var; falls back to "/api/v1".
 * - Auth is handled via HttpOnly cookie (`anvilops_token`) sent automatically by
 *   the browser on every request. No manual token attachment is needed.
 * - `withCredentials: true` ensures cookies are included on cross-origin requests.
 * - On 401 responses, redirects to /login and lets the server clear the cookie.
 */

import axios, { type AxiosError } from 'axios';

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_URL || '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30_000,
  withCredentials: true,
});

// ---------------------------------------------------------------------------
// Response interceptor: centralised error handling
// ---------------------------------------------------------------------------

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // On 401 Unauthorized, redirect to login. The server is responsible for
    // clearing the HttpOnly cookie — JS cannot clear it directly.
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      window.location.href = '/login';
    }
    return Promise.reject(error);
  },
);

export default apiClient;
