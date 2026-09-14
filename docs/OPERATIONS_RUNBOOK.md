# PawReach Operations & Incident Response Runbook
**Phase 2.9E — Staging & Pilot Incident Operations**

This runbook guides on-call engineers, site reliability operators, and technical leads during staging maintenance, controlled field pilots, and live incidents in PawReach.

---

## 1. Incident Severity Matrix & Response Expectations

| Severity | Definition | Target Resolution | Escalation Path |
|---|---|---|---|
| **SEV-1 (Critical)** | Core API down, database unreachable, spatial query failure, or dispatch pipeline completely halted | < 30 minutes | Lead Backend / DevOps / Infrastructure Owner |
| **SEV-2 (Major)** | Celery worker degraded, Beat scheduler stopped, push notifications failing, or image storage degraded | < 2 hours | Backend Engineer / Cloud Operator |
| **SEV-3 (Minor)** | Individual responder device issue, non-blocking telemetry alert, single client token refresh failure | Next business day | Operations Support |

---

## 2. General Operational Commands

### 2.1 Log Inspection
```bash
# Docker Compose Staging
docker compose -f docker-compose.staging.yml logs -f --tail=100 backend
docker compose -f docker-compose.staging.yml logs -f --tail=100 worker
docker compose -f docker-compose.staging.yml logs -f --tail=100 beat
docker compose -f docker-compose.staging.yml logs -f --tail=50 db
docker compose -f docker-compose.staging.yml logs -f --tail=50 redis

# Render Cloud PaaS (via Render Dashboard or CLI)
# Inspect logs tab under services:
# - pawreach-staging-api
# - pawreach-staging-worker
# - pawreach-staging-beat
# - pawreach-staging-frontend
```

### 2.2 Process Restart (Individual Services)
```bash
# Docker Compose:
docker compose -f docker-compose.staging.yml restart backend
docker compose -f docker-compose.staging.yml restart worker
docker compose -f docker-compose.staging.yml restart beat
docker compose -f docker-compose.staging.yml restart redis

# Render Cloud:
# In Render Dashboard -> Service -> 'Manual Deploy' -> 'Trigger Deploy' or 'Restart Service'
```

### 2.3 Migration Verification
```bash
cd backend
# Check current database revision and compare with migration heads
alembic current
alembic heads

# Apply missing migrations if out of sync
alembic upgrade head
```

### 2.4 Worker Heartbeat Verification
```bash
# Direct Redis inspection
redis-cli -u "$REDIS_URL" GET celery_worker_heartbeat
# Should return an ISO timestamp updated within the last 30 seconds (e.g., 2026-09-14T13:40:00.000000)

# Via Deep Readiness API
curl -s https://<STAGING_API_URL>/api/v1/health/ready | python -m json.tool
# Look for: "services": { "celery": "healthy" }
```

### 2.5 Pausing Controlled Pilot Testing
If an operational defect requires pausing field testing immediately:
1. **Disable Celery Beat**: Stops automated offer creation and expirations:
   ```bash
   docker compose -f docker-compose.staging.yml stop beat
   ```
2. **Set NGO Responders to Inactive**: Update responder profile availability:
   ```bash
   # Emergency script or database update via authorized Admin endpoint
   # PATCH /api/v1/ngo/responders/{id}/status -> { "is_active": false }
   ```
3. **Notify Active Responders**: Use dashboard broadcast banner.

---

## 3. Specific Failure Modes & Remediation Procedures

### 3.1 API Down (HTTP 502 / 503 / 504)
* **Symptoms**:
  - Web client displays offline banner or API connection error.
  - Health checks `/api/v1/health` fail with connection timeout or 502 Bad Gateway.
* **Diagnosis**:
  1. Inspect container/process status:
     ```bash
     docker compose -f docker-compose.staging.yml ps backend
     ```
  2. Check memory/CPU exhaustion:
     ```bash
     docker stats --no-stream
     ```
  3. Check backend error logs for fatal startup errors or unhandled exceptions:
     ```bash
     docker compose -f docker-compose.staging.yml logs backend --tail 100
     ```
* **Remediation**:
  1. If Gunicorn/Uvicorn workers hung or crashed:
     ```bash
     docker compose -f docker-compose.staging.yml restart backend
     ```
  2. Verify database connection string and network connectivity.

---

### 3.2 Database Unreachable
* **Symptoms**:
  - API returns HTTP 500 on all read/write endpoints.
  - `/api/v1/health/ready` reports `"database": "unhealthy"` or `"disconnected"`.
* **Diagnosis**:
  1. Ping the PostgreSQL database container/host:
     ```bash
     pg_isready -h <DB_HOST> -p 5432 -U <DB_USER>
     ```
  2. Check PostgreSQL service logs:
     ```bash
     docker compose -f docker-compose.staging.yml logs db --tail 50
     ```
* **Remediation**:
  1. If PostgreSQL container stopped:
     ```bash
     docker compose -f docker-compose.staging.yml start db
     ```
  2. Check connection limits (pool exhaustion): Verify `pool_size` and `max_overflow` in `app/database.py`.

---

### 3.3 PostGIS Spatial Engine Unavailable
* **Symptoms**:
  - Nearby rescue discovery (`/api/v1/rescues/nearby`) fails with `function st_dwithin does not exist`.
  - `/api/v1/health/ready` reports `"postgis": "unhealthy"`.
* **Diagnosis**:
  1. Connect to the database and query the extension:
     ```sql
     SELECT PostGIS_Version();
     ```
* **Remediation**:
  1. If the extension was not initialized in the database:
     ```sql
     CREATE EXTENSION IF NOT EXISTS postgis;
     ```
  2. Confirm spatial columns are using `geography(Point, 4326)`.

---

### 3.4 Redis Connection Unavailable
* **Symptoms**:
  - Background task enqueueing hangs or fails.
  - `/api/v1/health/ready` reports `"redis": "unhealthy"`.
  - Rate limiting logs fallback warnings.
* **Diagnosis**:
  1. Test Redis connectivity:
     ```bash
     redis-cli -u "$REDIS_URL" ping
     # Expected: PONG
     ```
  2. Inspect Redis memory:
     ```bash
     redis-cli -u "$REDIS_URL" info memory
     ```
* **Remediation**:
  1. Restart Redis container:
     ```bash
     docker compose -f docker-compose.staging.yml restart redis
     ```
  2. Restart Worker and Beat to re-establish broken connection pools:
     ```bash
     docker compose -f docker-compose.staging.yml restart worker beat
     ```

---

### 3.5 Celery Worker Missing / Degraded
* **Symptoms**:
  - `/api/v1/health/ready` reports `"celery": "unhealthy"` (heartbeat stale > 60s).
  - Background tasks (dispatch wave matching, notifications) do not execute.
* **Diagnosis**:
  1. Check worker logs:
     ```bash
     docker compose -f docker-compose.staging.yml logs worker --tail 100
     ```
  2. Check worker process status:
     ```bash
     docker compose -f docker-compose.staging.yml ps worker
     ```
* **Remediation**:
  1. Restart Celery worker:
     ```bash
     docker compose -f docker-compose.staging.yml restart worker
     ```
  2. If worker crashes on task deserialization, verify that the worker and API are running the same Git commit SHA.

---

### 3.6 Celery Beat Scheduler Missing / Stopped
* **Symptoms**:
  - Dispatch offers do not expire past their deadline (20 seconds in staging).
  - Case radius does not automatically expand (5km -> 10km -> 20km -> 40km).
  - Worker heartbeat is no longer refreshed.
* **Diagnosis**:
  1. Check beat logs:
     ```bash
     docker compose -f docker-compose.staging.yml logs beat --tail 100
     ```
  2. Check if a stale pidfile exists (`/tmp/celerybeat.pid`).
* **Remediation**:
  1. Clear stale pidfile and restart Beat:
     ```bash
     docker compose -f docker-compose.staging.yml restart beat
     ```
  2. Ensure only **one single instance** of Celery Beat is running across the staging cluster.

---

### 3.7 Queue Backlog & Task Starvation
* **Symptoms**:
  - High dispatch latency; offers take minutes to reach responders.
  - Redis memory growing continuously.
* **Diagnosis**:
  1. Check length of Celery task queues in Redis:
     ```bash
     redis-cli -u "$REDIS_URL" LLEN dispatch
     redis-cli -u "$REDIS_URL" LLEN notifications
     redis-cli -u "$REDIS_URL" LLEN default
     ```
* **Remediation**:
  1. Scale worker concurrency:
     ```bash
     # Temporarily increase worker processes
     celery -A app.tasks.celery_app.celery_app worker -c 8 -Q dispatch,notifications,default
     ```
  2. Identify slow or blocking tasks in worker logs.

---

### 3.8 Firebase Push Notification Failures
* **Symptoms**:
  - Responders report no mobile or desktop push notifications.
  - Backend logs show `FirebaseMessagingError`, `SenderIdMismatch`, or `UnregisteredError`.
* **Diagnosis**:
  1. Verify credentials configured:
     - Check `FIREBASE_CREDENTIALS_JSON` or `FIREBASE_CREDENTIALS_PATH`.
  2. Test health probe:
     - Check `/api/v1/health/ready` for `"firebase": "healthy"`.
  3. Verify client service worker registration in browser:
     - Inspect `navigator.serviceWorker.getRegistrations()`.
* **Remediation**:
  1. If credentials expired, rotate service account key in Firebase Console and update `FIREBASE_CREDENTIALS_JSON`.
  2. The application handles `UnregisteredError` by automatically marking stale device tokens `is_active = False`. Responders will receive new tokens upon next login.

---

### 3.9 Cloud Object Storage (S3) Degradation
* **Symptoms**:
  - Citizen image upload fails with HTTP 500.
  - Image access route `/rescues/{id}/images/{img_id}/access` fails to generate presigned URLs.
  - `/api/v1/health/ready` reports `"storage": "unhealthy"`.
* **Diagnosis**:
  1. Check AWS credentials:
     - Verify `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, and `S3_BUCKET_NAME`.
  2. Run standalone upload verification:
     ```bash
     python scripts/verify_staging_upload.py
     ```
* **Remediation**:
  1. Check AWS S3 service status and bucket permissions (Block All Public Access must be ON, IAM policy must allow `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject`).
  2. **Emergency Fallback**: Set `STORAGE_PROVIDER=local` in backend environment and restart API to route uploads to local disk.

---

### 3.10 Subsystem Readiness Degraded
* **Symptoms**:
  - `/api/v1/health/ready` returns HTTP 200 with `"status": "degraded"` or `"unhealthy"`.
* **Diagnosis**:
  1. Inspect the `services` object in `/api/v1/health/ready`:
     ```bash
     curl -s https://<STAGING_API_URL>/api/v1/health/ready | python -m json.tool
     ```
  2. Identify which specific key is not `"healthy"`.
* **Remediation**:
  - Follow the specific remediation section above corresponding to the degraded subsystem.

---

### 3.11 Deployed Git SHA Mismatch
* **Symptoms**:
  - Post-deploy smoke test fails with `Deployed git_sha does NOT match expected`.
  - API reports an older Git commit SHA on `/api/v1/health`.
* **Diagnosis**:
  1. Check `git_sha` reported by API:
     ```bash
     curl -s https://<STAGING_API_URL>/api/v1/health | grep git_sha
     ```
  2. Check Render build/deployment logs: verify whether the latest commit was pulled and built.
* **Remediation**:
  1. Trigger manual redeploy pointing to the exact target SHA:
     ```bash
     curl -X POST "$RENDER_DEPLOY_HOOK_URL"
     ```
  2. Confirm `GIT_SHA` or `RENDER_GIT_COMMIT` environment variable is captured at build time.

---

### 3.12 High Application Error Rate (5xx Surge)
* **Symptoms**:
  - Sentry reports error spike or reverse proxy logs show high HTTP 500 volume.
* **Diagnosis**:
  1. Query Sentry dashboard for top exceptions.
  2. Inspect backend logs for stack traces:
     ```bash
     docker compose -f docker-compose.staging.yml logs backend --tail 200 | grep -C 5 "ERROR"
     ```
* **Remediation**:
  1. If caused by bad deployment: Execute application rollback to previous known-good commit (see [`STAGING_ROLLBACK.md`](./STAGING_ROLLBACK.md)).
  2. If caused by database lock contention: Check active PostgreSQL queries:
     ```sql
     SELECT pid, query, state, age(clock_timestamp(), query_start) 
     FROM pg_stat_activity 
     WHERE state != 'idle' AND query NOT ILIKE '%pg_stat_activity%';
     ```
