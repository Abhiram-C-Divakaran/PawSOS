# Changelog

All notable changes to **PawReach (PawSOS)** are documented in this file.

## [1.0.0] - 2026-09-20

### Added
- **Real External AI Triage Provider (`GeminiVisionTriageProvider`)**: Implemented production-grade multimodal vision urgency triage (`backend/app/ai/gemini.py`) behind `VisionTriageProvider` using Google Gemini Vision API over HTTPS (`httpx`) with header-only API key authentication (`x-goog-api-key`), Pillow image verification, strict socket timeouts, error sanitization, and zero PII/GPS/case-ID transmission.
- **Inactive Device Token Cleanup Endpoint**: Added `DELETE /api/v1/notifications/devices/inactive/cleanup` and `cleanupRevokedDeviceTokens()` client helper to purge deactivated or revoked push tokens for the current user.
- **Safe Notification Deep-Linking**: Added `sanitizeNotificationRoute()` in both the background service worker (`frontend/public/firebase-messaging-sw.js`) and client (`frontend/src/services/firebase.ts`) to block external URLs, protocol-relative URLs, and script schemes.
- **Responsive Mobile Navigation**: Added accessible mobile navigation drawer, skip-to-content link, and ARIA dialog/label semantics across Citizen, Rescuer, Veterinarian, Foster, and NGO screens.
- **PWA Manifest & Service Worker Polish (Phase 3C)**: Added installable PWA manifest (`manifest.json`), SVG app icons (`192x192`, `512x512`), Apple web-app meta tags, and Firebase service worker registration.
- **Authenticated Staging Pilot & Credential Rotation**: Added operator-controlled credential rotation (`backend/scripts/rotate_staging_credentials.py`, `.github/workflows/staging-rotate-credentials.yml`), fixture reconciliation (`backend/scripts/seed_staging.py`), and Render cold-start wake-up retry handling in `scripts/staging_authenticated_pilot.py`.

### Fixed
- **Cross-User & Concurrent Device Token Registration**: Updated `POST /api/v1/notifications/devices` to deduplicate by global `DeviceToken.token` unique constraint with `IntegrityError` recovery so shared browsers across accounts never trigger HTTP 500 errors.
- **Invalid FCM Token Deactivation**: Enhanced `NotificationService._send_fcm` to automatically deactivate tokens returning `InvalidArgumentError` in addition to `UnregisteredError` and `SenderIdMismatchError`.
- **NGO Overview Map & Notification Payload Handling**: Guarded Leaflet marker creation in `NGOOverview.tsx` when `NGOCaseSummaryResponse` omits coordinates for discovery privacy, and fixed `NotificationListResponse` (`{ items, unread_count }`) parsing.
- **Rescue Report Step 5 Photo Preview**: Fixed review step in `ReportRescue.tsx` to display `photoPreview || photoUrl` so private S3 storage keys (`uploads/...`) render the local preview cleanly prior to submission.
- **Login Redirect & Registration Feedback**: Updated `Login.tsx` to display registration completion state messages and honor sanitized `?redirect=` query parameters from the adoption flow.

---

## [0.9.0] - 2026-09-18 (Phase 3A & Phase 3B)

### Added
- **Phase 3B Hybrid AI-Assisted Visual Triage**: Introduced `VisionTriageProvider`, `HybridTriageFusionEngine` (enforcing the non-downgrade safety invariant), `TriageAssessment` audit table, `GET /api/v1/rescues/{case_id}/triage`, `POST /api/v1/rescues/{case_id}/triage/retry`, and `TriageAdvisoryCard`.
- **Phase 3A Foster & Adoption Continuum**: Implemented caregiver profiles, NGO foster home verification, deterministic foster matching, daily care logs, public adoption catalog, citizen adoption applications, visit scheduling, and transactional adoption approval cascades.
- **Single-Winner Dispatch & Discovery Privacy Closure**: Enforced active `PENDING` dispatch offer verification on rescue claims, atomic NGO case claiming (`POST /api/v1/ngo/cases/{case_id}/claim`), and coordinate/PII masking on unassigned discovery endpoints.

---

## [0.8.0] - 2026-09-16 (Phase 2.9 Live Staging & Security Closure)

### Added
- **Zero-Cost Cloud Staging Architecture**: Deployed combined FastAPI + Celery solo worker + Celery Beat supervisor (`scripts/start_free_render.sh`) on Render Free Web Service with Supabase PostgreSQL/PostGIS, Supabase Private S3 Storage, and Upstash Redis over TLS (`rediss://`).
- **Private Evidence Media Security**: Enforced canonical S3 object keys and object-level authorized presigned URL generation (`GET /api/v1/rescues/{case_id}/images/{image_id}/access`).
- **Stateful JWT Session Revocation**: Added `RefreshSession` (`jti`) tracking with token rotation, replay detection, and global session invalidation (`POST /api/v1/auth/logout-all`).
