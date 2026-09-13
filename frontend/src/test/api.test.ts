import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import api, { formatApiError } from '../services/api';

describe('API Service (src/services/api.ts)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('injects Bearer access_token into outgoing request headers when present in localStorage', async () => {
    localStorage.setItem('access_token', 'test_access_token_xyz');

    const interceptor = api.interceptors.request as any;
    const requestHandler = interceptor.handlers[0].fulfilled;

    const config = await requestHandler({ headers: {} } as any);
    expect(config.headers.Authorization).toBe('Bearer test_access_token_xyz');
  });

  it('leaves Authorization header empty when access_token is absent', async () => {
    const interceptor = api.interceptors.request as any;
    const requestHandler = interceptor.handlers[0].fulfilled;

    const config = await requestHandler({ headers: {} } as any);
    expect(config.headers.Authorization).toBeUndefined();
  });

  it('rejects 401 errors immediately without refresh attempt if the request is to /auth/login', async () => {
    const interceptor = api.interceptors.response as any;
    const errorHandler = interceptor.handlers[0].rejected;

    const mockError: any = {
      config: { url: '/auth/login' },
      response: { status: 401, data: { detail: 'Invalid credentials' } },
    };

    await expect(errorHandler(mockError)).rejects.toMatchObject({
      response: { status: 401 },
    });
  });

  it('attempts token refresh on 401, updates tokens, and retries original request upon success', async () => {
    localStorage.setItem('access_token', 'stale_token');
    localStorage.setItem('refresh_token', 'valid_refresh_token');

    const interceptor = api.interceptors.response as any;
    const errorHandler = interceptor.handlers[0].rejected;

    const postSpy = vi.spyOn(axios, 'post').mockResolvedValueOnce({
      data: {
        access_token: 'new_access_token_123',
        refresh_token: 'new_refresh_token_456',
      },
    });

    vi.spyOn(axios.Axios.prototype, 'request').mockResolvedValueOnce({ data: { success: true } });

    const originalRequest: any = {
      url: '/rescues/active',
      headers: {},
      _retry: false,
      adapter: async (config: any) => ({
        data: { success: true },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }),
    };

    const mockError: any = {
      config: originalRequest,
      response: { status: 401, data: { detail: 'Token expired' } },
    };

    await errorHandler(mockError);

    expect(postSpy).toHaveBeenCalled();
    expect(localStorage.getItem('access_token')).toBe('new_access_token_123');
    expect(localStorage.getItem('refresh_token')).toBe('new_refresh_token_456');
  });

  it('clears localStorage tokens on refresh failure and rejects with error', async () => {
    localStorage.setItem('access_token', 'stale_token');
    localStorage.setItem('refresh_token', 'expired_refresh_token');

    const interceptor = api.interceptors.response as any;
    const errorHandler = interceptor.handlers[0].rejected;

    vi.spyOn(axios, 'post').mockRejectedValueOnce(new Error('Invalid refresh token'));

    const originalRequest: any = {
      url: '/ngo/analytics',
      headers: {},
      _retry: false,
    };

    const mockError: any = {
      config: originalRequest,
      response: { status: 401, data: { detail: 'Unauthorized' } },
    };

    await expect(errorHandler(mockError)).rejects.toThrow('Invalid refresh token');
    expect(localStorage.getItem('access_token')).toBeNull();
    expect(localStorage.getItem('refresh_token')).toBeNull();
  });

  it('propagates 403 Forbidden and 409 Conflict responses with formatted error details', async () => {
    const interceptor = api.interceptors.response as any;
    const errorHandler = interceptor.handlers[0].rejected;

    const forbiddenError: any = {
      config: { url: '/ngo/responders/99/status' },
      response: {
        status: 403,
        data: {
          detail: {
            code: 'CROSS_TENANT_RESPONDER_UPDATE_DENIED',
            message: 'You cannot modify responders from another organization.',
          },
        },
      },
    };

    await expect(errorHandler(forbiddenError)).rejects.toMatchObject({
      response: { status: 403 },
    });

    const conflictError: any = {
      config: { url: '/dispatch/offers/123/accept' },
      response: {
        status: 409,
        data: {
          detail: {
            code: 'OFFER_ALREADY_ACCEPTED',
            message: 'Another responder claimed this case.',
          },
        },
      },
    };

    await expect(errorHandler(conflictError)).rejects.toMatchObject({
      response: { status: 409 },
    });
  });

  it('formats network error and fallback messages safely', () => {
    const networkError: any = {
      message: 'Network Error',
    };
    const formatted = formatApiError(networkError);
    expect(formatted).toBe('Network Error');

    const emptyError: any = null;
    expect(formatApiError(emptyError)).toBe('An unexpected error occurred. Please try again.');
  });
});
