# PawReach (PawSOS)

PawReach is an end-to-end stray animal rescue coordination platform connecting citizens, field rescuers, veterinary clinics, foster caregivers, NGOs, and municipal authorities.

## Core End-to-End Workflow

```text
Citizen Registers (Role locked to CITIZEN)
        ↓
Citizen Logs In (Access + Refresh JWT with signature verification)
        ↓
Citizen Reports Animal (Upload real photo + Pinpoint real GPS on Leaflet map)
        ↓
Rule-Based Triage (Priority + Score: CRITICAL/URGENT/MODERATE/GENERAL)
        ↓
Case Stored in PostgreSQL/PostGIS (Geography POINT with spatial indexing)
        ↓
Geospatial Rescuer Dispatch (PostGIS ST_DWithin / Geodesic distance calculation)
        ↓
Rescuer Accepts (Row-level transactional locking prevents concurrent race conditions)
        ↓
Responder Status Progression (RESPONDER_ASSIGNED → EN_ROUTE → LOCATED → RESCUED → TRANSPORTING)
        ↓
Live Citizen Tracking (Real-time polling, timeline history, Leaflet case map)
        ↓
Arrival at Verified Veterinary Facility (AT_VETERINARY_FACILITY)
        ↓
Veterinarian Records Treatment (Diagnosis, medications, treatment notes)
        ↓
Medical Recovery (UNDER_TREATMENT → RECOVERING → READY_FOR_RELEASE)
        ↓
Case Closure (RELEASED / ADOPTED → CLOSED)
```

---

## Getting Started

### Prerequisites
- Node.js 20+
- Python 3.11+ (or Docker & Docker Compose)

---

### Backend Setup

#### Option A: Docker Compose (PostgreSQL + PostGIS + FastAPI)
```bash
cd backend
cp .env.example .env
docker compose up --build
```
The backend automatically runs Alembic migrations (`alembic upgrade head`) and waits for the database health check.

#### Option B: Local Python Development
```bash
cd backend
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
alembic upgrade head
python seed.py
uvicorn app.main:app --reload --port 8000
```

Swagger API Documentation is available at:
`http://localhost:8000/docs`

---

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The React + TypeScript + Vite app will start at `http://localhost:5173`.

---

## Running Tests

### Backend Test Suite (Pytest)
```bash
cd backend
pytest -vv
```
Covers:
- `tests/test_auth.py`: Citizen registration, role escalation prevention, OAuth2 login, refresh tokens, invalid/expired tokens.
- `tests/test_rescue.py`: Case reporting, triage calculation, status progression, invalid status transitions (409 Conflict).
- `tests/test_permissions.py`: Citizen status restrictions (403 Forbidden), rescuer diagnosis restrictions, access control scoping.
- `tests/test_dispatch.py`: PostGIS spatial distance filtering, radius expansion, concurrent acceptance row-locking.
- `tests/test_veterinary.py`: Dedicated facility inbox, treatment record creation, recovery status tracking.

### Frontend Test Suite (Vitest + React Testing Library)
```bash
cd frontend
npm test
npm run test:coverage
```
Covers:
- `src/test/Auth.test.tsx`: Form rendering, OAuth2 payload generation, role escalation exclusion, password match validation.
- `src/test/ReportRescue.test.tsx`: Species selection, photo upload validation, GPS location map picker, condition triage flags, review.
- `src/test/CaseTracking.test.tsx`: Case details, live status badges, timeline milestones, restricted access handling.

---

## Demo Credentials (from `seed.py`)

| Role | Email | Password |
|------|-------|----------|
| Citizen | `citizen@demo.com` | `password123` |
| Rescuer | `rescuer@demo.com` | `password123` |
| Veterinarian | `vet@demo.com` | `password123` |
| NGO Admin | `admin@demo.com` | `password123` |
