# PawReach / PawSOS — Staging Deployment & Operations Guide
**Phase 2.6 — Pilot Readiness & Staging Operations**

This runbook outlines the required infrastructure, environment configurations, deployment commands, readiness verification steps, and operational procedures for deploying the PawReach platform to a staging or production pilot environment.

---

## 1. Architecture & Infrastructure Requirements

| Service | Min. Version | Recommended Spec | Purpose |
| :--- | :--- | :--- | :--- |
| **PostgreSQL** | 15+ (with PostGIS 3+) | 2 vCPU, 4GB RAM | Primary relational & spatial database |
| **Redis** | 7.0+ | 1 vCPU, 2GB RAM | Celery message broker & result backend, rate limiting |
| **Celery Worker** | 5.3+ | 2 vCPU, 2GB RAM | Background dispatch engine, radius escalation, push jobs |
| **Celery Beat** | 5.3+ | 1 vCPU, 1GB RAM | Periodic task scheduler (offer expirations, heartbeats) |
| **FastAPI Backend** | Python 3.11+ | 2 vCPU, 2GB RAM | Async REST API, auth, business logic |
| **Vite Frontend (PWA)** | Node 18+ / Nginx | 1 vCPU, 1GB RAM | React + Tailwind dashboard, PWA service worker |
| **Object Storage** | AWS S3 / MinIO | S3-compatible | Animal evidence images, resized thumbnails (Lanczos) |
| **Firebase Cloud Messaging** | Admin SDK v6+ | Cloud Service | Real-time push alerts to mobile & desktop browsers |
| **Sentry** | Latest SDK | Cloud Service | Error tracking & telemetry |

---

## 2. Environment Variables Configuration

Create a production-grade `.env` in the root of the backend deployment. **Never commit secret keys or service account credentials to Git.**

```bash
# ==========================================
# Core Environment Settings
# ==========================================
ENVIRONMENT=staging
PROJECT_NAME="PawReach Staging"
DEBUG=false
JWT_SECRET_KEY="<GENERATE_SECURE_64_CHAR_HEX_KEY_MIN_32_CHARS>"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ==========================================
# Database & Spatial Engine (PostGIS)
# ==========================================
DATABASE_URL="postgresql://pawreach_user:<STRONG_PASSWORD>@db.staging.internal:5432/pawreach_staging"

# ==========================================
# Redis & Celery Task Queue
# ==========================================
REDIS_URL="redis://:redis_password@redis.staging.internal:6379/0"

# ==========================================
# CORS & Allowed Origins
# ==========================================
CORS_ORIGINS="https://staging.pawreach.org,https://admin.staging.pawreach.org"

# ==========================================
# Cloud Object Storage (S3 / MinIO)
# Note: In 'staging' and 'production', S3 credentials are strictly verified.
# ==========================================
STORAGE_PROVIDER=s3
AWS_ACCESS_KEY_ID="<AWS_IAM_ACCESS_KEY>"
AWS_SECRET_ACCESS_KEY="<AWS_IAM_SECRET_KEY>"
AWS_REGION="ap-south-1"
S3_BUCKET_NAME="pawreach-staging-media"

# ==========================================
# Firebase Cloud Messaging (Web Push Alerts)
# ==========================================
FIREBASE_CREDENTIALS_PATH="/etc/secrets/pawreach-firebase-admin.json"
FIREBASE_PROJECT_ID="pawreach-staging"

# ==========================================
# Monitoring & Telemetry (Sentry)
# ==========================================
SENTRY_DSN="https://<public_key>@o0.ingest.sentry.io/<project_id>"
```

---

## 3. Database Migration & Initialization

Run migrations before launching or rolling out new backend containers:

```bash
# Run Alembic migrations to apply schema updates
cd backend
alembic upgrade head

# Verify migration status
alembic current
```

---

## 4. Process Launch Commands

### A. FastAPI Application Server (Uvicorn / Gunicorn)
```bash
gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
```

### B. Celery Background Worker
```bash
celery -A app.tasks.celery_app worker \
  --loglevel=INFO \
  --concurrency=4 \
  --queues=dispatch,notifications,default \
  -n worker_pawreach_staging@%h
```

### C. Celery Beat Scheduler
```bash
celery -A app.tasks.celery_app beat \
  --loglevel=INFO \
  --pidfile=/tmp/celerybeat.pid \
  --schedule=/tmp/celerybeat-schedule
```

### D. Frontend Production Build & Static Serving
```bash
cd frontend
npm ci
npm run build
# The 'dist' directory is deployed to Nginx / Cloudflare Pages / AWS S3 + CloudFront
```

---

## 5. Health & Readiness Verification

PawReach includes deep health probes to confirm all subsystems are operational prior to routing pilot traffic.

### A. Basic Liveness Check
```http
GET /api/v1/health
```
Response:
```json
{
  "status": "healthy",
  "environment": "staging",
  "version": "2.0.0"
}
```

### B. Deep Readiness Probe (Verifies 6 Subsystems)
```http
GET /api/v1/health/readiness
```
Alias: `GET /api/v1/health/ready`

Response:
```json
{
  "status": "ready",
  "services": {
    "database": "connected",
    "spatial_postgis": "available",
    "redis": "connected",
    "celery": "ready",
    "storage": "connected",
    "firebase": "configured"
  }
}
```
*If any required service fails (e.g., Celery worker offline, PostGIS extension missing), HTTP 503 is returned with specific error details.*

---

## 6. Pilot Operational Verification Procedures

### Step 1: Storage & Image Processing Pipeline
1. Post image evidence via `POST /api/v1/uploads/image`.
2. Confirm image is converted to WebP with EXIF orientation metadata safely transposed.
3. Confirm Lanczos downscaling caps max dimension to 2048px.
4. Verify oversized files (>10MB) or fake MIME types (`application/x-msdownload`) are rejected with `400 Bad Request`.

### Step 2: Tenant Scoping & Isolation
1. Authenticate as NGO Admin A (`org_id: 1`).
2. Attempt to query rescue cases or patch organization details for NGO B (`org_id: 2`).
3. Verify backend strictly responds with `403 Forbidden` or `404 Not Found`.
4. Inspect `audit_logs` table to ensure unauthorized attempts and profile changes are immutably logged with actor ID and IP address.

### Step 3: Progressive Radius Escalation
1. Create a `CRITICAL` rescue case.
2. Confirm initial dispatch wave searches within 5 km.
3. Observe Celery beat worker expire unresponsive offers at 20 seconds.
4. Confirm radius escalation progression: 5 km → 10 km → 20 km → 40 km.
5. If no responder accepts across all 4 waves, verify case transitions to `UNRESOLVED` and critical alert is delivered.

### Step 4: Web Push Diagnostics
1. In NGO Settings (`/ngo/settings`), click **Send Test Notification**.
2. Confirm browser displays native push notification with action buttons.
3. Check notification bell and ensure unread badge updates reactively.

---

## 7. Disaster Recovery & Rollback Plan

1. **Database Snapshot**: Ensure automated daily snapshots + WAL archiving are active in RDS/PostgreSQL.
2. **Migration Rollback**: To revert an Alembic migration:
   ```bash
   alembic downgrade -1
   ```
3. **Session Revocation**: In event of suspected credential compromise, issue global logout:
   ```bash
   POST /api/v1/auth/logout-all
   ```
   This immediately revokes all refresh tokens and sessions for the user across all devices.
