# PawReach Staging & Pilot Rollback Plan
**Phase 2.9E — Operational Resilience & Rollback Protocols**

This document establishes the official rollback, fail-safe, and abort procedures for the PawReach staging environment and controlled pilot trials.

---

## 1. Rollback Philosophy & Core Rules

1. **Prefer Application Rollback Over Destructive Schema Rollback**:
   Database schemas in PawReach are strictly migration-driven via Alembic. Because running `alembic downgrade` in a shared or pre-production environment carries risks of data loss, column dropping, or foreign-key constraint violations, migrations must be designed to be forward-compatible (expand before contract).
2. **Deterministic Version Pinning**:
   Every deployment in staging is tied to an authoritative Git commit SHA verified by the CI pipeline. Rollbacks are executed by deploying a known-good previous Git SHA.
3. **Atomic Process Isolation**:
   Because PawReach runs separate processes (`api`, `worker`, `beat`, and static `frontend`), rollbacks must ensure all dependent services are aligned on the target revision to prevent message deserialization errors between Celery and the API.
4. **Zero Secret Persistence**:
   Never store credentials or API keys in rollback scripts or revision control. Use environment variables and secrets managers.

---

## 2. Abort Criteria for Controlled Pilot Trials

An active controlled field pilot or staging validation run must be paused or aborted immediately upon detecting any of the following triggers:

| Severity | Abort Trigger Condition | Action Required |
|---|---|---|
| **CRITICAL** | Authorization bypass or cross-tenant data leakage detected | **Immediate Halt**: Revoke tokens, pause dispatcher, quarantine cases |
| **CRITICAL** | Data loss, unrecoverable database corruption, or migration desynchronization | **Immediate Halt**: Roll back application, restore database snapshot |
| **HIGH** | Asynchronous dispatch engine deadlocked or creating duplicate assignments | **Pause Pilot**: Scale worker/beat to 0, run manual sweep if needed |
| **HIGH** | Private media evidence publicly accessible or presigned URLs leaking in bulk | **Pause Pilot**: Restrict S3 bucket policy, invalidate active sessions |
| **MEDIUM** | Real-device push notifications failing at rate > 50% | **Investigate**: Switch responders to polling mode while diagnosing FCM |
| **MEDIUM** | High API latency (p95 > 2.5s) degrading field rescuer responsiveness | **Throttle**: Restrict active pilot cases, investigate slow queries |

---

## 3. Application Rollback Procedure (Step-by-Step)

### Step 1: Identify Known-Good Target Commit SHA
Identify the last verified green commit SHA from the GitHub Actions CI pipeline history:
```bash
# Example known-good baseline:
TARGET_SHA="291e2ca21e685b52eb94375ba69813e20e86c54b"
```

### Step 2: Render PaaS Rollback
If deployed on Render via the blueprint (`render.yaml`):

1. **Deploy Target SHA via Render API or Dashboard**:
   - In the Render Dashboard, navigate to the service group `pawreach-staging`.
   - Under **Deploys**, find the deployment corresponding to `$TARGET_SHA` and click **Rollback to this deploy**.
   - Alternatively, trigger a deployment of the target commit via the deploy hook:
     ```bash
     curl -X POST "$RENDER_DEPLOY_HOOK_URL?ref=$TARGET_SHA"
     ```
2. **Verify All Services Rolled Back**:
   - `pawreach-staging-api` (Web)
   - `pawreach-staging-worker` (Background Worker)
   - `pawreach-staging-beat` (Scheduler)
   - `pawreach-staging-frontend` (Static Site)

### Step 3: Docker Compose Staging Rollback
If running the staging environment via `docker-compose.staging.yml`:

```bash
# 1. Check out the known-good commit
git checkout $TARGET_SHA

# 2. Rebuild and restart services cleanly
docker compose -f docker-compose.staging.yml down
docker compose -f docker-compose.staging.yml build --no-cache
docker compose -f docker-compose.staging.yml up -d

# 3. Verify container health status
docker compose -f docker-compose.staging.yml ps
```

---

## 4. Database & Migration Compatibility

### Forward-Compatible Migration Strategy
PawReach migrations follow the expand-and-contract pattern:
* **Additions are backward-compatible**: Adding nullable columns, new tables, or new indexes never breaks the previous application revision.
* **Deprecations are staged across releases**: Never drop a column or rename a table in the same release where the application code stops reading it.

### Verifying Migration State During Rollback
```bash
cd backend

# 1. Inspect current migration revision against head
alembic current
alembic heads

# 2. If the previous application code is compatible with current schema (recommended):
# Do NOT downgrade schema. The older application code will simply ignore newer nullable columns.

# 3. If a downgrade is strictly required (NON-DESTRUCTIVE ONLY):
# Only perform if the migration script specifically supports non-destructive downgrade
alembic downgrade -1
```

> [!CAUTION]
> Never execute `alembic downgrade base` in an environment containing active pilot or staging test data. Downgrade to base drops all tables, schemas, and spatial extension tables.

---

## 5. Celery Worker & Beat Rollback

When rolling back background queue processing:

1. **Stop Celery Beat First**:
   Always terminate the Beat scheduler before the workers to stop scheduling new recurring dispatch expiration and heartbeat checks:
   ```bash
   # Render: Suspend pawreach-staging-beat service
   # Docker Compose:
   docker compose -f docker-compose.staging.yml stop beat
   ```
2. **Drain or Purge Poison Messages**:
   If an unhandled exception in a newly introduced task broke the queue, inspect the dead-letter or error logs in Redis before resuming:
   ```bash
   # Inspect queue lengths in Redis
   redis-cli -u "$REDIS_URL" LLEN dispatch
   redis-cli -u "$REDIS_URL" LLEN notifications
   ```
3. **Restart Workers with Target Code**:
   ```bash
   # Docker Compose:
   docker compose -f docker-compose.staging.yml restart worker
   # Restart Beat once worker is confirmed healthy
   docker compose -f docker-compose.staging.yml start beat
   ```
4. **Verify Worker Heartbeat**:
   Confirm worker heartbeat is renewed in Redis within 30 seconds:
   ```bash
   redis-cli -u "$REDIS_URL" GET celery_worker_heartbeat
   ```

---

## 6. Frontend Rollback & Client Cache Invalidation

1. **Static Asset Invalidation**:
   The Vite production build generates unique content-hashed filenames for all JS/CSS chunks (e.g., `index-UBnxaQo_.css`, `index-DA8PWjRF.js`). Rolling back the frontend automatically points `index.html` to the previous content hashes.
2. **PWA Service Worker Invalidation**:
   If a broken service worker was deployed (`firebase-messaging-sw.js`):
   - The browser will detect changes to the service worker script on the next page load.
   - For emergency client-side cache clearing, users can perform a hard refresh (`Ctrl + F5` or `Cmd + Shift + R`), which updates the service worker registration.
3. **SPA Deep Route Fallback**:
   Verify that after rollback, direct URL navigation to `/cases/:id` and `/ngo/cases/:id` continues to serve `index.html` without HTTP 404 errors.

---

## 7. Cloud Storage (S3) Considerations

When rolling back code that touches object storage:

1. **Canonical Object Key Stability**:
   PawReach stores image keys in the database as `rescues/<uuid>.jpg`. This format is immutable and independent of code releases.
2. **Presigned URL Expiry**:
   Presigned URLs expire automatically after `S3_PRESIGNED_URL_EXPIRE_SECONDS` (default 900 seconds / 15 minutes). No manual URL invalidation is needed.
3. **S3 Bucket Policy**:
   Ensure the S3 bucket remains private with Block All Public Access enabled regardless of code revision.
4. **Emergency Storage Fallback**:
   If S3 integration fails unexpectedly during a pilot:
   ```bash
   # Temporarily switch to local storage in environment
   STORAGE_PROVIDER=local
   UPLOAD_DIR=/app/uploads
   ```

---

## 8. Firebase & Push Notification Rollback

1. **Credential Configuration**:
   If a Firebase service account credential is suspected compromised or invalid:
   - Rotate the service account key in the Firebase Console.
   - Update `FIREBASE_CREDENTIALS_JSON` in the secrets manager or GitHub environment.
   - Redeploy or restart the API and Worker processes.
2. **Device Token Compatibility**:
   Device tokens registered in the `device_tokens` table remain valid across application code rollbacks as long as the Firebase Project ID is unchanged.
3. **Graceful Fallback Mode**:
   If Firebase push delivery fails, PawReach automatically logs a warning, handles the failure gracefully, and continues the rescue dispatch workflow without raising unhandled HTTP 500 errors. Responders can still discover and accept offers through the live dashboard.

---

## 9. Secret Rotation & Incident Post-Mortem

If a secret is leaked or suspected compromised:

1. **JWT Secret Key (`JWT_SECRET_KEY`)**:
   - Generate a new 64-character secret (`openssl rand -hex 32`).
   - Update the secret in the environment configuration.
   - Restart the API and Worker services.
   - **Effect**: All existing sessions and access tokens are immediately invalidated; users must re-authenticate.
2. **Database Credentials (`DATABASE_URL`)**:
   - Update database password on PostgreSQL.
   - Update `DATABASE_URL` in environment variables.
   - Restart all dependent services.
3. **Redis Credentials (`REDIS_URL`)**:
   - Update Redis password.
   - Update `REDIS_URL` in environment variables.
   - Restart API, Worker, and Beat services.

---

## 10. Post-Rollback Smoke Verification Protocol

After any rollback is executed, immediately run the automated smoke test against the live staging URLs:

```bash
python scripts/staging_smoke_test.py \
  --api-url "$STAGING_API_URL" \
  --frontend-url "$STAGING_FRONTEND_URL" \
  --expected-sha "$TARGET_SHA"
```

Verify all 5 test stages pass:
1. **Liveness & Git SHA Match**: `/api/v1/health` confirms `git_sha == TARGET_SHA` and `status == ok`.
2. **Deep Readiness**: `/api/v1/health/ready` confirms all subsystems `healthy` (`database`, `postgis`, `redis`, `celery`, `storage`).
3. **CORS Validation**: Authorized origin receives CORS headers; unauthorized origin is denied.
4. **Security Headers**: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, HSTS present.
5. **Frontend SPA Routes**: Root `/` and deep route `/login` return HTTP 200.
