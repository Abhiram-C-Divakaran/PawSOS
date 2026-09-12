import { describe, it, expect } from 'vitest';
import { formatApiError } from '../utils/error';

describe('formatApiError utility', () => {
  it('extracts message from BaseAPIException payload inside response.data.detail', () => {
    const error = {
      response: {
        status: 401,
        data: {
          detail: {
            success: false,
            error: {
              code: 'UNAUTHORIZED',
              message: 'Incorrect email/phone or password',
            },
          },
        },
      },
    };

    const result = formatApiError(error);
    expect(result).toBe('Incorrect email/phone or password');
    expect(typeof result).toBe('string');
  });

  it('extracts string from plain string response.data.detail', () => {
    const error = {
      response: {
        status: 404,
        data: {
          detail: 'Rescue case not found',
        },
      },
    };

    expect(formatApiError(error)).toBe('Rescue case not found');
  });

  it('extracts messages from FastAPI 422 validation array in response.data.detail', () => {
    const error = {
      response: {
        status: 422,
        data: {
          detail: [
            { loc: ['body', 'email'], msg: 'value is not a valid email address' },
            { loc: ['body', 'password'], msg: 'field required' },
          ],
        },
      },
    };

    const result = formatApiError(error);
    expect(result).toContain('email: value is not a valid email address');
    expect(result).toContain('password: field required');
  });

  it('extracts message from response.data root error/message', () => {
    const error = {
      response: {
        status: 400,
        data: {
          message: 'Bad payload',
        },
      },
    };

    expect(formatApiError(error)).toBe('Bad payload');
  });

  it('handles raw object with { success, error } structure directly', () => {
    const error = {
      success: false,
      error: {
        code: 'FORBIDDEN',
        message: 'Access denied to NGO console',
      },
    };

    expect(formatApiError(error)).toBe('Access denied to NGO console');
  });

  it('falls back to err.message for network errors', () => {
    const error = new Error('Network Error');
    expect(formatApiError(error)).toBe('Network Error');
  });

  it('uses provided fallback when error is empty or undefined', () => {
    expect(formatApiError(null, 'Custom fallback')).toBe('Custom fallback');
    expect(formatApiError(undefined, 'Custom fallback')).toBe('Custom fallback');
    expect(formatApiError({}, 'Custom fallback')).toBe('Custom fallback');
  });

  it('never returns an object or array (prevents React child crash)', () => {
    const weirdObjects = [
      { foo: 'bar' },
      { detail: { unknown: 123 } },
      [1, 2, 3],
      { response: { data: { detail: {} } } },
    ];

    weirdObjects.forEach((obj) => {
      const formatted = formatApiError(obj, 'Safe fallback');
      expect(typeof formatted).toBe('string');
      expect(formatted).not.toBe('[object Object]');
    });
  });
});
