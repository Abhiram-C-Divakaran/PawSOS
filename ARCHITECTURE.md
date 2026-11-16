# PawReach – System Architecture

> [!IMPORTANT]
> **Implementation Status (v1.0.0)**:
> - **Active Client Architecture**: **React 19 + TypeScript + Vite Progressive Web Application (PWA)** serving all operational roles (Citizens, Field Rescuers, Veterinarians, Foster Caregivers, NGO Administrators, and Super Administrators) from a single responsive, installable web client (`frontend/`).
> - **Active Backend Architecture**: **FastAPI (Python 3.12+) + SQLAlchemy 2 + Alembic + PostgreSQL 15 / PostGIS 3.4 + Upstash Redis (TLS) + Celery Worker & Beat + Supabase S3-Compatible Private Storage** (`backend/`).
> - **Hybrid AI-Assisted Visual Triage**: Provider-neutral decision-support interface (`backend/app/ai/`) combining synchronous deterministic rule-based intake with optional asynchronous visual urgency evaluation (`GeminiVisionTriageProvider`). Strictly non-diagnostic and fail-closed (AI can **never** downgrade rule-based urgency). Disabled by default (`AI_TRIAGE_ENABLED=false`) in the zero-cost staging demo unless an external API key is configured.
> - **Historical / Conceptual Design Notes**: Early planning references to native Flutter mobile apps, local PyTorch/YOLO/OpenCV inference, and Cloudinary media hosting are preserved in [Section 15 (Historical & Future Conceptual Notes)](#15-historical--future-conceptual-notes) and are **not** part of the active runtime.

---

## 1. Architecture Overview

PawReach follows a **layered client-server architecture** designed for high-reliability emergency rescue coordination and strict multi-tenant data isolation:

1. **Client Layer**: React 19 / TypeScript / Tailwind CSS / Leaflet PWA (`frontend/`)
2. **API & Security Layer**: FastAPI REST API, JWT + `RefreshSession` (`jti`) revocation, RBAC, and fail-closed object/tenant authorization (`backend/app/api/`, `backend/app/core/`)
3. **Domain & Business Logic Layer**: Triage Engine, Spatial Dispatch & Progressive Escalation, Veterinary Intake, Foster Matching, and Adoption Cascade Services (`backend/app/services/`)
4. **Asynchronous Task & AI Layer**: Celery Worker & Beat Scheduler over Redis TLS (`backend/app/tasks/`) + Provider-Neutral Visual Triage Fusion (`backend/app/ai/`)
5. **Spatial & Relational Data Layer**: PostgreSQL 15 + PostGIS 3.4 (`backend/app/models/`, `backend/alembic/`)
6. **Private Media & Notification Layer**: Private S3-Compatible Object Storage with short-lived presigned URLs (`backend/app/services/storage_service.py`) and optional Firebase Cloud Messaging (`backend/app/services/notification_service.py`)

---

## 2. High-Level Implemented Architecture

```text
                      ┌────────────────────────────────────────┐
                      │                 USERS                  │
                      │                                        │
                      │ Citizen | Rescuer | Veterinarian       │
                      │ Foster Caregiver | NGO Admin | Admin   │
                      └───────────────────┬────────────────────┘
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │         REACT 19 PWA FRONTEND          │
                      │   (TypeScript + Vite + Tailwind CSS)   │
                      │                                        │
                      │ • Citizen Report & Live Case Tracking  │
                      │ • Rescuer GPS & Dispatch Offer Console │
                      │ • Veterinary Clinical Inpatient Portal │
                      │ • Foster Caregiver Hub & Care Logs     │
                      │ • Public Adoption Catalog & Apply Flow │
                      │ • NGO Command Center & Analytics       │
                      │ • Web App Manifest + FCM ServiceWorker │
                      └───────────────────┬────────────────────┘
                                          │
                                        HTTPS
                                          │
                                          ▼
                      ┌────────────────────────────────────────┐
                      │            FASTAPI BACKEND             │
                      │                                        │
                      │ • Auth (Argon2 + JWT + RefreshSession) │
                      │ • Rule-Based Emergency Triage          │
                      │ • Rescue Lifecycle & Row-Locked Claims │
                      │ • Multi-Tenant NGO Isolation           │
                      │ • Veterinary Facility Scoping          │
                      │ • Foster Matching & Adoption Cascades  │
                      └──────┬────────────┬─────────────┬──────┘
                             │            │             │
                 ┌───────────┘            │             └────────────┐
                 ▼                        ▼                          ▼
     ┌──────────────────────┐  ┌─────────────────────┐  ┌────────────────────────┐
     │   REDIS + CELERY     │  │  POSTGRESQL 15      │  │   EXTERNAL SERVICES    │
     │   BACKGROUND TASKS   │  │  + POSTGIS 3.4      │  │                        │
     │                      │  │                     │  │ • Private S3 Storage   │
     │ • Dispatch Waves     │  │ • Users & Sessions  │  │   (Presigned URLs)     │
     │   (5→10→20→40 km)    │  │ • Rescue Cases      │  │ • OpenStreetMap /      │
     │ • Offer Expiry Sweep │  │   (Geography POINT) │  │   Leaflet Tiles        │
     │ • Worker Heartbeat   │  │ • Dispatch Offers   │  │ • Firebase FCM Push    │
     │ • Async AI Visual    │  │ • Treatments        │  │   (Optional)           │
     │   Triage Fusion      │  │ • Foster & Adoption │  │ • Gemini Vision API    │
     └──────────────────────┘  │ • Audit Trail Logs  │  │   (Optional)           │
                               └─────────────────────┘  └────────────────────────┘
```

---

## 3. Client Layer (React 19 PWA)

The active client is a unified **React 19 Progressive Web Application** (`frontend/src/`) with route-level code splitting (`React.lazy`), role-protected routes (`ProtectedRoute`), and installable PWA metadata (`frontend/public/manifest.json`, `/icons/icon-192.svg`, `/icons/icon-512.svg`).

### 3.1 Citizen Experience
* Register, sign in, and manage authenticated sessions.
* Submit multi-step emergency animal reports (`/report`) with photo upload (validated JPG/PNG/WEBP up to 10 MB), interactive Leaflet GPS pin selection (`MapPicker`), and emergency condition questionnaire.
* Track reported cases in real time (`/my-cases`, `/cases/:id`) with live timeline updates, responder assignment status, and hybrid triage advisories (`TriageAdvisoryCard`).
* Browse verified adoptable animals (`/adopt`, `/adopt/:listingId`), submit adoption applications (`/adopt/:listingId/apply`), and track application/visit status (`/adoption-applications`).

### 3.2 Field Rescuer Console (`/rescuer`)
* Synchronize live GPS coordinates (`PATCH /api/v1/rescuers/me/location`).
* View coarse-location nearby emergency discovery summaries (`GET /api/v1/rescues/nearby` — exact coordinates and reporter PII remain protected prior to dispatch offer issuance).
* Receive real-time countdown dispatch offers (`GET /api/v1/rescuers/me/offers`) and atomically accept (`POST /api/v1/rescuers/offers/{offer_id}/accept`) or decline with an auditable reason.
* Progress active rescue missions through `RESPONDER_ASSIGNED` → `RESPONDER_EN_ROUTE` → `ANIMAL_LOCATED` → `RESCUED` → `TRANSPORTING` → `AT_VETERINARY_FACILITY`.

### 3.3 Veterinary Clinical Portal (`/vet`)
* View facility-scoped inpatient cases (`GET /api/v1/veterinary/cases`).
* Record clinical diagnoses, prescribed medications, and treatment plans (`POST /api/v1/rescues/{case_id}/treatments`) strictly scoped to the veterinarian's authorized facility.
* Progress patient recovery (`UNDER_TREATMENT` → `RECOVERING` → `READY_FOR_RELEASE` / `READY_FOR_ADOPTION` / `CLOSED`).

### 3.4 Foster Caregiver Hub (`/foster`)
* Create and manage foster home profiles (coarse locality, capacity, accepted species, medical care capability, availability status).
* Accept or decline NGO foster placement offers and log structured daily care updates (appetite, mobility, medication administration, behavioral notes).

### 3.5 NGO Operations Command Center (`/ngo/*`)
* **Overview (`/ngo`)**: Real-time KPI cards, live Leaflet operational map, spatial hotspots, active case roster, and response-time telemetry.
* **Cases & Dossier (`/ngo/cases`, `/ngo/cases/:id`)**: Filterable case registry, atomic unassigned case claiming (`POST /api/v1/ngo/cases/{case_id}/claim`), dispatch offer audit trail, visual triage retry, and auditable administrative overrides (re-dispatch, manual responder assignment, clinic transfer, case cancellation).
* **Responder Fleet (`/ngo/responders`)**: Live readiness, reliability scores, active mission tracking, and activation controls.
* **Veterinary Partners (`/ngo/veterinary`)**: Authorized clinic capacities and patient intake occupancy.
* **Foster Operations (`/ngo/foster`)**: Caregiver home verification, deterministic foster candidate scoring/matching, and placement offer dispatch.
* **Adoption Operations (`/ngo/adoptions`)**: Public listing publication, citizen application review, meet-and-greet visit scheduling, and transactional adoption approval cascades.
* **Analytics, Organization & Settings (`/ngo/analytics`, `/ngo/organization`, `/ngo/settings`)**: Historical response trends, outcome breakdowns, tenant profile management, notification preferences, and global session revocation.

---

## 4. Emergency Triage & Hybrid AI Decision Architecture

### 4.1 Synchronous Rule-Based Triage (`backend/app/services/triage_service.py`)
Every rescue report is immediately scored synchronously at intake using deterministic safety rules:
* **Priority 1 (`CRITICAL`)**: Unconscious/unresponsive animal, or vehicle collision combined with active bleeding or inability to walk, or severe breathing difficulty with trauma.
* **Priority 2 (`URGENT`)**: Active bleeding, inability to walk, vehicle collision, or breathing difficulty.
* **Priority 3 (`MODERATE`)**: Multiple moderate distress indicators.
* **Priority 4 (`GENERAL`)**: Welfare/stray report without acute emergency flags.

### 4.2 Asynchronous Hybrid Visual Triage (`backend/app/ai/` & `backend/app/tasks/ai_triage_tasks.py`)
When `AI_TRIAGE_ENABLED=true` and an evidence photo is attached, a background Celery task evaluates the image via the pluggable `VisionTriageProvider` interface:
* **Implemented Providers**:
  * `DisabledVisionTriageProvider` (`disabled`): Default safe no-op provider.
  * `GeminiVisionTriageProvider` (`gemini`): Real external multimodal vision provider calling Google Gemini Vision over HTTPS (`httpx`) with strict timeout enforcement, structured JSON schema validation, and non-diagnostic urgency instructions.
  * `MockVisionTriageProvider` (`mock`): Deterministic test fixture restricted strictly to automated tests and local development (blocked by runtime guardrails in `staging` and `production`).
* **Strict Privacy Boundary**: The provider receives **only** validated raw image bytes and the animal species string. Citizen PII, reporter IDs, case IDs, street addresses, exact GPS coordinates, and storage URLs are never transmitted.
* **Non-Downgrade Safety Invariant (`HybridTriageFusionEngine`)**:
  $$\text{Final Priority} = \max\left(\text{Rule Priority},\; \text{AI Suggested Priority (if confidence} \ge \tau\text{)}\right)$$
  AI can corroborate or escalate priority when confidence meets `AI_TRIAGE_MIN_CONFIDENCE` (default `0.70`), but can **never** downgrade a rule-based priority or override a `CRITICAL` rule result. Any provider timeout or error fails closed to rule-based triage.

---

## 5. Spatial Dispatch & Progressive Escalation Architecture

1. **Spatial Candidate Discovery**: PostgreSQL/PostGIS `ST_DWithin` and `ST_Distance` query available, active responders with fresh GPS locations (`RESPONDER_LOCATION_STALE_MINUTES`, default 30 min).
2. **Composite Responder Scoring**:
   $$\text{Score} = 0.40 \times \text{Distance} + 0.25 \times \text{Availability} + 0.15 \times \text{Experience} + 0.10 \times \text{Vehicle} + 0.10 \times \text{Reliability}$$
3. **Progressive Radius Waves**: Offers are issued in waves across `5 km → 10 km → 20 km → 40 km`. Each wave expires after `DISPATCH_OFFER_EXPIRY_SECONDS` (90s) if unaccepted. If all 4 waves are exhausted, the case transitions to `UNRESOLVED` and alerts NGO Administrators.
4. **Single-Winner Transactional Locking**: Accepting a dispatch offer (`POST /api/v1/rescuers/offers/{offer_id}/accept`) or claiming/assigning a case acquires pessimistic row locks (`SELECT ... FOR UPDATE`), verifies an active `PENDING` offer, cancels competing offers atomically, and prevents race conditions.

---

## 6. Private Media Storage Architecture

Evidence photos are never stored in PostgreSQL and raw S3 object keys are never exposed publicly:
1. Uploaded images are validated via Pillow (`StorageService.validate_image`) for decompression bombs ($\le 25\text{ MP}$), file size ($\le 10\text{ MB}$), and true binary format matching MIME (`JPEG`, `PNG`, `WEBP`).
2. Images are stored in a private S3-compatible bucket (`STORAGE_PROVIDER=s3` in staging/production; local filesystem in development).
3. Viewing an evidence image requires calling `GET /api/v1/rescues/{case_id}/images/{image_id}/access`, which enforces object-level authorization (reporter, assigned responder, admitting veterinary facility, or owning NGO tenant) before minting a short-lived presigned URL (`S3_PRESIGNED_URL_EXPIRE_SECONDS`, default 900s).

---

## 7. Security & Multi-Tenant Isolation

* **Authentication & Session Revocation**: Argon2id password hashing (`argon2-cffi`), short-lived JWT access tokens, and stateful refresh tokens tracked in `refresh_sessions` (`jti`) supporting single-device logout, global session revocation (`POST /api/v1/auth/logout-all`), and replay detection.
* **Discovery Privacy**: `GET /api/v1/rescues/nearby` and unassigned rows in `GET /api/v1/ngo/cases` strip reporter PII, exact coordinates, street addresses, and evidence keys until a dispatch offer is issued or an NGO atomically claims the case (`POST /api/v1/ngo/cases/{case_id}/claim`).
* **NGO Tenant Isolation**: `require_ngo_org_scope` enforces strict `organization_id` boundaries across cases, responders, foster homes, adoption listings, and analytics.
* **Veterinary Facility Scoping**: Clinical treatment logging (`POST /api/v1/rescues/{case_id}/treatments`) requires exact `case.veterinary_facility_id == current_user.veterinary_facility_id`.
* **HTTP Hardening**: Explicit CORS origin validation (wildcards prohibited in staging/production), SlowAPI rate limiting, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, and `Strict-Transport-Security` on HTTPS.

---

## 8. Zero-Cost Cloud Staging Topology & Operational Characteristics

```text
Browser / Mobile PWA Client
            │
            ▼
   Render Free Static Site
     (pawreach-frontend)
            │
          HTTPS
            │
            ▼
  Render Free Web Service
       (pawreach-api)
  ┌───────────────────────────┐
  │ ./scripts/start_free_render.sh │
  │ • FastAPI (Uvicorn)       │
  │ • Celery Worker (solo)    │
  │ • Celery Beat Scheduler   │
  └─────────────┬─────────────┘
                │
        ┌───────┴────────┐
        ▼                ▼
Supabase Free      Upstash Free
PostgreSQL 15      Redis (TLS)
+ PostGIS 3.4      rediss://
+ Private S3
```

> [!WARNING]
> **Free-Tier Render Sleep Limitation**:
> - Render's free web container spins down after **15 minutes of inactivity**.
> - The first request after an idle period incurs a **30–50 second cold-start delay** while the container boots and supervisord starts FastAPI, the Celery solo worker, and Celery Beat.
> - While the container is asleep, background dispatch sweeps pause. The hosted staging environment is a portfolio demonstration deployment and **not** 24/7 emergency response infrastructure.

---

## 9. Historical & Future Conceptual Notes

The following concepts from early project ideation are **not** part of the active v1.0 implementation and are recorded strictly as future architectural directions:
* **Native Mobile Clients (Flutter / Dart)**: Replaced in v1.0 by the responsive, installable React 19 Progressive Web Application (`frontend/`) to support all roles across mobile and desktop browsers with zero app-store distribution overhead.
* **Local Heavyweight Vision Models (PyTorch / YOLO / OpenCV)**: Replaced in Phase 3B by the lightweight, memory-safe `VisionTriageProvider` abstraction (`backend/app/ai/`) and optional external multimodal API integration (`GeminiVisionTriageProvider`) so the backend operates reliably within 512 MB free-tier container limits.
* **Cloudinary Media Hosting**: Replaced by S3-compatible private bucket storage (Supabase Storage S3 API) with server-authorized presigned URLs.
* **Future Enhancements**: Automated perceptual-hash duplicate report clustering, live in-app chat between citizens and responders, and municipal sterilization billing workflows.
