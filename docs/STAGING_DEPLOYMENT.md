# PawReach — Staging Deployment & Operations Guide
**Phase 2.9 — Staging Deployment, Security Hardening & Pilot Certification**

This document outlines the architecture, environment configurations, deployment manifests, database initialization, process management, readiness verification, and operational procedures for deploying PawReach to a staging environment.

---

## 1. Process & Service Architecture

In staging and production, PawReach runs as separate, dedicated services to guarantee performance, resilience, and horizontal scalability:

```
                                +---------------------------+
                                |  Nginx (Frontend SPA)     |
                                |  Port 80 / 443            |
                                +---------------------------+
                                              |
                                              | Reverse Proxy /api/
                                              v
+-----------------------+       +---------------------------+       +-----------------------+
|  Celery Beat          |       |  FastAPI Web Server       | ----> |  PostgreSQL + PostGIS |
|  (Scheduler)          |       |  Port 8000 (Gunicorn/Uvic)|       |  Port 5432            |
+-----------------------+       +---------------------------+       +-----------------------+
            |                                 |                                 ^
            | Enqueue periodic                | Enqueue tasks                   | Query state
            v                                 v                                 |
+-----------------------------------------------------------+                   |
|                        Redis Broker                       |                   |
|                        Port 6379                          |                   |
+-----------------------------------------------------------+                   |
            |                                                                   |
            v Dequeue dispatch & push jobs                                      |
+-------------------------------------------------------------------------------+
|  Celery Worker (dispatch, notifications, default queues)                      |
+-------------------------------------------------------------------------------+
            |
            +---> AWS S3 (Object Storage for evidence & records)
            +---> Firebase Cloud Messaging (Web Push alerts)
```

| Service Name | Command / Entrypoint | Scaling | Responsibilities |
| :--- | :--- | :--- | :--- |
| **`web`** | `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000` | Horizontal ($\ge 2$) | REST API endpoints, auth, webhooks |
| **`worker`** | `celery -A app.tasks.celery_app worker -l INFO -c 4 -Q dispatch,notifications,default` | Horizontal ($\ge 2$) | Asynchronous dispatch engine, push notifications, image processing |
| **`beat`** | `celery -A app.tasks.celery_app beat -l INFO --pidfile=/tmp/celerybeat.pid` | **Singleton (Exactly 1)** | Offer expiration (20s staging / 90s prod), worker heartbeats (10s) |
| **`db`** | PostgreSQL 15+ with PostGIS 3+ | Primary + Replica | Relational data, spatial indexing, audit logs |
| **`redis`** | Redis 7+ | Standalone / Cluster | Celery message broker, task results, rate limiting, heartbeats |
| **`frontend`** | Nginx serving built static assets (`frontend/dist`) | Multi-replica / CDN | React 19 SPA, route-level code splitting, PWA service worker |

---

## 2. Environment Variables Configuration

In staging, the backend enforces strict validation at startup via `app/config.py:validate_production_settings()`. Any missing, default, or insecure configuration causes an immediate startup failure (`SystemExit(1)`).

Create `backend/.env`:

```bash
# ==========================================
# Core Environment Settings
# ==========================================
ENVIRONMENT=staging
PROJECT_NAME="PawReach Staging"
DEBUG=false
# Minimum 32 chars, cannot contain 'secret', 'default', or 'changeme'
JWT_SECRET_KEY="<GENERATE_64_CHAR_HEX_KEY_e.g._openssl_rand_-hex_32>"
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ==========================================
# Database & Spatial Engine (PostGIS)
# NOTE: SQLite is strictly forbidden in staging
# ==========================================
DATABASE_URL="postgresql://pawreach_user:<STRONG_PASSWORD>@db.staging.internal:5432/pawreach_staging"

# ==========================================
# Redis Task Broker & Cache
# ==========================================
REDIS_URL="redis://:redis_password@redis.staging.internal:6379/0"

# ==========================================
# CORS & Allowed Origins
# NOTE: Wildcard '*' is strictly forbidden in staging
# ==========================================
CORS_ORIGINS="https://staging.pawreach.org,https://admin.staging.pawreach.org,http://localhost:5173"

# ==========================================
# Cloud Object Storage (S3 / MinIO)
# NOTE: All S3 keys required when STORAGE_PROVIDER=s3
# ==========================================
STORAGE_PROVIDER=s3
AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_REGION="ap-south-1"
S3_BUCKET_NAME="pawreach-staging-media"

# ==========================================
# Firebase Cloud Messaging (Web Push Alerts)
# ==========================================
FIREBASE_CREDENTIALS_PATH="/etc/secrets/firebase-admin.json"
FIREBASE_PROJECT_ID="pawreach-staging"

# ==========================================
# Staging Seed Security Password
# Must be >= 14 chars, not obvious/default patterns
# ==========================================
STAGING_SEED_PASSWORD="<STRONG_PILOT_PASSWORD_MIN_14_CHARS_!>"
```

---

## 3. Database Initialization & Seeding Workflow

> [!IMPORTANT]
> Always run schema migrations (`alembic upgrade head`) BEFORE running any seed script. `seed_staging.py` validates that tables already exist and will deliberately abort if the schema is uninitialized.

```bash
cd backend

# Step 1: Execute all Alembic migrations to build canonical PostGIS schema
alembic upgrade head

# Step 2: Verify current migration state
alembic current

# Step 3: Seed staging baseline data with strong password enforcement
STAGING_SEED_PASSWORD="<STRONG_PILOT_PASSWORD_MIN_14_CHARS_!>" python scripts/seed_staging.py
```

`seed_staging.py` enforces:
- Password validation: min 14 chars, rejects default phrases (`password`, `stagingpass`, `admin123`, `changeme`, etc.).
- Environment guard: Aborts immediately if `ENVIRONMENT=production`.
- Pre-existing schema check: Enforces that tables exist before inserting records.
- Timezone-aware UTC timestamps for all created records.

---

## 4. Deployment Manifests & Platforms

PawReach provides ready-to-deploy manifests for standard cloud platforms:

### Option A: Render.com Blueprint (`render.yaml`)
Deploys web service, worker, beat, managed PostgreSQL with PostGIS, and managed Redis:
```bash
# In Render Dashboard:
# 1. New -> Blueprint -> Connect PawReach repository
# 2. Render reads render.yaml and provisions all 5 services automatically.
# 3. Supply secret files and environment variables.
```

### Option B: Docker Compose Staging (`docker-compose.staging.yml`)
For self-hosted virtual machines (AWS EC2, DigitalOcean, GCP Compute Engine):
```bash
# Build and launch all 6 staging containers
docker compose -f docker-compose.staging.yml up -d --build

# Inspect running services
docker compose -f docker-compose.staging.yml ps

# Check Celery worker and beat logs
docker compose -f docker-compose.staging.yml logs -f worker beat
```

### Option C: Heroku / Railway / Fly.io (`Procfile`)
PawReach includes a root `Procfile` declaring process entrypoints:
```text
web: cd backend && gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT
worker: cd backend && celery -A app.tasks.celery_app worker -l INFO -c 4 -Q dispatch,notifications,default
beat: cd backend && celery -A app.tasks.celery_app beat -l INFO --pidfile=/tmp/celerybeat.pid
```

---

## 5. Frontend Production Build & Bundle Optimization

In Phase 2.9, route-level code splitting was introduced via `React.lazy` and dynamic imports for heavy components (Leaflet, Recharts, Command Center, Analytics, Vet Dashboard).

```bash
cd frontend
npm ci
npm run build
```

### Bundle Size Benchmark
| Bundle Metric | Phase 2.8 Baseline | Phase 2.9 Optimized | Improvement |
| :--- | :--- | :--- | :--- |
| **Initial JS Entry Chunk** | `1,083.20 kB` (monolithic) | **`317.75 kB`** | **-70.6% reduction** |
| **Chunks > 500 kB Warning** | 1 chunk (>1 MB warning) | **0 chunks > 500 kB** | **Zero Rollup warnings** |
| **Route Chunks** | None (bundled into index) | Clean split: Leaflet (148 kB), Recharts (332 kB), Pages (30-42 kB) | On-demand route loading |

The generated `frontend/dist` directory is served via the production Nginx container (`frontend/Dockerfile`, `frontend/nginx.conf`) with gzip compression, security headers (`X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`), and SPA fallback routing (`try_files $uri $uri/ /index.html`).

---

## 6. Health & Readiness Telemetry (6 Subsystems)

PawReach exposes deep health diagnostics to monitor staging infrastructure before routing pilot traffic.

### Liveness Check
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

### Deep Readiness Probe
```http
GET /api/v1/health/readiness
```
Alias: `GET /api/v1/health/ready`

Response when all systems operational:
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

If any service is degraded (e.g., Celery worker offline or S3 unreachable), the endpoint returns HTTP 503 with service-specific diagnostic status without leaking sensitive credentials.

---

## 7. Staging Smoke Test Verification

Execute the end-to-end staging smoke test script against deployed endpoints:

```bash
python scripts/staging_smoke_test.py \
  --api https://api.staging.pawreach.org \
  --frontend https://staging.pawreach.org
```

This automated script verifies:
1. **API Liveness**: `GET /api/v1/health` returns HTTP 200 and healthy status.
2. **Subsystem Readiness**: `GET /api/v1/health/readiness` checks all 6 subsystems.
3. **CORS Headers**: Confirms preflight and allowed origins match staging frontend.
4. **Frontend SPA Root**: Confirms HTML payload and script tags load.
5. **Frontend Deep Routing**: Confirms `/report`, `/ngo/overview`, `/vet` route correctly without 404s.

---

## 8. Rollback & Emergency Procedures

1. **Database Migration Rollback**:
   ```bash
   cd backend
   alembic downgrade -1
   ```
2. **Session Revocation (Suspected Token Leak)**:
   ```bash
   POST /api/v1/auth/logout-all
   Authorization: Bearer <ADMIN_OR_USER_TOKEN>
   ```
   Immediately blacklists refresh tokens and invalidates active sessions.
3. **Object Storage Fallback**:
   If S3 is temporarily degraded, switch `STORAGE_PROVIDER=local` in `.env` and restart the backend.
