import { initializeApp, getApps, type FirebaseApp } from 'firebase/app';
import { getMessaging, getToken, onMessage, isSupported, type Messaging } from 'firebase/messaging';
import api from './api';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
};

let app: FirebaseApp | null = null;
let messaging: Messaging | null = null;

export const isFirebaseConfigured = (): boolean => {
  return Boolean(
    firebaseConfig.apiKey &&
    firebaseConfig.projectId &&
    firebaseConfig.messagingSenderId
  );
};

export const initializeFirebase = async (): Promise<Messaging | null> => {
  if (typeof window === 'undefined') return null;

  try {
    const supported = await isSupported().catch(() => false);
    if (!supported || !isFirebaseConfigured()) {
      return null;
    }

    if (!getApps().length) {
      app = initializeApp(firebaseConfig);
    } else {
      app = getApps()[0];
    }

    if (!messaging) {
      messaging = getMessaging(app);
    }
    return messaging;
  } catch (err) {
    console.warn('Firebase initialization error:', err);
    return null;
  }
};

export const requestNotificationPermission = async (): Promise<NotificationPermission | 'unsupported'> => {
  if (typeof window === 'undefined' || !('Notification' in window)) {
    return 'unsupported';
  }
  try {
    const permission = await Notification.requestPermission();
    return permission;
  } catch (err) {
    console.error('Error requesting notification permission:', err);
    return 'denied';
  }
};

export const getFCMToken = async (): Promise<string | null> => {
  try {
    const msg = await initializeFirebase();
    if (!msg) return null;

    const vapidKey = import.meta.env.VITE_FIREBASE_VAPID_KEY || undefined;
    const token = await getToken(msg, { vapidKey });
    return token;
  } catch (err) {
    console.warn('Could not retrieve FCM token:', err);
    return null;
  }
};

export const registerDeviceTokenWithBackend = async (
  token: string,
  platform = 'WEB',
  deviceName?: string
): Promise<any> => {
  const name = deviceName || (typeof navigator !== 'undefined' ? navigator.userAgent.substring(0, 100) : 'Web Browser');
  try {
    const res = await api.post('/notifications/devices', {
      token,
      platform,
      device_name: name,
    });
    localStorage.setItem('fcm_registered_token', token);
    return res.data;
  } catch (err) {
    console.error('Failed to register device token with backend:', err);
    throw err;
  }
};

export const unregisterDeviceTokenFromBackend = async (): Promise<void> => {
  const token = localStorage.getItem('fcm_registered_token');
  if (!token) return;
  try {
    await api.delete(`/notifications/devices/${encodeURIComponent(token)}`);
    localStorage.removeItem('fcm_registered_token');
  } catch (err) {
    console.warn('Failed to unregister device token:', err);
    localStorage.removeItem('fcm_registered_token');
  }
};

export const onForegroundNotification = (
  callback: (payload: { title?: string; body?: string; data?: Record<string, any> }) => void
): (() => void) => {
  let unsubscribe = () => {};

  initializeFirebase().then((msg) => {
    if (!msg) return;
    try {
      unsubscribe = onMessage(msg, (payload) => {
        const title = payload.notification?.title || payload.data?.title || 'PawReach Alert';
        const body = payload.notification?.body || payload.data?.body || payload.data?.message || '';
        callback({ title, body, data: payload.data });
      });
    } catch (e) {
      console.warn('onMessage listener failed to attach:', e);
    }
  });

  return () => {
    unsubscribe();
  };
};
