import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as firebaseMessaging from 'firebase/messaging';
import api from '../services/api';
import {
  isFirebaseConfigured,
  initializeFirebase,
  requestNotificationPermission,
  getFCMToken,
  registerDeviceTokenWithBackend,
  unregisterDeviceTokenFromBackend,
  onForegroundNotification,
} from '../services/firebase';

vi.mock('firebase/app', () => ({
  initializeApp: vi.fn(() => ({ name: '[DEFAULT]' })),
  getApps: vi.fn(() => []),
}));

vi.mock('firebase/messaging', () => ({
  getMessaging: vi.fn(() => ({ app: { name: '[DEFAULT]' } })),
  getToken: vi.fn(),
  onMessage: vi.fn(),
  isSupported: vi.fn(),
}));

vi.mock('../services/api', () => ({
  default: {
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

describe('Firebase Service (src/services/firebase.ts)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('isFirebaseConfigured', () => {
    it('returns boolean reflecting presence of env configuration', () => {
      const result = isFirebaseConfigured();
      expect(typeof result).toBe('boolean');
    });
  });

  describe('requestNotificationPermission', () => {
    it('returns unsupported when Notification is not in window', async () => {
      const originalNotification = window.Notification;
      // @ts-ignore
      delete window.Notification;

      const res = await requestNotificationPermission();
      expect(res).toBe('unsupported');

      window.Notification = originalNotification;
    });

    it('returns granted when permission is successfully granted', async () => {
      window.Notification = {
        requestPermission: vi.fn().mockResolvedValue('granted'),
      } as any;

      const res = await requestNotificationPermission();
      expect(res).toBe('granted');
    });

    it('returns denied when permission request rejects', async () => {
      window.Notification = {
        requestPermission: vi.fn().mockRejectedValue(new Error('User dismissed')),
      } as any;

      const res = await requestNotificationPermission();
      expect(res).toBe('denied');
    });
  });

  describe('initializeFirebase', () => {
    it('returns null if isSupported resolves to false', async () => {
      vi.spyOn(firebaseMessaging, 'isSupported').mockResolvedValue(false);

      const msg = await initializeFirebase();
      expect(msg).toBeNull();
    });

    it('returns null if isSupported throws an error', async () => {
      vi.spyOn(firebaseMessaging, 'isSupported').mockRejectedValue(new Error('IndexedDB not available'));

      const msg = await initializeFirebase();
      expect(msg).toBeNull();
    });
  });

  describe('getFCMToken', () => {
    it('returns null if firebase initialization fails', async () => {
      vi.spyOn(firebaseMessaging, 'isSupported').mockResolvedValue(false);

      const token = await getFCMToken();
      expect(token).toBeNull();
    });

    it('handles errors from getToken gracefully', async () => {
      vi.spyOn(firebaseMessaging, 'isSupported').mockResolvedValue(true);
      vi.spyOn(firebaseMessaging, 'getToken').mockRejectedValue(new Error('FCM network failure'));

      const token = await getFCMToken();
      expect(token).toBeNull();
    });
  });

  describe('registerDeviceTokenWithBackend', () => {
    it('posts device token to backend and saves to localStorage', async () => {
      const mockPost = vi.spyOn(api, 'post').mockResolvedValueOnce({
        data: { id: 1, token: 'test_token_fcm_123', platform: 'WEB' },
      });

      const res = await registerDeviceTokenWithBackend('test_token_fcm_123', 'WEB', 'Chrome Mobile');

      expect(mockPost).toHaveBeenCalledWith('/notifications/devices', {
        token: 'test_token_fcm_123',
        platform: 'WEB',
        device_name: 'Chrome Mobile',
      });
      expect(localStorage.getItem('fcm_registered_token')).toBe('test_token_fcm_123');
      expect(res).toEqual({ id: 1, token: 'test_token_fcm_123', platform: 'WEB' });
    });

    it('throws error when backend registration fails', async () => {
      vi.spyOn(api, 'post').mockRejectedValueOnce(new Error('Network error'));

      await expect(registerDeviceTokenWithBackend('invalid_token')).rejects.toThrow('Network error');
      expect(localStorage.getItem('fcm_registered_token')).toBeNull();
    });
  });

  describe('unregisterDeviceTokenFromBackend', () => {
    it('does nothing if no token is saved in localStorage', async () => {
      const deleteSpy = vi.spyOn(api, 'delete');

      await unregisterDeviceTokenFromBackend();
      expect(deleteSpy).not.toHaveBeenCalled();
    });

    it('calls delete endpoint and cleans up localStorage on success', async () => {
      localStorage.setItem('fcm_registered_token', 'token_to_remove');
      const deleteSpy = vi.spyOn(api, 'delete').mockResolvedValueOnce({ data: { success: true } });

      await unregisterDeviceTokenFromBackend();

      expect(deleteSpy).toHaveBeenCalledWith('/notifications/devices/token_to_remove');
      expect(localStorage.getItem('fcm_registered_token')).toBeNull();
    });

    it('removes token from localStorage even if delete endpoint fails', async () => {
      localStorage.setItem('fcm_registered_token', 'stale_token_123');
      vi.spyOn(api, 'delete').mockRejectedValueOnce(new Error('Server error'));

      await unregisterDeviceTokenFromBackend();

      expect(localStorage.getItem('fcm_registered_token')).toBeNull();
    });
  });

  describe('onForegroundNotification', () => {
    it('returns an unsubscribe function', () => {
      const unsubscribe = onForegroundNotification(() => {});
      expect(typeof unsubscribe).toBe('function');
    });
  });
});
