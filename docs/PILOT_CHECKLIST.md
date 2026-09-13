# PawReach Pilot Checklist: Phase 2.9 Staging Validation, Security Hardening & Pilot Certification

This checklist defines the sign-off criteria required before opening the PawReach pilot to real field responders, citizens, and partner veterinary clinics.

---

## Part A: Automated Verification (Local & CI Test Suite)

All automated tests must pass and coverage thresholds must be satisfied on `main` before any staging or pilot deployment.

### 1. Backend Automated Testing & Coverage (Threshold: >= 85%)
- [x] **Pytest Unit & Integration Suite**: **108 passed**, 0 failures (83 core + 25 staging security tests).
- [x] **Backend Coverage Bar**: **87.16%** achieved across `backend/app` package — enforced in CI via `--cov-fail-under=85`.
- [x] **Staging Security Tests** (`test_staging_security.py`):
  - Staging seed password validation: enforces $\ge 14$ characters, rejects default/weak passwords (`stagingpass`, `password`, `admin123`, `changeme`, `pawsos`, `pawreach`).
  - Production environment block: prevents running staging seed scripts in production.
  - Uninitialized schema block: ensures `seed_staging.py` fails fast if Alembic migrations have not run.
  - Staging config validation: rejects SQLite in staging, rejects weak/default JWT secrets, rejects wildcard `*` CORS, requires `REDIS_URL`, requires all S3 keys when `STORAGE_PROVIDER=s3`.
  - S3 health check error handling: non-destructive `head_bucket` handles missing or invalid buckets safely.
  - FCM token lifecycle: catches Firebase unregistered errors and deactivates device tokens automatically.
- [x] **API Contract Tests** (`test_api_contracts.py`): Canonical `average_response_minutes`, outcome categories, period filtering.
- [x] **Tenant Scoping & Cross-Tenant Security Tests** (`test_scoping_security.py`, `test_ngo_organization.py`): Cross-organization data isolation verified; cross-tenant responder status mutation (`PATCH /ngo/responders/{user_id}/status`) blocked with HTTP 403 Forbidden (`CROSS_TENANT_RESPONDER_UPDATE_DENIED`) and immutable audit logging; organization reassignment strictly restricted to `SUPER_ADMIN`.
- [x] **NGO Analytics Tests** (`test_ngo_analytics.py`): Tenant-isolated metrics, trend calculations, outcomes, spatial hotspot metrics with time-window filtering (7d, 30d, 90d), PostGIS `ST_SnapToGrid` aggregation with SQLite fallback, strict arrival latency measurement without acceptance fallback, and nullable response time.
- [x] **NGO Organization & Settings Tests** (`test_ngo_organization.py`, `test_ngo_settings.py`): Profile editing, immutable field enforcement, audit log generation, notification preferences.
- [x] **Storage & Image Security Pipeline Tests** (`test_storage_service.py`): Pillow EXIF orientation, Lanczos downscaling $\le 2048$px, 10MB file limit, MIME enforcement, S3 bucket non-destructive health checks, decompression bomb limit (`MAX_IMAGE_PIXELS = 25,000,000`), format vs MIME mismatch detection, corrupt byte stream rejection.
- [x] **Background Dispatch & Radius Escalation** (`test_background_dispatch.py`, `test_dispatch_engine.py`): 5 km → 10 km → 20 km → 40 km expansion and `UNRESOLVED` fallback.
- [x] **Token Revocation & Session Security** (`test_token_revocation.py`, `test_health_and_security.py`): Single logout, global logout, refresh-token rotation, replay attack rejection, cookie security.

### 2. Frontend Automated Testing & Build Validation
- [x] **Vitest Unit & Integration Suite**: 11 test suites, **40 tests passing** (0 failures).
- [x] **Frontend Dependency Security Audit**: **0 vulnerabilities** (0 critical, 0 high, 0 moderate, 0 low). Scoped npm overrides for Firebase `undici: ^6.28.1` and jsdom `undici: ^7.25.0`.
- [x] **Production Bundle Optimization**:
  - Initial entry bundle reduced from `1,083.20 kB` to **`317.75 kB`** (-70.6% reduction).
  - Zero chunks over 500 kB (eliminating all Vite/Rollup chunk warnings).
  - Code splitting via `React.lazy()` for all heavy routes (Leaflet map: 148 kB, Recharts: 332 kB, Command Center: 42 kB, Analytics: 30 kB, Vet: 28 kB).
- [x] **NGO Analytics Component Tests** (`NGOAnalytics.test.tsx`): Metric cards, Recharts responsive rendering, outcome distribution, spatial density.
- [x] **NGO Organization Component Tests** (`NGOOrganization.test.tsx`): Dynamic profile loading, input editing, mutation success banner.
- [x] **NGO Settings Component Tests** (`NGOSettings.test.tsx`): Progressive radius parameters, notification toggles, test alert invocation.
- [x] **Authentication & Role Guarding** (`Auth.test.tsx`): JWT storage, role routing, unauthorized redirection.

### 3. Browser Mocked UI Contract Suite (Playwright `e2e-ui-contract/`)
- [x] **Citizen Emergency Reporting** (`e2e-ui-contract/citizen-report.spec.ts`): Species selection, geolocation, critical triage evaluation, case creation confirmation.
- [x] **Responder Field Workflow** (`e2e-ui-contract/responder-flow.spec.ts`): Dispatch offer alert reception, acceptance, and status advancement (`EN_ROUTE` -> `ANIMAL_LOCATED`).
- [x] **NGO Command Center Operations** (`e2e-ui-contract/ngo-operations.spec.ts`): Command Center KPI cards, case dossier drilldown, audit trail inspection, manual responder reassignment override.
- [x] **Veterinary Clinical Workflow** (`e2e-ui-contract/veterinary-flow.spec.ts`): Inpatient queue, patient intake, and clinical treatment plan recording.
- [x] **Multi-Tenant Security & Isolation** (`e2e-ui-contract/cross-tenant.spec.ts`): Cross-tenant case access denial, `#case-error-state` UI boundary, safe recovery navigation.
- [x] **Concurrent Dispatch Acceptance Protection** (`e2e-ui-contract/concurrent-acceptance.spec.ts`): Dispatch race condition conflict handling, claim rejection notification.

### 4. True Unmocked Full-Stack E2E Suite (Playwright `e2e-fullstack/`)
- [x] **Deterministic E2E Seed Fixture** (`backend/scripts/seed_e2e.py`): Fixed test organizations (Org A, Org B), South Mumbai Hospital facility, 7 deterministic test accounts, pre-staged concurrency and cross-tenant scenarios.
- [x] **Live Citizen Emergency Reporting** (`e2e-fullstack/citizen-report.spec.ts`): Unmocked report submission, database persistence, live case tracking page verification.
- [x] **Live Responder Field Workflow** (`e2e-fullstack/responder-flow.spec.ts`): Live dispatch trigger, real offer receipt, atomic acceptance, full lifecycle progression to veterinary handoff.
- [x] **Live Concurrent Acceptance Conflict** (`e2e-fullstack/concurrent-acceptance.spec.ts`): Real concurrent claim race condition; first responder claims successfully, second receives HTTP 409 Conflict.
- [x] **Live Veterinary Care Flow** (`e2e-fullstack/veterinary-flow.spec.ts`): Real patient intake, medical diagnosis, medications, treatment notes, and status advancement.
- [x] **Live Cross-Tenant Defense** (`e2e-fullstack/cross-tenant.spec.ts`): Real boundary defense; Org A Admin denied access and mutation to Org B responders and confidential cases.
- [x] **Live Dispatch Radius Escalation** (`e2e-fullstack/dispatch-escalation.spec.ts`): Emergency case creation, progressive escalation, and NGO Command Center visibility.

---

## Part B: Staging Infrastructure & Cloud Service Verification

These checks relate to real staging deployment environments. Items verified in automated suites are checked; items requiring cloud account provisioning are designated with their real operational status.

### 1. Database & Spatial Infrastructure
- [x] PostGIS extension enabled: Clean PostGIS migration tested in CI with `CREATE EXTENSION IF NOT EXISTS postgis;`.
- [x] Alembic schema migrations up to date (`alembic upgrade head`).
- [x] Spatial indexing (`GIST`) confirmed on rescue case locations and responder locations.

### 2. Background Task Infrastructure (Redis + Celery)
- [x] Process separation defined: Dedicated `worker` (concurrency 4, queues `dispatch,notifications,default`) and `beat` (singleton scheduler).
- [x] Periodic task configuration: Offer expiration every 20s (staging) and worker heartbeat every 10s.
- [x] Deep readiness probe `GET /api/v1/health/readiness`: Verifies 6 subsystems (database, spatial_postgis, redis, celery, storage, firebase).
- [x] Live System Telemetry UI in NGO Dashboard layout provides real-time health indicator and modal subsystem breakdown.
- [ ] Staging cloud Redis and worker instances deployed: **Status: REQUIRES_EXTERNAL_CREDENTIALS**

### 3. Object Storage Pipeline (AWS S3 / MinIO)
- [x] Image security & transformation pipeline verified (WebP, Lanczos $\le 2048$px, EXIF transpose, 10MB limit, 25M pixel ceiling).
- [x] Staging startup configuration validation (fails fast if S3 keys missing when `STORAGE_PROVIDER=s3`).
- [x] Standalone verification script created: `scripts/verify_staging_upload.py`.
- [ ] Real AWS S3 staging bucket created with private ACL and CORS configured: **Status: REQUIRES_EXTERNAL_CREDENTIALS**

### 4. Push & In-App Notification Delivery (Firebase Admin SDK)
- [x] Firebase Admin SDK service and device token deactivation lifecycle verified in automated tests.
- [x] PWA Service Worker (`firebase-messaging-sw.js`) configured at root scope.
- [x] Setup guide and diagnostic protocol documented (`docs/FIREBASE_STAGING_SETUP.md`).
- [ ] Real Firebase service account JSON loaded in staging environment: **Status: REQUIRES_EXTERNAL_CREDENTIALS**
- [ ] Push notification delivered to physical mobile device browser: **Status: REQUIRES_REAL_DEVICE_TEST**

---

## Part C: Operational Flow & Field Pilot Scenarios

All 5 core operational scenarios are validated by the unmocked fullstack E2E suite against live PostgreSQL/PostGIS, Redis, Celery, and FastAPI. In-field physical device smoke testing requires live staging deployment:

| Scenario | Automated E2E Test Suite | Field Pilot Physical Device Status |
| :--- | :--- | :--- |
| **Scenario 1: Citizen Report to NGO Dispatch** | Passed (`e2e-fullstack/citizen-report.spec.ts`) | **Status: REQUIRES_REAL_DEVICE_TEST** |
| **Scenario 2: Progressive Radius Escalation** | Passed (`e2e-fullstack/dispatch-escalation.spec.ts`) | **Status: REQUIRES_REAL_DEVICE_TEST** |
| **Scenario 3: Rescuer Acceptance & Transport** | Passed (`e2e-fullstack/responder-flow.spec.ts`) | **Status: REQUIRES_REAL_DEVICE_TEST** |
| **Scenario 4: Veterinary Intake & Treatment** | Passed (`e2e-fullstack/veterinary-flow.spec.ts`) | **Status: REQUIRES_REAL_DEVICE_TEST** |
| **Scenario 5: Multi-Tenant Security & Isolation** | Passed (`e2e-fullstack/cross-tenant.spec.ts`) | **Status: REQUIRES_REAL_DEVICE_TEST** |
