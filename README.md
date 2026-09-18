# PawReach — Stray Animal Rescue Coordination Platform

PawReach is an animal rescue and foster-to-adoption coordination platform connecting citizens, field rescuers, veterinary clinics, foster caregivers, NGOs, and municipal authorities.

> [!NOTE]
> **Live Staging Status**: **`PHASE 3B FINAL CLEANUP — LIVE STAGING VALIDATED ✅`** | **`LIVE INFRASTRUCTURE VERIFIED — AUTHENTICATED PILOT PENDING`**
> - **Hosted Staging API**: `https://pawreach-api.onrender.com` (Verified SHA: `abc9a674a274cf0cce31bd4777e1b6d8701a553d`, CI Run `35329973134`, Deployment Run `35330381134`)
> - **Readiness Telemetry**: Deep subsystem checks operational (Supabase PostgreSQL, PostGIS, Upstash Redis TLS, Celery worker active heartbeat, Supabase Private S3).
> - **Authenticated Pilot Record**: Run `35328481369` documented truthfully as `FAILED BEFORE EXECUTION — STAGING_SEED_PASSWORD ENVIRONMENT SECRET NOT CONFIGURED`. Workflow input removed; automated execution pending secret configuration and fresh deployment.

---

## Architecture & Workflow

```text
Citizen Reports Animal (Upload real photo + Pinpoint GPS)
        ↓
Rule-Based Triage (Priority + Score: CRITICAL/URGENT/MODERATE/GENERAL)
        ↓
Case Stored in PostgreSQL/PostGIS (Spatial geography POINT)
        ↓
Automatic Background Dispatch (Celery + Redis Worker)
        ↓
Progressive Radius Escalation (5km → 10km → 20km → 40km)
        ↓
Real Web Push Notifications (Firebase Cloud Messaging + Service Worker)
        ↓
Rescuer Accepts (Row-level transactional locking prevents race conditions)
        ↓
Responder Progression (ASSIGNED → EN_ROUTE → LOCATED → RESCUED → TRANSPORTING)
        ↓
Arrival at Authorized Veterinary Facility (Scoped to facility ID)
        ↓
Veterinarian Records Treatment (Diagnosis, medications, follow-up)
        ↓
Medical Recovery (UNDER_TREATMENT → RECOVERING → READY_FOR_RELEASE)
        ↓
Case Closure (RELEASED / ADOPTED → CLOSED)
```

If all 4 radius levels are exhausted without responder acceptance, the case automatically transitions to `UNRESOLVED` and generates urgent escalation alerts for NGO and System Administrators.

---

## Technology Stack

- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, GeoAlchemy2, PostgreSQL 15 + PostGIS 3.4
- **Background Workers**: Celery 5.6+, Redis 7
- **Push Notifications**: Firebase Admin SDK (Backend) + Firebase Cloud Messaging (Web Client)
- **Frontend**: React 19, TypeScript, Tailwind CSS, Leaflet / React-Leaflet, Vite, Vitest, Playwright
- **Security**: Argon2 password hashing, JWT with `jti` session revocation (`RefreshSession`), Decompression bomb protection (25MP limit), MIME format verification, Role-Based Access Control, Strict Tenant Organization & Private Facility Scoping, Pre-signed private S3 media URLs

---

## Local Development Setup

### 1. Prerequisites
- Docker & Docker Compose
- Node.js 24+
- Python 3.11+ (if running locally without Docker)

### 2. Full Stack with Docker Compose
```bash
# Clone the repository
git clone https://github.com/Abhiram-C-Divakaran/PawSOS.git
cd PawSOS

# Configure backend environment
cp backend/.env.example backend/.env

# Launch entire stack (PostgreSQL+PostGIS, Redis, Backend, Celery Worker, Frontend)
docker compose up --build
```

Services started:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- Swagger Docs: `http://localhost:8000/docs`
- Health Readiness Probe: `http://localhost:8000/api/v1/health/ready`
- Redis: `localhost:6379`
- PostgreSQL: `localhost:5432`

### 3. Local Python Development (Without Docker)
```bash
# Set up backend virtual environment
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/macOS

pip install -r requirements.txt
alembic upgrade head
python scripts/seed_staging.py

# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# In a separate terminal, start the Celery Worker & Beat scheduler (local development only)
# (Note: In the free-tier staging deployment on Render, FastAPI, the Celery solo worker, and Celery Beat run combined in a single free web container via ./scripts/start_free_render.sh)
celery -A app.tasks.celery_app worker -B --loglevel=info
```

### 4. Local Frontend Development
```bash
cd frontend
npm ci
npm run dev
```

---

## Running Test Suites

### Backend Tests with Coverage (>=85% Required)
```bash
cd backend
pytest tests --cov=app --cov-report=term-missing -v
```

Test suites cover:
- `test_api_contracts.py`: Comprehensive frontend/backend API contract validation for all NGO analytics, KPIs, and outcome classifications.
- `test_storage_service.py`: Image decode integrity, format vs MIME validation, and decompression bomb denial.
- `test_private_media_security.py`: Canonical S3 key normalization, pre-signed URL generation, and cross-tenant image access denial.
- `test_firebase_config.py`: Inline JSON vs file path credential loading, validation, and health probe degradation.
- `test_staging_workflow_validation.py` & `test_smoke_test_unit.py`: CD workflow parsing, smoke test protocol, and preflight script validation.
- `test_ngo_organization.py`: Multi-tenant boundary isolation, blocking cross-tenant responder and private facility assignments with audit logs.
- `test_background_dispatch.py`: Stale offer expiry via Celery worker, deterministic radius escalation (5 -> 10 -> 20 -> 40 km), responder exclusion, escalation to `UNRESOLVED`.
- `test_token_revocation.py`: Server-side `RefreshSession` tracking, token rotation, single/all device logout, replay rejection.
- `test_scoping_security.py`: Cross-tenant scoping, Super Admin global oversight, Veterinary facility scoping.
- `test_pilot_scenarios.py`: End-to-end execution of all 5 operational pilot scenarios.

### Frontend Quality & Unit Tests
```bash
cd frontend
npm run lint          # oxlint checks
npm run test:coverage # Vitest unit tests with coverage
npm run build         # Production TypeScript build
```

### Browser End-to-End Test Suite (Playwright)
```bash
cd frontend
# Mocked UI-contract suite
npm run test:e2e:ui-contract

# Unmocked full-stack E2E suite (requires running backend, Redis, and PostGIS)
npm run test:e2e:fullstack

# Run all E2E suites
npm run test:e2e
npm run test:e2e:ui   # Interactive UI mode
```

E2E specifications:
- `frontend/e2e-contract/`: Mocked API contract tests validating UI views, forms, error handling, and state transitions without external backends.
- `frontend/e2e-fullstack/`:
  - `citizen-report.spec.ts`: Emergency report form, species selection, geolocation, triage, and live case number generation.
  - `responder-flow.spec.ts`: Real-time dispatch offer alerting, acceptance, status advancement (`EN_ROUTE` -> `ANIMAL_LOCATED`).
  - `dispatch-escalation.spec.ts`: Progressive radius escalation from 5km up to 40km.
  - `veterinary-flow.spec.ts`: Clinical inpatient registry, patient admission, vitals & treatment plan logging.
  - `cross-tenant.spec.ts`: Multi-tenant isolation verification, cross-tenant case access denial alert and safe navigation.
  - `concurrent-acceptance.spec.ts`: Dispatch race condition conflict handling, claim rejection notification.

---

## Zero-Cost Free Staging & Demo Deployment

PawReach is designed to run completely within free-tier cloud limits for portfolio and college demonstration purposes:

* **Backend**: Render Free Web Service (`pawreach-api` executing combined FastAPI, Celery solo worker, and Celery Beat via `./scripts/start_free_render.sh`)
* **Frontend**: Render Free Static Site (`pawreach-frontend`)
* **Database**: Supabase Free PostgreSQL 15+ with PostGIS via Session Pooler on **Port 5432**
* **Image Storage**: Supabase Storage via S3-compatible API (Private bucket `evidence` with presigned URLs)
* **Task Broker**: Upstash Free Redis using TLS (`rediss://`)
* **Push Notifications**: Firebase Cloud Messaging (Optional, `REQUIRE_FIREBASE=false`)

> [!NOTE]
> **Deployment Status & Staging Baselines**:
> - **Historical Staging Baseline (Phase 3A)**: Verified green on hosted infrastructure at baseline commit [`1b2ee17`](https://github.com/Abhiram-C-Divakaran/PawSOS/commit/1b2ee17064117331ab3e947a3e9dac0a29d00666) (GitHub Actions Run [35089342305](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35089342305)).
> - **Historical Staging Baseline (Phase 3B)**: Verified green on hosted infrastructure at commit [`baf39e3`](https://github.com/Abhiram-C-Divakaran/PawSOS/commit/baf39e3bc19d21cc423186ed78bca13c3dc569c3) (GitHub Actions Run [35186238652](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35186238652)).
> - **Historical Staging Baseline (Phase 3B Final Closure)**: Verified green on hosted infrastructure at commit [`4e94602`](https://github.com/Abhiram-C-Divakaran/PawSOS/commit/4e94602c3671893a446493a11cba7cb93d4551e8) (GitHub Actions Deployment Run [35270974353](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35270974353), CI Run [35270529178](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35270529178)).
> - **Live Staging Verified Baseline (Celery Worker Recovery & Readiness Hardening)**: Verified green on hosted infrastructure at commit [`53f2626`](https://github.com/Abhiram-C-Divakaran/PawSOS/commit/53f26260d7d393d9721c6246d37d3a382caa5e76) (GitHub Actions Deployment Run [35280706164](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35280706164), CI Run [35280290241](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35280290241)). See [docs/LIVE_STAGING_VALIDATION.md](docs/LIVE_STAGING_VALIDATION.md).
> - **Current Status**: **`STAGING CELERY WORKER HEARTBEAT RECOVERY — LIVE STAGING VALIDATED ✅`**. Celery worker and beat queue routing unified to 'default', canonical Redis TLS normalization helper enforced across tasks/readiness, combined process supervisor hardened in start_free_render.sh with fail-closed supervision, readiness diagnostics enhanced with heartbeat age, and staging smoke test readiness polling verified green in production.

> [!WARNING]
> **Free-Tier Sleep Notice**:
> The Render free web container spins down after 15 minutes of inactivity. The first request after a sleep period incurs a 30–50 second cold-start delay. During container sleep, background dispatch sweeps pause. This deployment is a demonstration system and **NOT** 24/7 emergency response infrastructure.

### Canonical Frontend Contract
```text
VITE_API_BASE_URL=https://<your-render-subdomain>.onrender.com/api/v1
```
The frontend automatically normalizes this value via `src/utils/apiConfig.ts`.

---

## Staging Test Accounts (from `backend/scripts/seed_staging.py`)

All staging accounts are provisioned with the password set via `STAGING_SEED_PASSWORD` (minimum 14 characters, non-default):

| Role | Email | Scope / Affiliation |
|------|-------|---------------------|
| Citizen | `citizen@staging.pawsos.org` | Public Reporter |
| Super Admin | `superadmin@staging.pawsos.org` | Global Operations |
| **Org Alpha Admin** | `admin@staging.pawsos.org` / `admin.a@staging.pawsos.org` | Organization Alpha - Stray Relief |
| Rescuer Alpha 1 | `rescuer.a@staging.pawsos.org` | Org Alpha (Kochi Marine Drive) |
| Rescuer Alpha 2 | `rescuer.b@staging.pawsos.org` | Org Alpha (Kochi Kaloor) |
| Veterinarian Alpha | `vet@staging.pawsos.org` | Cochin PetCare Emergency Hospital |
| **Org Beta Admin** | `admin.b@staging.pawsos.org` | Organization Beta - Animal Aid Alliance |
| Rescuer Beta 1 | `rescuer.b1@staging.pawsos.org` | Org Beta (Fort Kochi) |
| Rescuer Beta 2 | `rescuer.b2@staging.pawsos.org` | Org Beta (Edappally) |
| Veterinarian Beta | `vet.b@staging.pawsos.org` | Alliance Trauma Clinic |

---

## Operational Documentation
- [Live Staging Verification Record](docs/LIVE_STAGING_VALIDATION.md) (Authoritative staging run)
- [Zero-Cost Free Live Deployment Guide](docs/FREE_DEPLOYMENT.md) (20-step setup sequence)
- [System Architecture](ARCHITECTURE.md) (Current implemented vs future/AI architecture)
- [Operations Incident Runbook](docs/OPERATIONS_RUNBOOK.md)
- [Historical Staging Records](docs/PHASE_2_9E_STAGING_EXECUTION.md) *(Superseded)*

