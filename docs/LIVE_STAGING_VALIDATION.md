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
> **Operational Status**: **`PHASE 3B FINAL CLEANUP — LIVE STAGING VALIDATED ✅`** | **`LIVE INFRASTRUCTURE VERIFIED — AUTHENTICATED PILOT PENDING`**.

---

## 8. Dispatch Claim Integrity Closure & Authenticated Live Staging Pilot Validation Record

* **Verification Date**: September 18, 2026
* **Target Environment**: Staging (Free Cloud Demo)
* **Authoritative Deployed Git Commit**: `abc9a674a274cf0cce31bd4777e1b6d8701a553d`
* **Commit Message**: `docs(staging): record dispatch claim integrity closure and live staging validation`
* **Preceding Core CI Run**: `PawReach CI / CD Pipeline` Run `35329973134` (`SUCCESS` - all 4 required gates green)
* **Live Staging Deployment Run**: `Staging Deployment & Smoke Tests` Run `35330381134` (`SUCCESS` - exact SHA `abc9a67` deployed and verified)
* **Authenticated Pilot Status**: **`AUTHENTICATED PILOT PENDING`**
  * **Initial Pilot Execution Run**: `35328481369` (`FAILURE`)
  * **Failure Analysis**: `FAILED BEFORE EXECUTION — STAGING_SEED_PASSWORD ENVIRONMENT SECRET NOT CONFIGURED`. The GitHub Environment secret `STAGING_SEED_PASSWORD` was unconfigured, halting the workflow prior to running `scripts/staging_authenticated_pilot.py`.
  * **Pilot Hardening**: Workflow updated to eliminate password inputs, enforce secret presence safely, pass `--expected-sha`, parse nested readiness telemetry, verify responder determinism with guaranteed cleanup, upload synthetic private evidence, and test explicit multi-tenant case claiming (`POST /api/v1/ngo/cases/{case_id}/claim`).

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Backend Test Suite & Coverage** | Completed | `SUCCESS` | 285 tests passed, 86.60% coverage (exceeds 85% requirement) |
| **Frontend Quality & Build** | Completed | `SUCCESS` | Clean oxlint, 86 vitest unit tests passed, production build passed |
| **Mocked UI Contract Suite (Playwright)** | Completed | `SUCCESS` | 9/9 UI contract scenarios passed |
| **Full-Stack E2E Integration Suite (Unmocked)** | Completed | `SUCCESS` | 7/7 real PostGIS, Redis, Celery worker/beat, and FastAPI full-stack tests passed |
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Staging secrets and environment validated |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render deploy hook triggered with ref `abc9a67` |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | Exact SHA `abc9a67` confirmed on hosted Render API, automated smoke suite passed |

### Live Readiness Verification

* **Endpoint**: `GET https://pawreach-api.onrender.com/api/v1/health`
* **Status**: `HTTP 200 OK`
* **Payload**:
```json
{
  "status": "ok",
  "environment": "staging",
  "version": "2.0.0",
  "git_sha": "abc9a674a274cf0cce31bd4777e1b6d8701a553d"
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

### Security, Discovery Privacy & Single-Winner Architecture Certification

1. **Discovery Privacy Closure**:
   - `GET /api/v1/rescues/nearby` now returns `RescueDiscoverySummary`, strictly omitting `reporter_id`, exact coordinates (`latitude`/`longitude`), street address (`address_text`), images, and assigned responder details. Rescuer cards display coarse distance without revealing exact scene location prior to dispatch offer issuance.
   - `GET /api/v1/ngo/cases` returns `NGOCaseSummaryResponse`, ensuring unassigned queue cases do not expose private reporter details, evidence keys, or exact coordinates prior to an organization claiming the case.
2. **Explicit Atomic NGO Case Claiming**:
   - `POST /api/v1/ngo/cases/{case_id}/claim` provides an auditable, atomic ownership operation utilizing pessimistic row locking (`with_for_update().populate_existing()`). Cross-tenant claims fail closed with HTTP 409 Conflict; same-tenant claims are idempotent.
3. **Manual Assignment Concurrency Protection**:
   - NGO manual responder assignment (`assign_responder`) acquires `RescueCase` row locks first, inspects existing `ACCEPTED` assignments, cancels competing offers atomically, and prevents double-winner races with concurrent responder acceptances.
4. **Elimination of Direct-Claim Security Bypass**:
   - `POST /api/v1/rescues/{case_id}/accept` strictly requires an active, unexpired `PENDING` dispatch offer issued to that responder, failing closed with **HTTP 403 Forbidden** for unoffered responders.
5. **Repeatable Authenticated Staging Pilot Automation**:
   - Standalone CLI runner established in `scripts/staging_authenticated_pilot.py` with authoritative preflight telemetry, expected commit SHA validation, responder availability setup with guaranteed cleanup, private synthetic evidence upload, and cross-tenant claim verification.
   - Workflow `.github/workflows/staging-authenticated-pilot.yml` hardened to source `STAGING_SEED_PASSWORD` exclusively from environment secrets without CLI parameter exposure.



