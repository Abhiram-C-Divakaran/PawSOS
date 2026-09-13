# PawReach Operations & Incident Response Runbook
**Phase 2.9 — Staging & Pilot Incident Operations**

This runbook guides on-call engineers, sysadmins, and technical operators during incidents, degradations, and operational maintenance in the PawReach staging environment.

---

## 1. Quick Incident Severity Matrix

| Severity | Definition | Target Resolution | Escalation Contact |
| :--- | :--- | :--- | :--- |
| **SEV-1 (Critical)** | API down, database unreachable, or dispatch completely stalled | < 30 minutes | Lead Backend / DevOps |
| **SEV-2 (Major)** | Celery worker degraded, push notifications failing, image uploads failing | < 2 hours | Backend Engineer |
| **SEV-3 (Minor)** | Individual responder device issue, non-critical telemetry alert | Next business day | Operations Support |

---

## 2. API Service Unresponsive or Failing (HTTP 502 / 503 / 504)

### Symptoms
- Frontend displays network error / offline banner.
- `/api/v1/health` or `/api/v1/health/readiness` fails or times out.
- Reverse proxy (Nginx or Cloudflare) returns HTTP 502 Bad Gateway.

### Diagnostic Steps
1. Check running status of backend container or service:
   ```bash
   # Docker Compose
   docker compose -f docker-compose.staging.yml ps backend
   docker compose -f docker-compose.staging.yml logs backend --tail 100

   # Systemd / Render
   # Inspect service metrics and deployment logs in cloud dashboard
   ```
2. Verify system resources (CPU, Memory, Disk space):
   ```bash
   docker stats --no-stream
   df -h
   ```
3. Test direct internal API port:
   ```bash
   curl -I http://127.0.0.1:8000/api/v1/health
   ```

### Remediation
1. If Gunicorn workers hung or died due to OOM:
   ```bash
   docker compose -f docker-compose.staging.yml restart backend
   ```
2. Check database connectivity:
   ```bash
   docker exec -it pawreach_staging_db pg_isready -U pawreach_user -d pawreach_staging
   ```

---

## 3. Background Worker or Dispatch Engine Stalled

### Symptoms
- `/api/v1/health/readiness` reports `"celery": "degraded"` or `"celery": "no_heartbeat"`.
- Dispatch offers do not expire past their deadline (20s staging / 90s prod).
- Progressive radius does not expand automatically.

### Root Cause Analysis
PawReach separates asynchronous processing into:
- **`worker`**: Consumes from `dispatch`, `notifications`, `default` queues.
- **`beat`**: Singleton scheduler that enqueues periodic tasks (heartbeats every 10s, offer expiration every 20s).

### Diagnostic Steps
1. Check Celery worker and beat logs:
   ```bash
   docker compose -f docker-compose.staging.yml logs worker --tail 100
   docker compose -f docker-compose.staging.yml logs beat --tail 100
   ```
2. Verify Redis broker accessibility:
   ```bash
   docker exec -it pawreach_staging_redis redis-cli ping
   # Expected output: PONG
   ```
3. Check worker heartbeat key in Redis:
   ```bash
   docker exec -it pawreach_staging_redis redis-cli get celery_worker_heartbeat
   # Should return a recent ISO timestamp (within last 30 seconds)
   ```

### Remediation
1. If Celery Beat stopped scheduling:
   ```bash
   # Remove stale pidfile and restart beat
   docker compose -f docker-compose.staging.yml restart beat
   ```
2. If Worker process crashed:
   ```bash
   docker compose -f docker-compose.staging.yml restart worker
   ```
3. **Emergency Manual Dispatch Sweep**:
   If background workers cannot be restored immediately during an active pilot, run the dispatch lifecycle synchronously via CLI:
   ```bash
   docker exec -it pawreach_staging_backend python -c "
   from app.database import SessionLocal
   from app.services.dispatch_service import DispatchService
   db = SessionLocal()
   results = DispatchService.process_dispatch_lifecycle(db)
   print('Emergency dispatch cycle completed:', results)
   "
   ```

---

## 4. Redis Connection Unavailable

### Symptoms
- `/api/v1/health/readiness` reports `"redis": "disconnected"`.
- Token blacklisting and rate limiting fall back to local or fail.
- Background tasks queue up or fail immediately.

### Diagnostic Steps
1. Inspect Redis logs:
   ```bash
   docker compose -f docker-compose.staging.yml logs redis --tail 50
   ```
2. Check Redis memory usage:
   ```bash
   docker exec -it pawreach_staging_redis redis-cli info memory
   ```

### Remediation
1. Restart Redis:
   ```bash
   docker compose -f docker-compose.staging.yml restart redis
   docker compose -f docker-compose.staging.yml restart worker beat
   ```

---

## 5. Object Storage (S3) Degradation & Emergency Fallback

### Symptoms
- Evidence photo uploads return HTTP 500 or `Cloud storage upload failed`.
- Readiness probe reports `"storage": "degraded"`.

### Diagnostic Steps
1. Check AWS credentials in `.env`:
   - Verify `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET_NAME`.
2. Run standalone upload verification:
   ```bash
   python scripts/verify_staging_upload.py
   ```

### Emergency Local Fallback Procedure
If AWS S3 is down during an active field pilot:
1. In `backend/.env`, temporarily update:
   ```bash
   STORAGE_PROVIDER=local
   UPLOAD_DIR=/app/uploads
   ```
2. Restart backend:
   ```bash
   docker compose -f docker-compose.staging.yml restart backend
   ```
3. The application will store images locally and serve them via `/uploads/` until cloud storage is restored.

---

## 6. Firebase Web Push Delivery Failures

### Symptoms
- Responders report not receiving browser push notifications.
- Backend logs show `FCM delivery error` or `SenderIdMismatch`.

### Diagnostic Steps
1. Check service account file existence and validity:
   ```bash
   ls -la /etc/secrets/firebase-admin.json
   ```
2. Confirm `FIREBASE_PROJECT_ID` matches the credential JSON project ID.
3. Check token deactivation logs:
   - Stale/unregistered tokens are marked `is_active=False` automatically when Firebase returns `UnregisteredError`.
4. Browser Service Worker verification:
   - In browser developer tools, check **Application** -> **Service Workers**.
   - Verify `/firebase-messaging-sw.js` is registered and active at root scope.

---

## 7. Security Breach, Credential Compromise & Session Revocation

### Immediate Token Revocation
If an admin, dispatcher, or responder credential is suspected to be leaked:
1. Execute global logout for the affected user:
   ```bash
   curl -X POST \
     -H "Authorization: Bearer <USER_OR_ADMIN_TOKEN>" \
     https://api.staging.pawreach.org/api/v1/auth/logout-all
   ```
   This immediately revokes all refresh tokens for that user account across all devices.
2. If secret keys (JWT key or Database password) were compromised:
   - Generate new `JWT_SECRET_KEY` using `openssl rand -hex 32`.
   - Update `backend/.env`.
   - Restart all backend containers immediately (`docker compose -f docker-compose.staging.yml restart backend`).
   - This invalidates all existing JWT tokens globally.

---

## 8. Database Reset & Seeding Recovery

If the staging database needs to be cleanly reset and re-seeded:
```bash
cd backend

# Roll back all migrations to base (DESTRUCTIVE - Staging only!)
alembic downgrade base

# Reapply all migrations up to head
alembic upgrade head

# Re-seed with strong staging password
STAGING_SEED_PASSWORD="<YourSecureStagingPassword14+!>" python scripts/seed_staging.py
```
