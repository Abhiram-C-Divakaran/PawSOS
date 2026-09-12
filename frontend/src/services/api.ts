import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { formatApiError } from '../utils/error';

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

const api = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true,
});

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (token: string) => void;
  reject: (error: any) => void;
}> = [];

const processQueue = (error: any, token: string | null = null) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else if (token) {
      prom.resolve(token);
    }
  });
  failedQueue = [];
};

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token');
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    // Normalize structured error response bodies to ensure clean string messages
    if (error.response?.data && typeof error.response.data === 'object') {
      const data: any = error.response.data;
      if (data.detail && typeof data.detail === 'object') {
        data.detail = formatApiError(error);
      }
    }

    const originalRequest = error.config as InternalAxiosRequestConfig & { _retry?: boolean };

    // Do not attempt refresh on login or refresh endpoints
    const url = originalRequest?.url || '';
    if (url.includes('/auth/login') || url.includes('/auth/refresh')) {
      return Promise.reject(error);
    }

    if (error.response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({
            resolve: (token: string) => {
              if (originalRequest.headers) {
                originalRequest.headers.Authorization = `Bearer ${token}`;
              }
              resolve(api(originalRequest));
            },
            reject: (err: any) => {
              reject(err);
            },
          });
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      const refreshToken = localStorage.getItem('refresh_token');

      try {
        const response = await axios.post(
          `${baseURL}/auth/refresh`,
          refreshToken ? { refresh_token: refreshToken } : {},
          { withCredentials: true }
        );

        const { access_token, refresh_token: newRefreshToken } = response.data;
        localStorage.setItem('access_token', access_token);
        if (newRefreshToken) {
          localStorage.setItem('refresh_token', newRefreshToken);
        }

        api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`;
        if (originalRequest.headers) {
          originalRequest.headers.Authorization = `Bearer ${access_token}`;
        }

        processQueue(null, access_token);
        return api(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr, null);
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
          window.location.href = `/login?redirect=${encodeURIComponent(window.location.pathname)}`;
        }
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

export { formatApiError };
export default api;
