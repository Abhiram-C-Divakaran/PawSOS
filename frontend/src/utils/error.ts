/**
 * PawReach Frontend Error Utility
 * Safely extracts user-friendly error strings from API responses, Axios errors, or generic exceptions.
 * Guaranteed to NEVER return an object, array, or null, preventing React "Objects are not valid as a React child" crashes.
 */

export function formatApiError(
  err: unknown,
  fallback: string = 'An unexpected error occurred. Please try again.'
): string {
  if (!err) return fallback;

  // 1. Direct string
  if (typeof err === 'string') {
    const trimmed = err.trim();
    return trimmed.length > 0 ? trimmed : fallback;
  }

  const anyErr = err as any;

  // 2. Axios / Fetch response error payload
  const responseData = anyErr?.response?.data;
  if (responseData) {
    // If responseData is a direct string
    if (typeof responseData === 'string' && responseData.trim().length > 0) {
      return responseData.trim();
    }

    // Check FastAPI standard 'detail' field
    const detail = responseData.detail;
    if (typeof detail === 'string' && detail.trim().length > 0) {
      return detail.trim();
    }

    if (detail && typeof detail === 'object') {
      // BaseAPIException structure: { success: false, error: { code, message } }
      if (typeof detail.error?.message === 'string' && detail.error.message.trim().length > 0) {
        return detail.error.message.trim();
      }
      if (typeof detail.message === 'string' && detail.message.trim().length > 0) {
        return detail.message.trim();
      }
      if (typeof detail.error === 'string' && detail.error.trim().length > 0) {
        return detail.error.trim();
      }
      // Pydantic / FastAPI 422 validation error array: [{ loc: [...], msg: "..." }]
      if (Array.isArray(detail)) {
        const msgs = detail
          .map((item: any) => {
            if (typeof item === 'string') return item.trim();
            if (item?.msg) {
              const field = Array.isArray(item.loc) ? item.loc[item.loc.length - 1] : null;
              return field && field !== 'body' ? `${field}: ${item.msg}` : item.msg;
            }
            if (item?.message) return item.message;
            return null;
          })
          .filter(Boolean);
        if (msgs.length > 0) {
          return msgs.join(', ');
        }
      }
    }

    // Direct root error/message fields in responseData
    if (typeof responseData.error?.message === 'string' && responseData.error.message.trim().length > 0) {
      return responseData.error.message.trim();
    }
    if (typeof responseData.message === 'string' && responseData.message.trim().length > 0) {
      return responseData.message.trim();
    }
    if (typeof responseData.error === 'string' && responseData.error.trim().length > 0) {
      return responseData.error.trim();
    }
  }

  // 3. Raw object with { success, error: { message } } or { message }
  if (typeof anyErr.error?.message === 'string' && anyErr.error.message.trim().length > 0) {
    return anyErr.error.message.trim();
  }
  if (typeof anyErr.message === 'string' && anyErr.message.trim().length > 0) {
    return anyErr.message.trim();
  }

  return fallback;
}
