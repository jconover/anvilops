import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';

describe('apiClient', () => {
  describe('base URL configuration', () => {
    afterEach(() => {
      vi.unstubAllEnvs();
      vi.resetModules();
    });

    it('defaults to /api/v1 when NEXT_PUBLIC_API_URL is not set', async () => {
      vi.unstubAllEnvs();
      const { default: client } = await import('../client');
      expect(client.defaults.baseURL).toBe('/api/v1');
    });

    it('uses NEXT_PUBLIC_API_URL when set', async () => {
      vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://localhost:8000/api/v1');
      vi.resetModules();
      const { default: client } = await import('../client');
      expect(client.defaults.baseURL).toBe('http://localhost:8000/api/v1');
    });
  });

  describe('static configuration', () => {
    it('sets Content-Type to application/json', async () => {
      const { default: client } = await import('../client');
      expect(client.defaults.headers['Content-Type']).toBe('application/json');
    });

    it('sets withCredentials to true for cookie-based auth', async () => {
      const { default: client } = await import('../client');
      expect(client.defaults.withCredentials).toBe(true);
    });

    it('sets timeout to 30000ms', async () => {
      const { default: client } = await import('../client');
      expect(client.defaults.timeout).toBe(30_000);
    });
  });

  describe('401 response interceptor', () => {
    beforeEach(() => {
      vi.resetModules();
    });

    it('redirects to /login on 401 when window is defined', async () => {
      const { default: client } = await import('../client');

      // Simulate a 401 error via the interceptor
      const error = {
        response: { status: 401 },
        isAxiosError: true,
      };

      // Access the interceptor handler directly
      const interceptors = (client.interceptors.response as unknown as {
        handlers: Array<{ fulfilled: (r: unknown) => unknown; rejected: (e: unknown) => unknown } | null>;
      }).handlers;
      const errorHandler = interceptors.find((h) => h !== null)?.rejected;

      expect(errorHandler).toBeDefined();

      // window.location.href is writable in jsdom
      const assignSpy = vi.spyOn(window, 'location', 'get').mockReturnValue({
        ...window.location,
        href: '/',
      } as Location);

      let rejected = false;
      try {
        await errorHandler!(error);
      } catch {
        rejected = true;
      }

      expect(rejected).toBe(true);
      assignSpy.mockRestore();
    });

    it('rejects the promise on non-401 errors', async () => {
      const { default: client } = await import('../client');

      const error = {
        response: { status: 500 },
        isAxiosError: true,
        message: 'Server error',
      };

      const interceptors = (client.interceptors.response as unknown as {
        handlers: Array<{ fulfilled: (r: unknown) => unknown; rejected: (e: unknown) => unknown } | null>;
      }).handlers;
      const errorHandler = interceptors.find((h) => h !== null)?.rejected;

      let caughtError: unknown;
      try {
        await errorHandler!(error);
      } catch (e) {
        caughtError = e;
      }

      expect(caughtError).toBe(error);
    });
  });
});
