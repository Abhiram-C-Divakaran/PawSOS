# PawReach Pilot Checklist: Phase 2.6 Pilot Readiness & Staging Operations

This checklist defines the sign-off criteria required before opening the PawReach pilot to real field responders, citizens, and partner veterinary clinics.

---

## Part A: Automated Verification (Local & CI Test Suite)

These checks are verified via automated CI pipelines and local command execution. All tests must pass before deploying to staging.

### 1. Backend Automated Testing & Coverage (Goal: >= 85%)
- [x] **Pytest Unit & Integration Suite**: 66 passed, 0 failures.
- [x] **Backend Coverage Bar**: 85.5% achieved across `backend/app` (2657 statements, 386 misses).
- [x] **Tenant Scoping Tests** (`test_scoping_security.py`): Cross-organization data leak prevention verified.
- [x] **NGO Analytics Tests** (`test_ngo_analytics.py`): Tenant-isolated metrics, trend calculations, outcomes, hotspots.
- [x] **NGO Organization & Settings Tests** (`test_ngo_organization.py`, `test_ngo_settings.py`): Profile editing, immutable field enforcement, audit log generation, notification preferences.
- [x] **Storage & Image Pipeline Tests** (`test_storage_service.py`): Pillow EXIF orientation, Lanczos downscaling <= 2048px, 10MB file limit, MIME enforcement, S3 environment validation.
- [x] **Background Dispatch & Radius Escalation** (`test_background_dispatch.py`, `test_dispatch_engine.py`): 5 km → 10 km → 20 km → 40 km expansion and `UNRESOLVED` fallback.
- [x] **Token Revocation & Session Security** (`test_token_revocation.py`): Single logout, global logout, replay attack rejection.

### 2. Frontend Automated Testing & Build Validation
- [x] **Vitest Unit & Integration Suite**: 11 test files, 40 tests passing (0 failures).
- [x] **NGO Analytics Component Tests** (`NGOAnalytics.test.tsx`): Metric cards, Recharts responsive rendering, outcome distribution, spatial density.
- [x] **NGO Organization Component Tests** (`NGOOrganization.test.tsx`): Dynamic profile loading, input editing, mutation success banner.
- [x] **NGO Settings Component Tests** (`NGOSettings.test.tsx`): Progressive radius parameters, notification toggles, test alert invocation.
- [x] **Authentication & Role Guarding** (`Auth.test.tsx`): JWT storage, role routing, unauthorized redirection.
- [x] **Production Bundle Build (`npm run build`)**: TypeScript check (`tsc -b`) and Vite production bundle generated without errors.

---

## Part B: Staging & Infrastructure Integration Verification

These checks require active staging infrastructure (PostgreSQL/PostGIS, Redis, Celery, S3, Firebase, Sentry).

### 1. Database & Spatial Infrastructure
- [ ] PostGIS extension enabled: `SELECT PostGIS_Version();` succeeds.
- [ ] Alembic schema migrations up to date (`alembic upgrade head`).
- [ ] Spatial indexing (`GIST`) confirmed on rescue case locations and responder locations.

### 2. Background Task Infrastructure (Redis + Celery)
- [ ] Redis instance reachable with TLS/auth enabled.
- [ ] Celery worker running and consuming from `dispatch`, `notifications`, and `default` queues.
- [ ] Celery beat running with periodic tasks scheduled:
  - Expire unaccepted offers every 20 seconds.
  - Record worker heartbeat every 10 seconds.
- [ ] Deep readiness probe `GET /api/v1/health/readiness` returns status `ready` for all 5 subsystems.

### 3. Object Storage Pipeline (S3 / MinIO)
- [ ] Staging S3 bucket created with private ACL and CORS configured for staging domains.
- [ ] Image upload endpoint (`POST /api/v1/uploads/image`) returns S3 URL with WebP format.
- [ ] Backend fails fast on startup if `ENVIRONMENT=staging` and S3 credentials are missing or invalid.

### 4. Push & In-App Notification Delivery (Firebase Admin SDK)
- [ ] Firebase service account credentials loaded from secure path.
- [ ] Device token registration (`POST /api/v1/notifications/devices`) stores valid FCM tokens.
- [ ] Diagnostic test push from NGO Settings triggers notification on recipient browser.
- [ ] PWA Service Worker (`firebase-messaging-sw.js`) handles background pushes and displays native OS notification.

---

## Part C: Operational Flow & Field Pilot Scenarios

Perform these manual smoke tests in the staging environment using real test mobile devices.

### Scenario 1: Citizen Report to NGO Dispatch
1. **Citizen Submission**: Open app on mobile browser, report a critical rescue with live camera photo and GPS coordinates.
2. **Auto-Triage**: Verify case is tagged `CRITICAL` or `URGENT` with triage score >= 70.
3. **Dispatch Wave 1**: System automatically broadcasts dispatch offers to active responders within 5 km.
4. **NGO Visibility**: NGO Overview dashboard updates active case count and displays new pin on the Leaflet operational map.

### Scenario 2: Progressive Radius Escalation
1. Keep Wave 1 responders inactive.
2. After offer expiration window (20s staging), verify Celery worker triggers Wave 2 (10 km).
3. Verify subsequent expansions: 10 km → 20 km → 40 km.
4. If still unaccepted, verify case transitions to `UNRESOLVED` and high-priority notification appears on NGO dashboard.

### Scenario 3: Rescuer Acceptance & Transport
1. Rescuer receives dispatch alert on mobile with countdown timer.
2. Rescuer accepts offer; verify concurrent acceptance protection prevents other responders from claiming the case.
3. Rescuer updates status: `EN_ROUTE_TO_ANIMAL` → `ARRIVED_ON_SCENE` → `EN_ROUTE_TO_VET`.
4. Rescuer uploads on-scene evidence photo; confirm image is compressed and stripped of EXIF.

### Scenario 4: Veterinary Intake & Treatment
1. Vet logs into `/vet` dashboard; sees incoming transport under their assigned facility.
2. Vet marks case as `ARRIVED_AT_VET`.
3. Vet records triage diagnosis, vital signs, and treatment plan.
4. Vet uploads recovery photo and marks case as `RECOVERED` or `DISCHARGED`.

### Scenario 5: Multi-Tenant Security & Organization Isolation
1. Log in as NGO Admin from Organization Alpha.
2. Verify analytics, responders, and cases show only Organization Alpha data.
3. Attempt to fetch or edit Organization Beta records via direct API requests; confirm HTTP `403 Forbidden`.
4. Check `audit_logs` table; verify attempt is immutably logged with user ID, target organization, and timestamp.
