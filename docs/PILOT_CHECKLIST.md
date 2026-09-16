# PawReach Pilot Checklist: Phase 2.9 Staging Validation, Security Hardening & Pilot Certification

> [!NOTE]
> **SUPERSEDED**: Historical checklist preserved for audit reference. Current operational procedures and live validation results are documented in [LIVE_STAGING_VALIDATION.md](LIVE_STAGING_VALIDATION.md) and [FREE_DEPLOYMENT.md](FREE_DEPLOYMENT.md).

This checklist defines the sign-off criteria required before opening the PawReach pilot to real field responders, citizens, and partner veterinary clinics.

---

## Part A: Automated Verification (Local & CI Test Suite)

All automated tests must pass and coverage thresholds must be satisfied on `main` before any staging or pilot deployment.

### 1. Backend Automated Testing & Coverage (Threshold: >= 85%)
- [x] **Pytest Unit & Integration Suite**: **169 passed**, 0 failures (100% pass rate). Status: **`VERIFIED IN CI`**
- [x] **Backend Coverage Bar**: **87.02%** achieved across `backend/app` package — enforced in CI via `--cov-fail-under=85`. Status: **`VERIFIED IN CI`**
- [x] **Access Control & Private Media Security Tests** (`test_access_control_closure.py`): Status: **`VERIFIED IN CI`**
  - Centralized fail-closed authorization: citizens only access owned cases; independent citizen receives 403.
  - Rescuer case relationship: rescuers without active offer/assignment denied 403; open status alone never grants access.
  - Veterinarian facility scoping: strict fail-closed matching on non-null `veterinary_facility_id`.
  - NGO tenant isolation: cross-tenant access denied 403; unassigned private case details/dossier denied 403.
  - Private media security: canonical keys persisted, generic list endpoints return `presign_images=False`, discovery `/nearby` returns `images = []`, dedicated endpoint `/rescues/{id}/images/{img_id}/access` validates relationship.
- [x] **Staging Security & Config Tests** (`test_staging_security.py`): Status: **`VERIFIED IN CI`**
  - Staging seed password validation: enforces $\ge 14$ characters, rejects default/weak passwords.
  - Production environment block: prevents running staging seed scripts in production.
  - Uninitialized schema block: ensures `seed_staging.py` fails fast if Alembic migrations have not run.
  - Staging config validation: rejects SQLite in staging, rejects weak/default JWT secrets, rejects wildcard `*` CORS, requires `REDIS_URL`, requires all S3 keys when `STORAGE_PROVIDER=s3`.
  - S3 health check error handling: non-destructive `head_bucket` handles missing or invalid buckets safely.
  - FCM token lifecycle: catches Firebase unregistered errors and deactivates device tokens automatically.
- [x] **Staging Workflow & CD Validation Tests** (`test_staging_workflow_validation.py`): Status: **`VERIFIED IN CI`**
  - Staging CD workflow trigger references exact CI workflow name (`PawReach CI / CD Pipeline`).
  - Smoke test CLI argument flags and parser compatibility verified.
  - SHA polling and bounded rollout loop logic verified.
  - `render.yaml` preDeployCommand and `docker-compose.staging.yml` process types validated.
- [x] **API Contract Tests** (`test_api_contracts.py`): Canonical `average_response_minutes`, outcome categories, period filtering. Status: **`VERIFIED IN CI`**
- [x] **Storage & Image Security Pipeline Tests** (`test_storage_service.py`): Pillow EXIF orientation, Lanczos downscaling $\le 2048$px, 10MB file limit, MIME enforcement, S3 bucket non-destructive health checks, decompression bomb limit (`MAX_IMAGE_PIXELS = 25,000,000`), format vs MIME mismatch detection, corrupt byte stream rejection. Status: **`VERIFIED IN CI`**
- [x] **Background Dispatch & Radius Escalation** (`test_background_dispatch.py`, `test_dispatch_engine.py`): 5 km → 10 km → 20 km → 40 km expansion and `UNRESOLVED` fallback. Status: **`VERIFIED IN CI`**
- [x] **Token Revocation & Session Security** (`test_token_revocation.py`, `test_health_and_security.py`): Single logout, global logout, refresh-token rotation, replay attack rejection, cookie security. Status: **`VERIFIED IN CI`**

### 2. Frontend Automated Testing & Build Validation
- [x] **Vitest Unit & Integration Suite**: 13 test suites, **61 tests passing** (0 failures) including API interceptor token rotation and Firebase push notification lifecycle. Status: **`VERIFIED IN CI`**
- [x] **Frontend Dependency Security Audit**: **0 vulnerabilities** (0 critical, 0 high, 0 moderate, 0 low). Scoped npm overrides for Firebase `undici: ^6.28.1` and jsdom `undici: ^7.25.0`. Status: **`VERIFIED IN CI`**
- [x] **Frontend Linter Hygiene**: **0 errors, 0 warnings** across all 67 files via oxlint. Status: **`VERIFIED IN CI`**
- [x] **Production Bundle & Asset Resolution Optimization**: Status: **`VERIFIED IN CI`**
  - Initial entry bundle: **`318.27 kB`** (Gzip: 100 kB).
  - Zero chunks over 500 kB (eliminating all Vite/Rollup chunk warnings).
  - Zero Leaflet distribution asset warnings (all markers and layers resolved at build time).
  - Code splitting via `React.lazy()` for all heavy routes (Leaflet map: 148 kB, Recharts: 332 kB, Command Center: 43 kB, Analytics: 31 kB, Vet: 11 kB).
- [x] **Protected Image Component**: `<ProtectedImage />` tested with direct uploads, loading states, error fallbacks, and authenticated presigned URL fetching. Status: **`VERIFIED IN CI`**
- [x] **NGO Analytics Component Tests** (`NGOAnalytics.test.tsx`): Metric cards, Recharts responsive rendering, outcome distribution, spatial density. Status: **`VERIFIED IN CI`**
- [x] **NGO Organization Component Tests** (`NGOOrganization.test.tsx`): Dynamic profile loading, input editing, mutation success banner. Status: **`VERIFIED IN CI`**
- [x] **NGO Settings Component Tests** (`NGOSettings.test.tsx`): Progressive radius parameters, notification toggles, test alert invocation. Status: **`VERIFIED IN CI`**
- [x] **Authentication & Role Guarding** (`Auth.test.tsx`): JWT storage, role routing, unauthorized redirection. Status: **`VERIFIED IN CI`**

### 3. Browser Mocked UI Contract Suite (Playwright `e2e-ui-contract/`)
- [x] **Citizen Emergency Reporting** (`e2e-ui-contract/citizen-report.spec.ts`): Species selection, geolocation, critical triage evaluation, case creation confirmation. Status: **`VERIFIED IN CI`**
- [x] **Responder Field Workflow** (`e2e-ui-contract/responder-flow.spec.ts`): Dispatch offer alert reception, acceptance, and status advancement (`EN_ROUTE` -> `ANIMAL_LOCATED`). Status: **`VERIFIED IN CI`**
- [x] **NGO Command Center Operations** (`e2e-ui-contract/ngo-operations.spec.ts`): Command Center KPI cards, case dossier drilldown, audit trail inspection, manual responder reassignment override. Status: **`VERIFIED IN CI`**
- [x] **Veterinary Clinical Workflow** (`e2e-ui-contract/veterinary-flow.spec.ts`): Inpatient queue, patient intake, and clinical treatment plan recording. Status: **`VERIFIED IN CI`**
- [x] **Multi-Tenant Security & Isolation** (`e2e-ui-contract/cross-tenant.spec.ts`): Cross-tenant case access denial, `#case-error-state` UI boundary, safe recovery navigation. Status: **`VERIFIED IN CI`**
- [x] **Concurrent Dispatch Acceptance Protection** (`e2e-ui-contract/concurrent-acceptance.spec.ts`): Dispatch race condition conflict handling, claim rejection notification. Status: **`VERIFIED IN CI`**

### 4. True Unmocked Full-Stack E2E Suite (Playwright `e2e-fullstack/`)
- [x] **Deterministic E2E Seed Fixture** (`backend/scripts/seed_e2e.py`): Fixed test organizations (Org A, Org B), South Mumbai Hospital facility, 8 deterministic test accounts (including `citizen2.e2e@pawreach.test` for cross-user tests), pre-staged concurrency and cross-tenant scenarios. Status: **`VERIFIED IN CI`**
- [x] **Live Citizen Emergency Reporting** (`e2e-fullstack/citizen-report.spec.ts`): Unmocked report submission, database persistence, live case tracking page verification. Status: **`VERIFIED IN CI`**
- [x] **Live Responder Field Workflow** (`e2e-fullstack/responder-flow.spec.ts`): Live dispatch trigger, real offer receipt, atomic acceptance, full lifecycle progression to veterinary handoff. Status: **`VERIFIED IN CI`**
- [x] **Live Concurrent Acceptance Conflict** (`e2e-fullstack/concurrent-acceptance.spec.ts`): Real concurrent claim race condition; first responder claims successfully, second receives HTTP 409 Conflict. Status: **`VERIFIED IN CI`**
- [x] **Live Veterinary Care Flow** (`e2e-fullstack/veterinary-flow.spec.ts`): Real patient intake, medical diagnosis, medications, treatment notes, and status advancement. Status: **`VERIFIED IN CI`**
- [x] **Live Cross-Tenant Defense** (`e2e-fullstack/cross-tenant.spec.ts`): Real boundary defense; Org A Admin denied access and mutation to Org B responders and confidential cases. Status: **`VERIFIED IN CI`**
- [x] **Live Dispatch Radius Escalation** (`e2e-fullstack/dispatch-escalation.spec.ts`): Emergency case creation, natural Celery Beat offer expiry, 5km -> 10km escalation, wave 2 responder offer, no-duplicate-offer guarantee, UNRESOLVED transition, citizen owner polling, and cross-user denial. Status: **`VERIFIED IN CI`**

---

## Part B: Staging Infrastructure & Cloud Service Verification

| Infrastructure Component | Verification Criteria | Status |
|---|---|---|
| **PostgreSQL + PostGIS** | Clean PostGIS migration tested in CI with `CREATE EXTENSION IF NOT EXISTS postgis;`, Alembic head verified, GIST spatial indexing verified | **`VERIFIED IN CI`** / `REQUIRES_PROVIDER_CONFIGURATION` |
| **Redis Broker & Cache** | Redis 7-alpine connectivity verified in CI, standalone/cluster config verified, password authentication configured | **`VERIFIED IN CI`** / `REQUIRES_PROVIDER_CONFIGURATION` |
| **Celery Background Worker** | Worker process separated from Beat (`dispatch,notifications,default`), consumer concurrency 4, task execution verified | **`VERIFIED IN CI`** / `REQUIRES_PROVIDER_CONFIGURATION` |
| **Celery Beat Scheduler** | Singleton periodic scheduler, offer expiration every 20s (staging), worker heartbeat every 10s | **`VERIFIED IN CI`** / `REQUIRES_PROVIDER_CONFIGURATION` |
| **Deep Readiness Probe** | `/api/v1/health/ready` verified with 6 subsystems (database, postgis, redis, celery, storage, firebase) | **`VERIFIED IN CI`** |
| **Private S3 Media Bucket** | Private bucket ACL, Block All Public Access, canonical key persistence, 15-min presigned URL generation, Pillow image downscaling | **`VERIFIED IN CI`** / `REQUIRES_EXTERNAL_CREDENTIALS` |
| **Firebase Cloud Messaging** | Admin SDK initialization, token registration lifecycle, unregistered token deactivation, PWA service worker | **`VERIFIED IN CI`** / `REQUIRES_EXTERNAL_CREDENTIALS` |
| **Staging CD Automation** | `.github/workflows/staging-deploy.yml` triggers upon green CI, environment `staging` gating, SHA resolution, bounded health polling | **`VERIFIED IN CI`** / `REQUIRES_EXTERNAL_CREDENTIALS` |
| **Rollback Plan & Runbooks** | `docs/STAGING_ROLLBACK.md` and `docs/OPERATIONS_RUNBOOK.md` covering all 12 incident modes | **`IMPLEMENTED`** |

---

## Part C: Operational Flow & Field Pilot Scenarios

All 5 core operational scenarios are validated by the unmocked fullstack E2E suite against live PostgreSQL/PostGIS, Redis, Celery, and FastAPI. In-field physical device smoke testing requires live staging deployment:

| Scenario | Automated Full-Stack Suite (CI) | Real-Device Pilot Status |
|---|---|---|
| **Scenario 1: Citizen Report to NGO Dispatch** | **`VERIFIED IN CI`** (`citizen-report.spec.ts`) | **`REQUIRES_REAL_DEVICE_TEST`** |
| **Scenario 2: Progressive Radius Escalation** | **`VERIFIED IN CI`** (`dispatch-escalation.spec.ts`) | **`REQUIRES_REAL_DEVICE_TEST`** |
| **Scenario 3: Rescuer Response & Tracking** | **`VERIFIED IN CI`** (`responder-flow.spec.ts`) | **`REQUIRES_REAL_DEVICE_TEST`** |
| **Scenario 4: Concurrent Acceptance Protection** | **`VERIFIED IN CI`** (`concurrent-acceptance.spec.ts`) | **`REQUIRES_REAL_DEVICE_TEST`** |
| **Scenario 5: Veterinary Care Handoff** | **`VERIFIED IN CI`** (`veterinary-flow.spec.ts`) | **`REQUIRES_REAL_DEVICE_TEST`** |

---

## Part D: Sign-Off Summary

```text
================================================================================
PILOT SIGN-OFF STATUS:
STAGING CONFIGURATION READY — EXTERNAL ACTION REQUIRED
================================================================================
Automated Quality Gates: 100% PASS (169 backend, 61 vitest, 6 UI contract, 7 fullstack)
Security & Authorization: 100% PASS (Phase 2.9D fail-closed access control)
Deployment Architecture: 100% READY (render.yaml, Procfile, docker-compose.staging.yml)
Next Step: Operator populates GitHub staging environment secrets to trigger cloud deployment.
================================================================================
```
