/**
 * PawReach Frontend API Base URL Normalization & Validation.
 *
 * Canonical contract: https://<domain>/api/v1 (no trailing slash).
 * Individual Axios calls use root-relative paths starting with a slash, e.g.:
 *   /auth/login -> https://<domain>/api/v1/auth/login
 *   /rescues    -> https://<domain>/api/v1/rescues
 */

export const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1';

export function resolveApiBaseUrl(rawUrl?: string | null, isProduction: boolean = false): string {
  const trimmed = (rawUrl || '').trim();

  // If unconfigured or empty:
  if (!trimmed) {
    if (isProduction) {
      throw new Error(
        'VITE_API_BASE_URL environment variable is required in production builds.'
      );
    }
    return DEFAULT_API_BASE_URL;
  }

  // Validate URL syntax
  let parsed: URL;
  try {
    parsed = new URL(trimmed);
  } catch {
    throw new Error(
      `Invalid VITE_API_BASE_URL: "${trimmed}". Must be a valid absolute URL (e.g. https://api.pawreach.org/api/v1).`
    );
  }

  // Validate protocol
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error(
      `Invalid protocol "${parsed.protocol}" in VITE_API_BASE_URL. Only HTTP and HTTPS are allowed.`
    );
  }

  // In production builds, forbid insecure HTTP unless targeting localhost
  if (
    isProduction &&
    parsed.protocol === 'http:' &&
    parsed.hostname !== 'localhost' &&
    parsed.hostname !== '127.0.0.1'
  ) {
    throw new Error(
      `Insecure HTTP protocol is forbidden in production: "${trimmed}". Staging and production require HTTPS.`
    );
  }

  // Normalize pathname: strip trailing slashes
  let pathname = parsed.pathname.replace(/\/+$/, '');

  // Strip duplicate /api/v1 if inadvertently appended multiple times
  while (pathname.endsWith('/api/v1/api/v1')) {
    pathname = pathname.slice(0, -'/api/v1'.length);
  }

  // Ensure pathname ends with /api/v1
  if (!pathname.endsWith('/api/v1')) {
    if (pathname === '' || pathname === '/') {
      pathname = '/api/v1';
    } else {
      pathname = `${pathname}/api/v1`;
    }
  }

  return `${parsed.origin}${pathname}`;
}
