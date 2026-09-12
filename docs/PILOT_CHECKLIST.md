# PawReach Pilot Checklist: MVP Phase 2.5 Staging & Operational Readiness

This checklist must be executed and validated in the staging environment before opening the pilot to external responders and partner veterinary clinics.

---

## 1. Authentication & Security
- [ ] Citizen registration generates account with strictly `CITIZEN` role.
- [ ] Login sets HttpOnly, Secure, SameSite cookie (`refresh_token`).
- [ ] In production/staging, the JSON login response does not leak the refresh token.
- [ ] Token refresh generates new access token and performs atomic session rotation.
- [ ] Single-device logout (`POST /api/v1/auth/logout`) revokes current refresh session in database.
- [ ] Multi-device logout (`POST /api/v1/auth/logout-all`) revokes all active user sessions.
- [ ] Reusing a revoked refresh token is immediately rejected with `401 Unauthorized`.

---

## 2. Citizen Rescue Reporting & GPS
- [ ] Citizen reports injured animal with real camera photo and GPS coordinates.
- [ ] Pillow image optimization automatically compresses and resizes photos exceeding 2048px.
- [ ] EXIF metadata is stripped from uploaded evidence images.
- [ ] Rule-based triage assigns correct triage score and priority (`CRITICAL`, `URGENT`, `MODERATE`, `GENERAL`).
- [ ] Case transitions to `SEARCHING_RESPONDER` upon submission of critical/urgent cases.

---

## 3. Background Dispatch & Radius Escalation (Celery + Redis)
- [ ] Celery worker and Celery beat process background queues.
- [ ] Redis heartbeat key `celery_worker_heartbeat` updates every 10 seconds.
- [ ] Initial dispatch searches 5 km radius, excludes unresponsive/rejected responders.
- [ ] Stale offers expire automatically via background worker every 20 seconds without frontend interaction.
- [ ] Radius expands deterministically: 5 km -> 10 km -> 20 km -> 40 km.
- [ ] When all 4 radius levels are exhausted without acceptance, case transitions to `UNRESOLVED`.
- [ ] Urgent failure notification is sent to NGO Admins and Super Admins.

---

## 4. Web Push & In-App Notifications (Firebase)
- [ ] Non-intrusive permission CTA banner ("Enable rescue alerts") renders for authenticated users.
- [ ] Browser permission prompt triggered only upon user clicking "Enable Alerts".
- [ ] Device token registered with backend (`POST /api/v1/notifications/devices`) with platform `WEB`.
- [ ] Background push notifications displayed by service worker (`firebase-messaging-sw.js`).
- [ ] Clicking notification focuses/navigates browser to destination route (`/rescuer` or `/cases/:id`).
- [ ] In-app toast banner appears when notification is received while actively using the site.
- [ ] On logout, device token registration is cleanly deactivated.

---

## 5. Multi-Tenant Scoping & Permissions
- [ ] NGO Admin Org A cannot view Org B rescue cases (`403 Forbidden`).
- [ ] NGO Admin Org A cannot view Org B responders or facilities.
- [ ] NGO Overview KPIs aggregate only metrics for the authorized organization.
- [ ] Veterinarian assigned to Facility A cannot view or treat cases assigned to Facility B (`403 Forbidden`).
- [ ] Super Admin maintains global visibility across all organizations and facilities.

---

## 6. Mobile & Network Resilience
- [ ] Mobile responsive layout verified at 390px, 430px, and 768px viewports.
- [ ] Dispatch alert card and countdown timer clearly legible on mobile screens.
- [ ] Network throttling (Slow 3G) tested: double-click prevention on report submission and offer acceptance.
- [ ] Offline recovery: reconnecting resumes polling and synchronization.
