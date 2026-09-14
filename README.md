# PawReach (PawSOS) — MVP Phase 2.9E: Real Staging Provisioning, Deployment Verification & Controlled Pilot Validation

PawReach is an enterprise-grade stray animal rescue coordination platform connecting citizens, field rescuers, veterinary clinics, foster caregivers, NGOs, and municipal authorities.

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
# (Note: -B embedded beat scheduler is for local development only; staging and production run dedicated worker and beat services)
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

## Staging & Production Deployment

### 1. Database (PostgreSQL + PostGIS)
- Deploy PostgreSQL 15+ with PostGIS extension enabled (`CREATE EXTENSION IF NOT EXISTS postgis;`).
- Run database migrations: `alembic upgrade head`.
- Seed initial staging data with secure operator-defined password:
  ```bash
  STAGING_SEED_PASSWORD="<STRONG_UNIQUE_PASSWORD_MIN_14_CHARS>" ENVIRONMENT=staging python scripts/seed_staging.py
  ```

### 2. Redis & Background Workers (Worker & Beat)
- Provision a Redis instance (e.g. Railway, Redis Cloud, Upstash).
- Set `REDIS_URL=redis://<user>:<pass>@<host>:<port>/0`.
- In staging and production, run Worker and Beat as separate services:
  ```bash
  # Background Task Worker
  celery -A app.tasks.celery_app.celery_app worker --loglevel=info

  # Periodic Beat Scheduler
  celery -A app.tasks.celery_app.celery_app beat --loglevel=info
  ```

### 3. Cloud Storage (S3)
- Set in backend environment:
  ```text
  STORAGE_PROVIDER=s3
  AWS_ACCESS_KEY_ID=<key>
  AWS_SECRET_ACCESS_KEY=<secret>
  AWS_REGION=<region>
  S3_BUCKET_NAME=<bucket>
  S3_PRESIGNED_URL_EXPIRE_SECONDS=900
  ```
- Images are automatically resized (max dimension 2048px), compressed, and EXIF metadata stripped via Pillow. S3 objects remain strictly private with temporary presigned URLs.

### 4. Firebase Cloud Messaging (Web Push)
- Supply credentials via environment variable (preferred in cloud PaaS) or file path:
  ```text
  FIREBASE_CREDENTIALS_JSON={"type": "service_account", ...}
  # OR: FIREBASE_CREDENTIALS_PATH=/etc/secrets/firebase-adminsdk.json
  REQUIRE_FIREBASE=true
  FIREBASE_PROJECT_ID=pawsos-staging
  ```
- Configure frontend environment:
  ```text
  VITE_FIREBASE_API_KEY=...
  VITE_FIREBASE_PROJECT_ID=...
  VITE_FIREBASE_VAPID_KEY=...
  ```

### 5. Frontend SPA Deployment (Vercel / Netlify / Cloudflare Pages)
- Set `VITE_API_BASE_URL=https://<your-api-domain>/api/v1`.
- SPA rewrites are preconfigured in `frontend/public/_redirects` and `frontend/vercel.json`.

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
- [Phase 2.9 Certification Report](docs/PHASE_2_9_CERTIFICATION.md)
- [Phase 2.9E Staging Execution Record](docs/PHASE_2_9E_STAGING_EXECUTION.md)
- [Staging Deployment Architecture](docs/STAGING_DEPLOYMENT.md)
- [Staging Rollback Plan](docs/STAGING_ROLLBACK.md)
- [Operations Incident Runbook](docs/OPERATIONS_RUNBOOK.md)
- [Pilot Verification Checklist](docs/PILOT_CHECKLIST.md)
- [Staging Deployment & Pilot Results](docs/STAGING_PILOT_RESULTS.md)
