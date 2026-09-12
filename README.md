# PawReach (PawSOS) — MVP Phase 2.5

PawReach is an end-to-end stray animal rescue coordination platform connecting citizens, field rescuers, veterinary clinics, foster caregivers, NGOs, and municipal authorities.

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

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, GeoAlchemy2, PostgreSQL 15 + PostGIS 3.4
- **Background Workers**: Celery 5.6+, Redis 7
- **Push Notifications**: Firebase Admin SDK (Backend) + Firebase Cloud Messaging (Web Client)
- **Frontend**: React 19, TypeScript, Tailwind CSS, Leaflet / React-Leaflet, Vite, Vitest
- **Security**: Argon2 password hashing, JWT with `jti` session revocation (`RefreshSession`), HttpOnly Secure cookies, Role-Based Access Control, Tenant Organization & Veterinary Facility Scoping

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
- Health Check: `http://localhost:8000/health/ready`
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

# In a separate terminal, start the Celery Worker & Beat scheduler
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

### Backend Tests with Coverage
```bash
cd backend
pytest backend/tests --cov=app --cov-report=term-missing -v
```

Test suites cover:
- `test_background_dispatch.py`: Stale offer expiry via Celery worker, deterministic radius escalation (5 -> 10 -> 20 -> 40 km), responder exclusion, escalation to `UNRESOLVED`, admin alert distribution.
- `test_token_revocation.py`: Server-side `RefreshSession` tracking, token rotation, single device logout (`POST /auth/logout`), all device logout (`POST /auth/logout-all`), replay rejection.
- `test_scoping_security.py`: NGO Admin Org A isolation from Org B cases/responders/stats, Super Admin global access, Veterinary Facility A isolation from Facility B cases.
- `test_pilot_scenarios.py`: End-to-end execution of all 5 operational pilot scenarios without manual database edits.
- `test_dispatch_engine.py`: Composite dispatch scoring, row-locking race conditions, rejection reasons.
- `test_e2e_rescue_lifecycle.py`: Complete lifecycle from reporting to release.

### Frontend Quality & Tests
```bash
cd frontend
npm run lint          # oxlint checks
npm run test:coverage # Vitest unit tests with coverage
npm run build         # Production TypeScript build
```

---

## Staging & Production Deployment

### 1. Database (PostgreSQL + PostGIS)
- Deploy PostgreSQL 15+ with PostGIS extension enabled (`CREATE EXTENSION IF NOT EXISTS postgis;`).
- Run database migrations: `alembic upgrade head`.
- Seed initial staging data: `python scripts/seed_staging.py`.

### 2. Redis & Celery Worker
- Provision a Redis instance (e.g. Railway, Redis Cloud, Upstash).
- Set `REDIS_URL=redis://<user>:<pass>@<host>:<port>/0`.
- Deploy worker container:
  ```bash
  celery -A app.tasks.celery_app worker -B --loglevel=info
  ```

### 3. Cloud Storage (S3)
- Set in backend environment:
  ```text
  STORAGE_PROVIDER=s3
  AWS_ACCESS_KEY_ID=<key>
  AWS_SECRET_ACCESS_KEY=<secret>
  AWS_REGION=<region>
  S3_BUCKET_NAME=<bucket>
  ```
- Images are automatically resized (max dimension 2048px), compressed, and EXIF metadata stripped via Pillow.

### 4. Firebase Cloud Messaging (Web Push)
- Place service account JSON file on backend and set:
  ```text
  FIREBASE_CREDENTIALS_PATH=/etc/secrets/firebase-adminsdk.json
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

## Staging Test Accounts (from `seed_staging.py`)

All staging accounts share the default password: `StagingPass123!`

| Role | Email | Phone | Scope / Affiliation |
|------|-------|-------|---------------------|
| Citizen | `citizen@staging.pawsos.org` | `+919876543210` | Public Reporter |
| Rescuer A | `rescuer.a@staging.pawsos.org` | `+919876543211` | Cochin Animal Rescue Network (Kochi Marine Drive) |
| Rescuer B | `rescuer.b@staging.pawsos.org` | `+919876543212` | Cochin Animal Rescue Network (Kochi Kaloor) |
| Veterinarian | `vet@staging.pawsos.org` | `+919876543213` | Cochin PetCare Emergency Hospital |
| NGO Admin | `admin@staging.pawsos.org` | `+919876543214` | Cochin Animal Rescue Network |
| Super Admin | `superadmin@staging.pawsos.org` | `+919876543215` | Global Operations |

---

## Operational Documentation
- [Pilot Verification Checklist](docs/PILOT_CHECKLIST.md)
- [Operations Incident Runbook](docs/OPERATIONS_RUNBOOK.md)
