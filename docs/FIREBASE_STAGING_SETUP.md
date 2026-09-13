# Firebase Cloud Messaging (FCM) — Staging Setup & Operational Guide
**PawReach MVP Phase 2.9 — Staging Configuration**

This document details the configuration, security, device lifecycle, and verification procedures for Firebase Cloud Messaging (FCM) web push notifications in the PawReach staging environment.

---

## 1. Architecture Overview

PawReach uses Firebase Cloud Messaging (via the official `firebase-admin` Python SDK on the backend and Firebase Web SDK on the frontend PWA) to deliver real-time push alerts to field responders, NGO dispatchers, and veterinary staff.

```
+-------------------+       REST (FastAPI)       +-----------------------+
|  Frontend PWA     | -------------------------> |  Backend API          |
|  (Service Worker) |                            |  (NotificationService)|
+-------------------+                            +-----------------------+
         ^                                                   |
         | Push Notification                                 | Push Dispatch
         |                                                   v
+------------------------------------------------------------------------+
|                   Firebase Cloud Messaging (FCM)                      |
+------------------------------------------------------------------------+
```

---

## 2. Staging Firebase Project Setup

### Step 1: Create or Select Firebase Project
1. Navigate to the [Firebase Console](https://console.firebase.google.com/).
2. Create a new project named `pawreach-staging` (or select existing staging project).
3. Disable Google Analytics (optional for staging) to simplify setup.

### Step 2: Generate Service Account Key (Backend)
1. Go to **Project Settings** (gear icon) -> **Service accounts**.
2. Select **Firebase Admin SDK** -> **Python**.
3. Click **Generate new private key**, then confirm **Generate key**.
4. A JSON credential file is downloaded (e.g., `pawreach-staging-firebase-adminsdk-xxxxx.json`).

### Step 3: Secure Service Account Storage
> [!CAUTION]
> NEVER commit this JSON file to version control. `.gitignore` strictly blocks `firebase-adminsdk*.json` and `*service-account*.json`.

- **Local / Docker Staging**: Store at `backend/secrets/firebase-adminsdk.json` (ensure `backend/secrets/` is ignored).
- **Render / Cloud Deployment**: Provide the file via **Secret Files** mount:
  - Path: `/etc/secrets/firebase-admin.json`
  - In `render.yaml` or Render dashboard, create a Secret File pointing to this path.

### Step 4: Generate Web Push VAPID Key Pair (Frontend)
1. In Firebase Console, go to **Project Settings** -> **Cloud Messaging** tab.
2. Scroll to **Web configuration** -> **Web Push certificates**.
3. Click **Generate key pair**.
4. Copy the public key (VAPID Key). This is your `VITE_FIREBASE_VAPID_KEY`.

---

## 3. Environment Variables Configuration

### Backend (`backend/.env`)
```bash
# Absolute or container path to the service account JSON
FIREBASE_CREDENTIALS_PATH=/etc/secrets/firebase-admin.json

# Firebase project ID matching the credential file
FIREBASE_PROJECT_ID=pawreach-staging
```

### Frontend (`frontend/.env.staging` or `frontend/.env.production`)
```bash
VITE_FIREBASE_API_KEY="AIzaSy..."
VITE_FIREBASE_AUTH_DOMAIN="pawreach-staging.firebaseapp.com"
VITE_FIREBASE_PROJECT_ID="pawreach-staging"
VITE_FIREBASE_STORAGE_BUCKET="pawreach-staging.appspot.com"
VITE_FIREBASE_MESSAGING_SENDER_ID="123456789012"
VITE_FIREBASE_APP_ID="1:123456789012:web:abcdef..."
VITE_FIREBASE_VAPID_KEY="BEl...your_vapid_public_key..."
```

---

## 4. Frontend Service Worker & Token Registration Lifecycle

### Service Worker Scope
- The browser service worker is located at `frontend/public/firebase-messaging-sw.js` and registered at root scope (`/`).
- It handles background push events when the PWA browser tab is inactive or closed:
  ```javascript
  // Handles background messages from FCM
  messaging.onBackgroundMessage((payload) => {
    const notificationTitle = payload.notification.title;
    const notificationOptions = {
      body: payload.notification.body,
      icon: '/icon-192.png',
      badge: '/badge-72.png',
      data: payload.data,
    };
    self.registration.showNotification(notificationTitle, notificationOptions);
  });
  ```

### Device Token Registration API
When a user logs in and grants notification permission:
1. The frontend requests browser permission (`Notification.requestPermission()`).
2. If granted, Firebase SDK generates an FCM registration token.
3. The frontend registers the token with the backend:
   ```http
   POST /api/v1/notifications/devices
   Authorization: Bearer <JWT_ACCESS_TOKEN>
   Content-Type: application/json

   {
     "token": "eX_ample_fcm_device_token...",
     "device_type": "web"
   }
   ```
4. The backend stores the token in the `device_tokens` table with `is_active = True`.

### Inactive Token & Error Deactivation Lifecycle
When sending push notifications, FCM may report that a token is stale, uninstalled, or revoked:
- If FCM returns `messaging.UnregisteredError` or `messaging.InvalidArgumentError`:
  - The backend catches the exception in `notification_service.py`.
  - The token is automatically marked `is_active = False` in the database.
  - No further push attempts are made to that token until re-registered.

### Fallback Behavior
- If the user denies notification permission or the browser does not support push notifications, the frontend falls back to:
  - In-app notification bell polling (`GET /api/v1/notifications/`).
  - Active UI banners for incoming emergency dispatches.

---

## 5. Verification & Testing Procedures

### A. Subsystem Health Verification
Check that the backend recognizes Firebase initialization:
```bash
curl -s http://localhost:8000/api/v1/health/readiness | jq .services.firebase
# Expected output: "configured"
```

### B. Diagnostic Test Notification (UI)
1. Log in as an NGO Admin at `/ngo/settings`.
2. Scroll to the **Notification Preferences** card.
3. Click the **Send Test Push Notification** button.
4. Confirm:
   - A success banner appears in the UI.
   - The browser displays a native system notification with title `"PawReach Emergency Alert Test"`.
   - The notification bell icon badge increments by 1.

### C. Direct Backend Verification (Python Shell)
```bash
python -c "
from app.database import SessionLocal
from app.services.notification_service import notification_service

db = SessionLocal()
status = notification_service.send_push_notification(
    db=db,
    user_id=1,
    title='Staging FCM Probe',
    body='Verification of FCM connectivity from staging environment.',
    data={'type': 'SYSTEM_PROBE'}
)
print(f'Notification dispatched. Success: {status}')
"
```

---

## 6. Staging Readiness Status

| Requirement | Implementation | Status |
| :--- | :--- | :--- |
| Firebase Admin SDK integration | `app/services/notification_service.py` | Verified (Automated unit tests pass) |
| Device token lifecycle & deactivation | `app/api/routes/notifications.py` | Verified (Automated unit tests pass) |
| Timezone-aware UTC timestamps | `datetime.now(timezone.utc)` enforced | Verified |
| Readiness probe health telemetry | `GET /api/v1/health/readiness` -> `firebase: configured` | Verified |
| Staging credentials file provisioned | Operator must supply service account JSON | **Status: REQUIRES_EXTERNAL_CREDENTIALS** |
| Real device web push reception | Physical Android/iOS mobile browser test | **Status: REQUIRES_REAL_DEVICE_TEST** |
