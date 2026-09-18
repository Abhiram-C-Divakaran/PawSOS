# PawReach — Live Staging Verification Record

This document records the official live staging deployment validation for **PawReach**, establishing the operational baseline for public demonstration and college portfolio evaluation.

---

## 1. Deployment Baseline & Evidence

* **Verification Date**: September 16, 2026
* **Target Environment**: Staging (Free Cloud Demo)
* **Authoritative Git Commit**: `1b2ee17064117331ab3e947a3e9dac0a29d00666`
* **Commit Message**: `fix(deploy): close free-tier Redis TLS and database connection compatibility`
* **GitHub Actions Workflow**: `Staging Deployment & Smoke Tests`
* **Workflow Run ID**: `35089342305` (Attempt 2)
* **Workflow Overall Conclusion**: `SUCCESS` (All jobs green)

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Staging secrets verified in GitHub Environment |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render webhook triggered successfully |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | API rolled out, SHA matched, smoke suite passed |

---

## 2. Verified Topology & Infrastructure

PawReach is hosted entirely on free-tier cloud resources:

```text
Browser / Mobile PWA Client
            │
            ▼
   Render Static Site
   (pawreach-frontend)
            │
          HTTPS
            │
            ▼
 Render Free Web Service
     (pawreach-api)
  ┌─────────────────────────┐
  │  FastAPI (Uvicorn)      │
  │  Celery Worker (solo)   │
  │  Celery Beat Scheduler  │
  └───────────┬─────────────┘
              │
      ┌───────┴────────┐
      ▼                ▼
Supabase Free     Upstash Free
PostgreSQL        Redis (TLS)
PostGIS           rediss://
Private S3
```

### Verified Subsystem Classes

1. **API Liveness & Telemetry (`/api/v1/health`)**:
   - Status: `ok`
   - Environment: `staging`
   - Version: `2.0.0`
   - Deployed SHA: `1b2ee17064117331ab3e947a3e9dac0a29d00666` (exact match)

2. **Subsystem Deep Readiness (`/api/v1/health/ready`)**:
   - Database: `healthy` (Supabase PostgreSQL via Session Pooler on Port 5432)
   - PostGIS: `healthy` (`PostGIS_Version()` verified)
   - Redis: `healthy` (Upstash Redis over TLS via `rediss://`)
   - Celery: `healthy` (Worker heartbeat freshness verified within TTL)
   - Storage: `healthy` (Supabase private bucket `evidence` via S3-compatible API)
   - Firebase: `unconfigured` (`REQUIRE_FIREBASE=false` confirmed non-blocking)
   - Overall Readiness: `ready`

3. **CORS Security Controls**:
   - Allowed Origin: Exact deployed frontend origin granted credentialed access
   - Wildcard Origin: Explicitly prohibited; `*` rejected
   - Unauthorized Origin: Denied (`https://unauthorized.example` rejected)

4. **HTTP Security Headers**:
   - `X-Content-Type-Options: nosniff` verified
   - `Strict-Transport-Security` (HSTS) enforced on HTTPS
   - Referrer-Policy verified

5. **Frontend PWA & Deep Routing**:
   - Root SPA (`/`) returns valid application entrypoint
   - Deep client-side routes (`/login`, `/report`, `/rescuer`, `/vet`, `/ngo`) return SPA index payload cleanly (HTTP 200)

---

## 3. Free-Tier Operational Characteristics & Limitations

> [!WARNING]
> **Demo / Portfolio Operational Boundary**:
> - **Inactivity Spin-Down**: The Render free-tier container spins down after 15 minutes of inactivity.
> - **Cold-Start Delay**: The first request after a sleep period may incur a 30–50 second cold-start initialization.
> - **Combined Process Execution**: Because FastAPI, the lightweight Celery worker, and Celery Beat execute in a single free container, background task processing and periodic sweeps pause while the container sleeps.
> - **Dispatch Notice**: Automatic background dispatch is best-effort in this free public demo. It is **NOT** a 24/7 production emergency response system.
> - **Zero Recurring Cost**: The application maintains zero operational cost within the defined free-tier allowances of Render, Supabase, and Upstash.

---

## 4. Canonical Frontend-Backend Contract

The single authoritative contract for frontend configuration is:
```text
VITE_API_BASE_URL=https://<your-render-api-subdomain>.onrender.com/api/v1
```
The frontend normalization layer (`frontend/src/utils/apiConfig.ts`) automatically cleans trailing slashes and ensures consistent `/api/v1` prefixing.

---

## 5. Phase 3B Staging Validation Record

* **Verification Date**: September 17, 2026
* **Target Environment**: Staging (Free Cloud Demo)
* **Authoritative Git Commit**: `baf39e3bc19d21cc423186ed78bca13c3dc569c3`
* **Commit Message**: `fix(triage): wrap triage task errors in ValueError and log non-sensitive messages`
* **GitHub Actions Workflow**: `Staging Deployment & Smoke Tests`
* **Workflow Run ID**: `35186238652`
* **Workflow Overall Conclusion**: `SUCCESS` (All jobs green)

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Secrets and environment verified |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render webhook triggered successfully |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | Exact SHA `baf39e3` verified, all smoke tests passed |

---

## 6. Phase 3B Final Closure & Hardening Validation Record

* **Verification Date**: September 18, 2026
* **Target Environment**: Staging (Free Cloud Demo)
* **Authoritative Git Commit**: `4e94602c3671893a446493a11cba7cb93d4551e8`
* **Commit Message**: `fix(frontend): guard against missing rule_assessment in TriageAdvisoryCard`
* **GitHub Actions Workflow**: `Staging Deployment & Smoke Tests`
* **Workflow Run ID**: `35270974353`
* **Workflow Overall Conclusion**: `SUCCESS` (All jobs green)
* **Preceding CI Workflow**: `PawReach CI / CD Pipeline` (Run ID `35270529178`, `SUCCESS`)

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Staging secrets verified in GitHub Environment |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render deployment webhook dispatched for ref `4e94602` |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | Live Render API verified deployed SHA `4e94602`, automated smoke suite passed |

---

## 7. Staging Celery Worker Heartbeat Recovery & Readiness Hardening Validation Record

* **Verification Date**: September 18, 2026
* **Target Environment**: Staging (Free Cloud Demo)
* **Authoritative Git Commit**: `53f26260d7d393d9721c6246d37d3a382caa5e76`
* **Commit Message**: `fix(deploy): initialize supervisor termination state in start_free_render.sh`
* **GitHub Actions Deployment Workflow**: `Staging Deployment & Smoke Tests`
* **Workflow Run ID**: `35280706164`
* **Workflow Overall Conclusion**: `SUCCESS` (All jobs green)
* **Preceding CI Workflow**: `PawReach CI / CD Pipeline` (Run ID `35280290241`, `SUCCESS`)

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Staging secrets and environment validated |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render deploy hook triggered with ref `53f2626` |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | Exact SHA `53f2626` confirmed, automated smoke test suite passed |

### Live Readiness Verification

* **Endpoint**: `GET /api/v1/health/ready`
* **Status**: `HTTP 200 OK`
* **Payload**:
```json
{
  "status": "ready",
  "environment": "staging",
  "services": {
    "database": "healthy",
    "postgis": "healthy",
    "redis": "healthy",
    "celery": "healthy",
    "storage": "healthy",
    "firebase": "unconfigured",
    "ai_triage": "disabled"
  },
  "checks": {
    "database": "connected",
    "postgis": "available",
    "redis": "connected",
    "worker": "active",
    "storage": "healthy",
    "firebase": "unconfigured",
    "ai_triage": "disabled",
    "worker_heartbeat_age_seconds": 35.8
  }
}
```

---

> [!NOTE]
> **Operational Status**: **`PHASE 3B FINAL CLEANUP — LIVE STAGING VALIDATED ✅`** | **`LIVE FREE DEMO VERIFIED ✅`**.

---

## 8. Dispatch Claim Integrity Closure & Authenticated Live Staging Pilot Validation Record

* **Verification Date**: September 18, 2026
* **Target Environment**: Staging (Free Cloud Demo)
* **Authoritative Git Commit**: `4e8859c1c677f6e3e4be802536b3c337336c9cf9`
* **Commit Message**: `fix(dispatch): enforce dispatch claim authorization and single-winner integrity`
* **GitHub Actions Deployment Workflow**: `Staging Deployment & Smoke Tests`
* **Workflow Run ID**: `35328069882`
* **Workflow Overall Conclusion**: `SUCCESS` (All jobs green)
* **Preceding CI Workflow**: `PawReach CI / CD Pipeline` (Run ID `35327661605`, `SUCCESS`)

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Backend Test Suite & Coverage** | Completed | `SUCCESS` | 285 tests passed, 85.72% coverage (above 85% threshold) |
| **Frontend Quality & Build** | Completed | `SUCCESS` | Clean oxlint (0 errors), 86 vitest unit tests passed, production build passed |
| **Mocked UI Contract Suite (Playwright)** | Completed | `SUCCESS` | 9/9 UI contract scenarios passed |
| **Full-Stack E2E Integration Suite (Unmocked)** | Completed | `SUCCESS` | Real PostGIS, Redis, Celery worker/beat, and FastAPI full-stack tests passed |
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Staging secrets and environment validated |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render deploy hook triggered with ref `4e8859c` |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | Exact SHA `4e8859c` confirmed on hosted Render API, automated smoke suite passed |

### Live Readiness Verification

* **Endpoint**: `GET https://pawreach-api.onrender.com/api/v1/health`
* **Status**: `HTTP 200 OK`
* **Payload**:
```json
{
  "status": "ok",
  "environment": "staging",
  "version": "2.0.0",
  "git_sha": "4e8859c1c677f6e3e4be802536b3c337336c9cf9"
}
```

* **Endpoint**: `GET https://pawreach-api.onrender.com/api/v1/health/ready`
* **Status**: `HTTP 200 OK`
* **Payload**:
```json
{
  "status": "ready",
  "environment": "staging",
  "services": {
    "database": "healthy",
    "postgis": "healthy",
    "redis": "healthy",
    "celery": "healthy",
    "storage": "healthy",
    "firebase": "unconfigured",
    "ai_triage": "disabled"
  },
  "checks": {
    "database": "connected",
    "postgis": "available",
    "redis": "connected",
    "worker": "active",
    "storage": "healthy",
    "firebase": "unconfigured",
    "ai_triage": "disabled",
    "worker_heartbeat_age_seconds": 42.3
  }
}
```

### Security & Single-Winner Architecture Certification

1. **Elimination of Direct-Claim Security Bypass**:
   - `POST /api/v1/rescues/{case_id}/accept` has been converted from creating arbitrary assignments to a secure backwards-compatible shim.
   - Responders can no longer accept missions by knowing or discovering a case UUID. Mission acceptance strictly requires an active, unexpired `PENDING` dispatch offer issued to that responder.
   - An unoffered responder or third-party attempting to claim a case receives **HTTP 403 Forbidden** (`No active dispatch offer found for this rescuer on this case`).
2. **Canonical Dispatch Delegation**:
   - All claims delegate to `DispatchService.accept_offer` utilizing pessimistic row-locking (`RescueCase.with_for_update().populate_existing()`).
   - The winning responder claims the mission and atomically transitions the case to `RESPONDER_ASSIGNED`.
   - All other pending dispatch offers for that case are immediately marked `CANCELLED`.
   - Any second or concurrent claimant receives **HTTP 409 Conflict**.
3. **Frontend Nearby Discovery Read-Only Transition**:
   - In `frontend/src/pages/RescuerDashboard.tsx`, the nearby emergencies list no longer renders a direct "Accept Rescue Mission" button.
   - Nearby cases render a neutral, non-actionable `Awaiting Dispatch Offer` badge with clock icon.
   - All mission acceptance occurs exclusively through incoming dispatch offer alert cards with timer countdowns and match scores.
4. **Comprehensive Authorization Regression Coverage**:
   - All 12 claim authorization scenarios are enforced and verified in `backend/tests/test_dispatch_claim_authorization.py`.
5. **Repeatable Authenticated Staging Pilot Automation**:
   - Standalone CLI runner established in `scripts/staging_authenticated_pilot.py`.
   - Dispatchable GitHub Actions workflow established in `.github/workflows/staging-authenticated-pilot.yml`.



