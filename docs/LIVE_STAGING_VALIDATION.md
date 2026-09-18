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
* **Authoritative Deployed Git Commit**: `7cbbb627c78bcbb13da1dd57e011f81e4fabbc91`
* **Commit Message**: `fix(security): close discovery privacy and staging pilot gaps`
* **Preceding Core CI Run**: `PawReach CI / CD Pipeline` Run `35362773445` (`SUCCESS` - all 4 required gates green)
* **Live Staging Deployment Run**: `Staging Deployment & Smoke Tests` Run `35363303817` (`SUCCESS` - exact SHA `7cbbb62` deployed and verified)
* **Authenticated Pilot Status**: **`AUTHENTICATED PILOT PENDING`**
  * **Automated Pilot Execution Run**: `35383131986` (`FAILURE`)
  * **Failure Analysis**: `FAILED BEFORE EXECUTION — STAGING_SEED_PASSWORD ENVIRONMENT SECRET NOT CONFIGURED IN GITHUB ENVIRONMENT 'staging'`. The preflight step verified the missing secret and exited cleanly without running commands or leaking secrets.
  * **Pilot Hardening**: Workflow updated to eliminate password inputs, enforce secret presence safely, pass `--expected-sha`, parse nested readiness telemetry, verify responder determinism with guaranteed cleanup, upload synthetic private evidence, and test explicit multi-tenant case claiming (`POST /api/v1/ngo/cases/{case_id}/claim`).

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Backend Test Suite & Coverage** | Completed | `SUCCESS` | 297 tests passed, 86.27% coverage (exceeds 85% requirement) |
| **Frontend Quality & Build** | Completed | `SUCCESS` | Clean oxlint, 88 vitest unit tests passed, production build passed |
| **Mocked UI Contract Suite (Playwright)** | Completed | `SUCCESS` | 9/9 UI contract scenarios passed |
| **Full-Stack E2E Integration Suite (Unmocked)** | Completed | `SUCCESS` | Real PostGIS, Redis, Celery worker/beat, and FastAPI full-stack tests passed |
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Staging secrets and environment validated |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render deploy hook triggered with ref `7cbbb62` |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | Exact SHA `7cbbb62` confirmed on hosted Render API, automated smoke suite passed |

### Live Readiness Verification

* **Endpoint**: `GET https://pawreach-api.onrender.com/api/v1/health`
* **Status**: `HTTP 200 OK`
* **Payload**:
```json
{
  "status": "ok",
  "environment": "staging",
  "version": "2.0.0",
  "git_sha": "7cbbb627c78bcbb13da1dd57e011f81e4fabbc91"
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

---

## 9. Final Object-Level Authorization Closure & Authenticated Live Staging Pilot Record

* **Verification Date**: September 19, 2026
* **Target Environment**: Staging (Free Cloud Demo)
* **Authoritative Deployed Git Commit**: `eec547575a617bf477eb43c964e6acb2854c5993`
* **Commit Message**: `fix(security): import Any in case_access for animal authorization boundary`
* **Preceding Core CI Run**: `PawReach CI / CD Pipeline` Run `35388208844` (`SUCCESS` — all 4 required gates green)
* **Live Staging Deployment Run**: `Staging Deployment & Smoke Tests` Run `35388656412` (`SUCCESS` — exact SHA `eec5475` deployed and verified)
* **Authenticated Pilot Status**: **`AUTHENTICATED PILOT PENDING`**
  * **Automated Pilot Execution Run**: `35388946280` (`FAILURE`)
  * **Failure Analysis**: `FAILED BEFORE EXECUTION — STAGING_SEED_PASSWORD ENVIRONMENT SECRET NOT CONFIGURED IN GITHUB ENVIRONMENT 'staging'`. The preflight step verified the missing secret and exited cleanly without running commands or leaking secrets.

### Job Execution Summary

| Job | Status | Conclusion | Note |
|-----|--------|------------|------|
| **Backend Test Suite & Coverage** | Completed | `SUCCESS` | 307 passed, 1 skipped, 86.95% coverage (exceeds 85% requirement) in 140s |
| **Frontend Quality & Build** | Completed | `SUCCESS` | Clean oxlint, 88 vitest unit tests passed, production build passed in 36s |
| **Mocked UI Contract Suite (Playwright)** | Completed | `SUCCESS` | 9/9 UI contract scenarios passed in 52s |
| **Full-Stack E2E Integration Suite (Unmocked)** | Completed | `SUCCESS` | 7/7 scenarios passed (Real PostGIS, Redis TLS, Celery worker/beat, FastAPI) in 151s |
| **Check Deployment Prerequisites** | Completed | `SUCCESS` | Staging secrets and environment validated (3s) |
| **Trigger Staging Cloud Deployment** | Completed | `SUCCESS` | Render deploy hook triggered with ref `eec5475` (2s) |
| **Await Deployment & Run Staging Smoke Tests** | Completed | `SUCCESS` | Exact SHA `eec5475` confirmed on hosted Render API, automated smoke suite passed (140s) |

### Live Readiness Verification

* **Endpoint**: `GET https://pawreach-api.onrender.com/health`
* **Status**: `HTTP 200 OK`
* **Payload**:
```json
{
  "status": "ok",
  "environment": "staging",
  "version": "2.0.0",
  "git_sha": "eec547575a617bf477eb43c964e6acb2854c5993"
}
```

* **Endpoint**: `GET https://pawreach-api.onrender.com/health/ready`
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
    "worker_heartbeat_age_seconds": 1.6
  }
}
```

### Security & Object-Level Authorization Certification

1. **Rescue Status Update Authorization**:
   - `verify_case_status_update_access` enforces strict actor-to-case linkage: Citizens restricted to reported cases, Rescuers restricted to accepted assignments, Veterinarians restricted to non-null exact facility match, NGO Admins restricted to non-null own-tenant cases (unassigned cases require prior explicit claim).
2. **Clinical Treatment Scoping & Read Authorization**:
   - `POST /rescues/{case_id}/treatments` fail-closed: requires non-null `case.veterinary_facility_id == current_user.veterinary_facility_id` (silent auto-claiming stripped).
   - `GET /rescues/{case_id}/treatments` authorized to linked actors only.
3. **Animal Record BOLA Closure**:
   - Citizen role removed from `GET` and `PATCH /animals/{id}`. Access restricted to linked actors through cases, and standalone records restricted to organization staff.
4. **NGO Multi-Tenant Isolation**:
   - `require_ngo_org_scope` returns HTTP 403 Forbidden for null-org NGO admins across all private endpoints.
   - Unassigned cases strictly stripped from all NGO analytics queries.
   - `execute_ngo_case_action` rejects unassigned cases with HTTP 403 Forbidden.
   - `assign_responder` blocks unaffiliated and foreign-org responders with HTTP 403 Forbidden, and inactive responders with HTTP 400 Bad Request.




