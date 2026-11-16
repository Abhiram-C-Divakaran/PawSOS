# PawReach — Stray Animal Rescue Coordination Platform

PawReach is an end-to-end animal rescue, clinical treatment, foster care, and adoption coordination platform connecting citizens, field rescuers, veterinary clinics, foster caregivers, NGOs, and municipal authorities.

> [!NOTE]
> **Live Staging & Release Status (`v1.0.0`)**: **`LIVE STAGING & AUTHENTICATED PILOT VALIDATED ✅`**
> - **Hosted Staging API**: `https://pawreach-api.onrender.com`
> - **Phase 3C PWA Polish Deployment**: Verified green at SHA [`04ffe2f9cd0a64ff9369fe87f42526e0178ee41f`](https://github.com/Abhiram-C-Divakaran/PawSOS/commit/04ffe2f9cd0a64ff9369fe87f42526e0178ee41f) (CI Run [`35465104021`](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35465104021), Staging Deployment & Smoke Tests Run [`35465336141`](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35465336141)).
> - **Authenticated Staging Pilot Execution**: Verified green (`SUCCESS`) in GitHub Actions Run [`35464082551`](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35464082551) at SHA [`def8de56c9a9323def930066b3ff8a4e3396a123`](https://github.com/Abhiram-C-Divakaran/PawSOS/commit/def8de56c9a9323def930066b3ff8a4e3396a123) (CI Run [`35463569514`](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35463569514), Deployment Run [`35463841324`](https://github.com/Abhiram-C-Divakaran/PawSOS/actions/runs/35463841324)) — executing all 10 live multi-role pilot stages (OAuth2 login, responder setup, synthetic evidence upload to private S3, dispatch offer & single-winner claim, BOLA/media boundary checks, atomic NGO case claim, rescue lifecycle progression, veterinary treatment, case closure, and state-preserving cleanup).
> - **Readiness Telemetry**: Deep subsystem checks operational (`database`, `postgis`, `redis` over TLS, `celery` worker heartbeat, and private `storage`).

---

## Architecture & Rescue Lifecycle

```text
Citizen Reports Animal (Upload validated photo + Pinpoint GPS on Leaflet Map)
        ↓
Synchronous Rule-Based Triage (Priority + Score: CRITICAL / URGENT / MODERATE / GENERAL)
        ↓
Optional Async Hybrid Visual Triage (Provider-neutral AI fusion; non-downgrade invariant)
        ↓
Case Stored in PostgreSQL 15 / PostGIS 3.4 (Spatial geography POINT)
        ↓
Automatic Background Dispatch (Celery + Redis Worker)
        ↓
Progressive Radius Escalation (5 km → 10 km → 20 km → 40 km waves)
        ↓
Web Push & In-App Notifications (Firebase Cloud Messaging + Service Worker)
        ↓
Rescuer Accepts Offer (Pessimistic row-level locking prevents race conditions)
        ↓
Responder Progression (ASSIGNED → EN_ROUTE → LOCATED → RESCUED → TRANSPORTING)
        ↓
Arrival at Authorized Veterinary Facility (Strictly scoped to facility ID)
        ↓
Veterinarian Records Treatment (Diagnosis, medications, clinical notes)
        ↓
Post-Treatment Continuum (UNDER_TREATMENT → RECOVERING → Foster Care / Ready for Release or Adoption)
        ↓
Case Resolution (RELEASED / ADOPTED → CLOSED)
```

If all 4 radius waves are exhausted without responder acceptance, the case automatically transitions to `UNRESOLVED` and generates urgent escalation alerts for NGO and System Administrators.

---

## Feature Matrix: Implemented vs. Optional vs. Future

| Capability | Status | Details |
|------------|--------|---------|
| **Citizen Reporting & Live Tracking** | **Implemented** | Multi-step wizard, Pillow-validated photo upload, Leaflet GPS picker, live status timeline. |
| **Deterministic Rule-Based Triage** | **Implemented** | Synchronous priority scoring (`CRITICAL`, `URGENT`, `MODERATE`, `GENERAL`) at intake. |
| **PostGIS Spatial Dispatch & Escalation** | **Implemented** | Composite responder scoring and automatic `5 → 10 → 20 → 40 km` Celery radius escalation. |
| **Single-Winner Atomic Claiming** | **Implemented** | Row-locked (`SELECT ... FOR UPDATE`) offer acceptance and NGO unassigned case claiming. |
| **Discovery & Location Privacy** | **Implemented** | Unoffered rescuers and unclaimed NGO queues cannot access exact coordinates, reporter PII, or evidence keys. |
| **Veterinary Inpatient & Treatment Portal** | **Implemented** | Facility-scoped inpatient registry, clinical diagnosis/medication logging, recovery progression. |
| **Multi-Tenant NGO Command Center** | **Implemented** | Live Leaflet map, hotspots, responder fleet, clinic capacities, audit logs, and analytics. |
| **Foster Care Operations (Phase 3A)** | **Implemented** | Caregiver profiles, NGO verification, deterministic foster matching, offer acceptance, care logs. |
| **Public Adoption Catalog & Workflow (Phase 3A)** | **Implemented** | Sanitized public listings, citizen applications, visit scheduling, transactional approval cascades. |
| **PWA & Installable Web Client (Phase 3C)** | **Implemented** | Web App Manifest (`manifest.json`), SVG app icons (`192x192`, `512x512`), mobile navigation, service worker registration. |
| **Private S3 Media with Presigned URLs** | **Implemented** | Canonical object keys, object-level access verification, short-lived presigned URLs. |
| **JWT + RefreshSession (`jti`) Revocation** | **Implemented** | Argon2 password hashing, single-device and global (`logout-all`) session invalidation. |
| **Hybrid AI Visual Triage (`GeminiVisionTriageProvider`)** | **Optional Integration** | Implemented behind `VisionTriageProvider` (`AI_TRIAGE_PROVIDER=gemini`). Disabled by default (`AI_TRIAGE_ENABLED=false`) unless `AI_TRIAGE_API_KEY` is configured. Never downgrades rule-based priority. |
| **Firebase Cloud Messaging (FCM) Web Push** | **Optional Integration** | Implemented in backend (`firebase-admin`) and frontend (`firebase-messaging-sw.js`). Graceful no-op fallback when `REQUIRE_FIREBASE=false` and credentials are unconfigured. |
| **Sentry Error Telemetry** | **Optional Integration** | Automatically enabled when `SENTRY_DSN` is provided. |
| **Native Flutter Mobile Apps / Local PyTorch & YOLO** | **Future / Conceptual** | Early design concepts superseded by the React 19 PWA and lightweight provider-neutral vision API to operate within 512 MB free-tier cloud containers. |

---

## Technology Stack

- **Frontend (Active Client)**: React 19, TypeScript, Vite, Tailwind CSS, React Router 7, Leaflet, Recharts, Lucide Icons, Vitest, Playwright (`frontend/`)
- **Backend**: Python 3.12+, FastAPI, SQLAlchemy 2, Alembic, GeoAlchemy2, PostgreSQL 15 + PostGIS 3.4, Pydantic v2, SlowAPI (`backend/`)
- **Background Workers**: Celery 5.6+ (Worker & Beat Scheduler), Redis 7 / Upstash Redis over TLS (`rediss://`)
- **Media & Security**: Pillow (25 MP decompression bomb guard + MIME verification), Boto3 S3 Private Storage, Argon2-CFFI, PyJWT

---

## Local Development Setup

### 1. Prerequisites
- Docker & Docker Compose
- Node.js 22+ / 24+
- Python 3.12+ (if running locally without Docker)

### 2. Full Stack with Docker Compose
```bash
git clone https://github.com/Abhiram-C-Divakaran/PawSOS.git
cd PawSOS

cp backend/.env.example backend/.env
docker compose up --build
```

Services started:
- **Frontend PWA**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000`
- **OpenAPI / Swagger Docs**: `http://localhost:8000/docs`
- **Deep Readiness Probe**: `http://localhost:8000/api/v1/health/ready`
- **PostgreSQL + PostGIS**: `localhost:5432`
- **Redis**: `localhost:6379`

### 3. Local Backend Development (Without Docker)
```bash
cd backend
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate # Linux/macOS

pip install -r requirements.txt
alembic upgrade head
python scripts/seed_staging.py

# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# In a separate terminal, start Celery Worker & Beat scheduler
celery -A app.tasks.celery_app worker -B --loglevel=info
```

### 4. Local Frontend Development
```bash
cd frontend
cp .env.example .env
npm ci
npm run dev
```

---

## Environment Variable Reference

### Backend (`backend/.env`)

| Variable | Required in Staging/Prod | Default (Dev) | Description |
|----------|--------------------------|---------------|-------------|
| `ENVIRONMENT` | **Yes** (`staging` / `production`) | `development` | Runtime environment mode; enables strict production security validators. |
| `PROCESS_TYPE` | **Yes** (`api` / `worker` / `beat` / `all`) | `api` | Process role selector for supervisor and startup validation. |
| `DATABASE_URL` | **Yes** (PostgreSQL + PostGIS) | `sqlite:///./pawsos.db` | SQLAlchemy connection string (SQLite is strictly forbidden in staging/prod). |
| `JWT_SECRET_KEY` | **Yes** ($\ge 32$ chars, non-default) | *(dev fallback)* | HMAC signing secret for access and refresh tokens. |
| `CORS_ORIGINS` | **Yes** (explicit origin list) | `http://localhost:5173,...` | Comma-separated allowed origins (wildcard `*` forbidden in staging/prod). |
| `REDIS_URL` | **Yes** (`redis://` or `rediss://`) | `redis://localhost:6379/0` | Redis broker/backend URL (normalized automatically for Upstash TLS). |
| `STORAGE_PROVIDER` | **Yes** (`s3`) | `local` | Evidence storage backend (`s3` required in staging/prod). |
| `AWS_ACCESS_KEY_ID` | **Yes** (when `s3`) | `""` | S3-compatible access key ID. |
| `AWS_SECRET_ACCESS_KEY` | **Yes** (when `s3`) | `""` | S3-compatible secret access key. |
| `AWS_REGION` | **Yes** (when `s3`) | `us-east-1` | S3 bucket region. |
| `S3_BUCKET_NAME` | **Yes** (when `s3`) | `""` | Private S3 bucket name for rescue evidence images. |
| `S3_ENDPOINT_URL` | Optional (required for Supabase S3) | `""` | Custom S3 endpoint URL. |
| `S3_FORCE_PATH_STYLE` | Optional | `false` | Set `true` for Supabase S3 path-style addressing. |
| `REQUIRE_FIREBASE` | Optional | `false` | If `true`, startup fails unless Firebase credentials are provided. |
| `FIREBASE_CREDENTIALS_JSON` | Optional | `""` | Inline JSON service account credentials for Firebase Admin SDK. |
| `AI_TRIAGE_ENABLED` | Optional | `false` | Enables asynchronous visual urgency triage. |
| `AI_TRIAGE_PROVIDER` | Optional | `disabled` | `disabled`, `gemini`, or `mock` (`mock` is blocked in staging/prod). |
| `AI_TRIAGE_API_KEY` | Required when `AI_TRIAGE_PROVIDER=gemini` | `""` | Google Gemini API key (sent via header only; never logged). |
| `AI_TRIAGE_MODEL_NAME` | Optional | `pawreach-vision-safety` | Gemini model identifier (uses `gemini-2.5-flash` when `gemini` is active). |
| `AI_TRIAGE_MIN_CONFIDENCE` | Optional | `0.70` | Minimum confidence threshold ($0.0\text{–}1.0$) required to escalate priority. |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_API_BASE_URL` | **Yes** | Backend API base URL (e.g., `http://localhost:8000/api/v1` or `https://pawreach-api.onrender.com/api/v1`). |
| `VITE_FIREBASE_API_KEY` | Optional | Firebase Web API key for browser push notifications. |
| `VITE_FIREBASE_AUTH_DOMAIN` | Optional | Firebase Auth domain. |
| `VITE_FIREBASE_PROJECT_ID` | Optional | Firebase Project ID. |
| `VITE_FIREBASE_STORAGE_BUCKET` | Optional | Firebase Storage bucket. |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Optional | Firebase Messaging Sender ID. |
| `VITE_FIREBASE_APP_ID` | Optional | Firebase Web App ID. |
| `VITE_FIREBASE_VAPID_KEY` | Optional | Web Push VAPID public key. |

---

## Running Test Suites & Release Gates

### 1. Backend Test Suite & Coverage ($\ge 85\%$ Required)
```bash
cd backend
pytest tests --cov=app --cov-report=term-missing -v
```

### 2. Frontend Lint, Unit Tests & Production Build
```bash
cd frontend
npm run lint          # oxlint static analysis
npm run test:coverage # Vitest unit & component tests
npm run build         # TypeScript check + Vite production bundle
```

### 3. Browser End-to-End Suites (Playwright)
```bash
cd frontend
# Mocked UI-contract E2E suite
npm run test:e2e:ui-contract

# Unmocked full-stack E2E suite (requires running PostgreSQL/PostGIS, Redis, Celery, and FastAPI)
npm run test:e2e:fullstack
```

---

## Zero-Cost Free Staging Deployment & Known Limitations

PawReach is deployed on zero-cost cloud tiers (`render.yaml`):
- **Backend**: Render Free Web Service (`pawreach-api` running FastAPI, Celery solo worker, and Celery Beat via `./scripts/start_free_render.sh`)
- **Frontend**: Render Free Static Site (`pawreach-frontend`)
- **Database & Storage**: Supabase Free PostgreSQL 15 + PostGIS 3.4 (Session Pooler on Port 5432) + Supabase S3 Private Storage (`evidence` bucket)
- **Broker**: Upstash Free Redis over TLS (`rediss://`)

> [!WARNING]
> **Known Operational Limitations (Free-Tier Demo)**:
> 1. **Render Free-Tier Sleep & Cold Start**: The Render free web service spins down after **15 minutes of inactivity**. The first request after an idle period incurs a **30–50 second cold-start delay**. During container sleep, background Celery dispatch sweeps pause. This hosted deployment is a demonstration environment and **not** 24/7 emergency response infrastructure.
> 2. **Optional External Credentials**: Firebase Cloud Messaging (`FIREBASE_CREDENTIALS_JSON` / `VITE_FIREBASE_*`) and Gemini Visual Triage (`AI_TRIAGE_API_KEY`) are optional integrations and remain disabled (`unconfigured` / `disabled`) in the public demo unless operator credentials are supplied.

---

## Staging Demo Accounts (`backend/scripts/seed_staging.py`)

Staging accounts are provisioned using the operator-configured `STAGING_SEED_PASSWORD` secret (minimum 14 characters, rotated via `.github/workflows/staging-rotate-credentials.yml`):

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

## Release Checklist (`v1.0.0`)

- [x] All backend unit, integration, security, and authorization tests passing with $\ge 85\%$ coverage
- [x] Frontend `oxlint`, Vitest unit suite, and production `tsc -b && vite build` passing with zero errors
- [x] Playwright UI-contract and unmocked full-stack E2E suites verified
- [x] Real external `GeminiVisionTriageProvider` implemented with strict non-downgrade safety, timeout enforcement, error sanitization, and zero PII/GPS leakage
- [x] Firebase service worker, PWA manifest/icons, duplicate device token handling, and safe deep-linking verified
- [x] Live staging deployment (`35465336141`) and authenticated multi-role staging pilot (`35464082551`) verified green

---

## Documentation Index
- [System Architecture](ARCHITECTURE.md)
- [Live Staging & Authenticated Pilot Validation Record](docs/LIVE_STAGING_VALIDATION.md)
- [Phase 3A: Foster & Adoption Operations](docs/PHASE_3A_FOSTER_ADOPTION.md)
- [Phase 3B: Hybrid AI-Assisted Visual Triage](docs/PHASE_3B_AI_TRIAGE.md)
- [Zero-Cost Free Cloud Deployment Guide](docs/FREE_DEPLOYMENT.md)
- [Operations Incident Runbook](docs/OPERATIONS_RUNBOOK.md)
- [Changelog](CHANGELOG.md)
