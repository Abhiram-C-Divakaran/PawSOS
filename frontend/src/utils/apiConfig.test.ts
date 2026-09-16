import { describe, it, expect } from 'vitest';
import { resolveApiBaseUrl, DEFAULT_API_BASE_URL } from './apiConfig';

describe('resolveApiBaseUrl', () => {
  it('returns canonical /api/v1 URL untouched when provided correctly', () => {
    const input = 'https://pawreach-api.onrender.com/api/v1';
    expect(resolveApiBaseUrl(input)).toBe('https://pawreach-api.onrender.com/api/v1');
  });

  it('safely strips trailing slashes from full /api/v1 URLs', () => {
    const input = 'https://pawreach-api.onrender.com/api/v1/';
    expect(resolveApiBaseUrl(input)).toBe('https://pawreach-api.onrender.com/api/v1');
  });

  it('safely appends /api/v1 to domain-only URLs', () => {
    const input = 'https://pawreach-api.onrender.com';
    expect(resolveApiBaseUrl(input)).toBe('https://pawreach-api.onrender.com/api/v1');
  });

  it('safely appends /api/v1 to domain URLs with trailing slash', () => {
    const input = 'https://pawreach-api.onrender.com/';
    expect(resolveApiBaseUrl(input)).toBe('https://pawreach-api.onrender.com/api/v1');
  });

  it('prevents duplicate /api/v1/api/v1 in accidentally doubled paths', () => {
    const input = 'https://pawreach-api.onrender.com/api/v1/api/v1';
    expect(resolveApiBaseUrl(input)).toBe('https://pawreach-api.onrender.com/api/v1');
  });

  it('falls back to default localhost URL in non-production mode when unconfigured', () => {
    expect(resolveApiBaseUrl(undefined, false)).toBe(DEFAULT_API_BASE_URL);
    expect(resolveApiBaseUrl('', false)).toBe(DEFAULT_API_BASE_URL);
    expect(resolveApiBaseUrl(null, false)).toBe(DEFAULT_API_BASE_URL);
  });

  it('throws an error in production builds when VITE_API_BASE_URL is missing', () => {
    expect(() => resolveApiBaseUrl(undefined, true)).toThrowError(
      /VITE_API_BASE_URL environment variable is required/
    );
    expect(() => resolveApiBaseUrl('', true)).toThrowError(
      /VITE_API_BASE_URL environment variable is required/
    );
  });

  it('rejects malformed URLs', () => {
    expect(() => resolveApiBaseUrl('not-a-valid-url')).toThrowError(/Invalid VITE_API_BASE_URL/);
    expect(() => resolveApiBaseUrl('htt p://broken')).toThrowError(/Invalid VITE_API_BASE_URL/);
  });

  it('rejects non-HTTP/HTTPS protocols', () => {
    expect(() => resolveApiBaseUrl('ftp://files.pawreach.org/api/v1')).toThrowError(
      /Only HTTP and HTTPS are allowed/
    );
    expect(() => resolveApiBaseUrl('javascript:alert(1)')).toThrowError(
      /Only HTTP and HTTPS are allowed/
    );
  });

  it('rejects insecure HTTP in production builds for non-localhost hosts', () => {
    expect(() => resolveApiBaseUrl('http://pawreach-api.onrender.com', true)).toThrowError(
      /Insecure HTTP protocol is forbidden in production/
    );
  });

  it('permits HTTP for localhost in production testing modes', () => {
    expect(resolveApiBaseUrl('http://localhost:8000', true)).toBe('http://localhost:8000/api/v1');
    expect(resolveApiBaseUrl('http://127.0.0.1:8000', true)).toBe('http://127.0.0.1:8000/api/v1');
  });
});
