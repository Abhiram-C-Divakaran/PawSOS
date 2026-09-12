# PawReach Operations Incident Runbook

This runbook guides on-call operators and system administrators during incident response.

---

## 1. API Service Unresponsive (HTTP 502 / 503 / 504)
### Symptoms
- Frontend displays network error banner.
- `/health` or `/health/ready` fails or times out.

### Diagnosis & Remediation
1. Check container/process status:
   ```bash
   docker ps | grep pawsos
   docker logs pawsos_backend --tail 100
   ```
2. Verify system resources (CPU, Memory, Disk space):
   ```bash
   docker stats --no-stream
   df -h
   ```
3. Check PostgreSQL database connectivity:
   ```bash
   docker exec -it pawsos_db pg_isready -U postgres
   ```
4. Restart backend service if deadlocked:
   ```bash
   docker restart pawsos_backend
   ```

---

## 2. Background Worker or Dispatch Stuck
### Symptoms
- `/health/ready` reports `"worker": "no_heartbeat"` or `"worker": "degraded"`.
- Dispatch offers do not expire past their 90-second deadline.
- Radii do not expand automatically.

### Diagnosis & Remediation
1. Check Celery worker process and logs:
   ```bash
   docker logs pawsos_worker --tail 100
   ```
2. Check Redis connection:
   ```bash
   docker exec -it pawsos_redis redis-cli ping
   # Check worker heartbeat key
   docker exec -it pawsos_redis redis-cli get celery_worker_heartbeat
   ```
3. If worker process crashed or hung on task execution:
   ```bash
   docker restart pawsos_worker
   ```
4. Manually trigger expiration batch in emergency via python shell:
   ```bash
   docker exec -it pawsos_backend python -c "from app.database import SessionLocal; from app.services.dispatch_service import DispatchService; db = SessionLocal(); print(DispatchService.process_dispatch_lifecycle(db))"
   ```

---

## 3. Redis Connection Unavailable
### Symptoms
- `/health/ready` reports `"redis": "disconnected"`.
- Rate limiting falls back or fails; background tasks queue up in memory or fail.

### Diagnosis & Remediation
1. Inspect Redis container logs:
   ```bash
   docker logs pawsos_redis --tail 50
   ```
2. Check Redis memory usage:
   ```bash
   docker exec -it pawsos_redis redis-cli info memory
   ```
3. Restart Redis:
   ```bash
   docker restart pawsos_redis
   docker restart pawsos_worker
   ```

---

## 4. Firebase Web Push Delivery Failures
### Symptoms
- Responders report not receiving push notifications when browser tab is inactive.
- Backend logs show `FCM delivery error` or `SenderIdMismatch`.

### Diagnosis & Remediation
1. Verify Firebase credentials path and project ID in `.env`:
   ```text
   FIREBASE_CREDENTIALS_PATH=/path/to/firebase-adminsdk.json
   FIREBASE_PROJECT_ID=pawsos-staging
   ```
2. Check if device tokens have expired:
   - Tokens marked `is_active=False` automatically when Firebase returns `UnregisteredError`.
3. Check browser client console for service worker registration errors:
   - Ensure `/firebase-messaging-sw.js` is accessible at root URL without CORS blocks.

---

## 5. Cloud Storage / S3 Unavailable
### Symptoms
- Rescue image upload returns `500` or `400 Cloud storage upload failed`.

### Diagnosis & Remediation
1. Check AWS credentials and bucket configuration:
   ```text
   AWS_ACCESS_KEY_ID
   AWS_SECRET_ACCESS_KEY
   AWS_REGION
   S3_BUCKET_NAME
   ```
2. For emergency operations, temporarily set `STORAGE_PROVIDER=local` in `.env` and restart backend. Images will be served from `/uploads`.
