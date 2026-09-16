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
