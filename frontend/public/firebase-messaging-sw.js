// Firebase Cloud Messaging Service Worker for PawReach Background Notifications
/* eslint-disable no-restricted-globals */
importScripts('https://www.gstatic.com/firebasejs/10.8.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/10.8.0/firebase-messaging-compat.js');

function sanitizeNotificationRoute(rawRoute, fallbackCaseId) {
  const safeCaseId =
    typeof fallbackCaseId === 'string' && /^[a-zA-Z0-9-]+$/.test(fallbackCaseId.trim())
      ? fallbackCaseId.trim()
      : '';
  const candidate =
    typeof rawRoute === 'string' && rawRoute.trim()
      ? rawRoute.trim()
      : safeCaseId
      ? `/cases/${safeCaseId}`
      : '/';

  if (
    !candidate.startsWith('/') ||
    candidate.startsWith('//') ||
    /[\r\n\\]/.test(candidate) ||
    /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(candidate)
  ) {
    return '/';
  }
  return candidate;
}

// Parse URL search params or fallback to self configuration
const searchParams = new URL(location).searchParams;
const firebaseConfig = {
  apiKey: searchParams.get('apiKey') || '',
  authDomain: searchParams.get('authDomain') || '',
  projectId: searchParams.get('projectId') || '',
  storageBucket: searchParams.get('storageBucket') || '',
  messagingSenderId: searchParams.get('messagingSenderId') || '',
  appId: searchParams.get('appId') || '',
};

if (firebaseConfig.apiKey && firebaseConfig.projectId) {
  firebase.initializeApp(firebaseConfig);
  const messaging = firebase.messaging();

  messaging.onBackgroundMessage((payload) => {
    const title = payload.notification?.title || payload.data?.title || '🐾 PawReach Emergency Alert';
    const body = payload.notification?.body || payload.data?.body || payload.data?.message || 'New dispatch or case update.';
    const route = sanitizeNotificationRoute(payload.data?.route, payload.data?.case_id);

    const notificationOptions = {
      body,
      icon: '/icons/icon-192.svg',
      badge: '/icons/icon-192.svg',
      data: {
        ...payload.data,
        route,
      },
      tag: payload.data?.offer_id || payload.data?.case_id || 'pawreach-alert',
      renotify: true,
      requireInteraction: true,
    };

    self.registration.showNotification(title, notificationOptions);
  });
}

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const route = sanitizeNotificationRoute(
    event.notification.data?.route,
    event.notification.data?.case_id
  );

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
      // If PawReach window is open, focus and navigate it safely within same origin
      for (const client of windowClients) {
        if (client.url && 'focus' in client) {
          if ('navigate' in client) {
            client.navigate(route);
          }
          return client.focus();
        }
      }
      // Otherwise open new window at safe internal route
      if (clients.openWindow) {
        return clients.openWindow(route);
      }
    })
  );
});
