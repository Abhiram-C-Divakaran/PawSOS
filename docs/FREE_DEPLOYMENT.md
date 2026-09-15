# PawReach — Zero-Cost Free Live Deployment Guide

This guide describes how to deploy **PawReach** as a free public portfolio / college demonstration project using 100% free-tier cloud services:

* **Frontend**: Render Static Site (Free)
* **Backend**: Render Web Service (Free — combined FastAPI, lightweight Celery worker, and Celery Beat scheduler)
* **Database**: Supabase Free Tier (PostgreSQL with PostGIS via Session Pooler)
* **Image Storage**: Supabase Storage via S3-compatible API (Private bucket)
* **Task Broker (Redis)**: Upstash Redis (Free tier via TCP/TLS `rediss://`)
* **Push Notifications**: Firebase Cloud Messaging (Spark free plan — optional)

---

## Important Free-Tier Characteristics & Limitations

> [!WARNING]
> **Render Free Container Sleep Behavior & Dispatch Notice**:
> - **Container Inactivity Sleep**: The free Render backend spins down after 15 minutes of inactivity.
> - **Cold Starts**: The first request after a sleep period may experience a 30–50 second cold-start delay while the container starts.
> - **Worker & Beat Suspension**: Because the Celery worker and Beat scheduler run inside the same free web container, both processes pause while the container sleeps.
> - **Best-Effort Dispatch**: Background rescue dispatch and periodic sweeps are therefore best-effort in this public demo deployment.
> - **Not Production 24/7 Infrastructure**: This deployment is suitable for a student portfolio / college project demo. It is **NOT** 24/7 emergency rescue infrastructure. If PawReach is ever transitioned into an operational service, the backend can immediately be restored to dedicated, always-on API, Celery worker, and Celery Beat services.

---

## Step-by-Step Operator Setup Sequence

Follow these 20 steps in order:

### 1. Create Supabase Free Project
1. Go to [Supabase](https://supabase.com) and create a free account.
2. Click **New Project**, choose a project name (e.g., `pawreach-demo`), set a strong database password, and select your preferred region.

### 2. Enable PostGIS
1. In the Supabase Dashboard, open the **SQL Editor** from the left sidebar.
2. Run the following command to enable geospatial extensions:
   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   ```

### 3. Copy Session Pooler Connection String on Port 5432
1. In the Supabase Dashboard, click **Connect** (or go to **Project Settings** → **Database**).
2. Select **Session pooler** mode on **Port 5432**.
   > [!IMPORTANT]
   > **Session vs Transaction Pooler**:
   > - **Port 5432 (Session mode)**: **Required** for PawReach's FastAPI/SQLAlchemy/Alembic backend to handle session-level state, prepared statements, and database migrations properly.
   > - **Port 6543 (Transaction mode)**: Do **NOT** use port 6543 as transaction mode has session-level prepared statement limitations incompatible with our migration and ORM workflows.
3. Copy the exact dashboard-generated connection string (do NOT manufacture hostnames manually):
   ```text
   postgresql://postgres.<project-ref>:<db-password>@<pooler-host>.pooler.supabase.com:5432/postgres?sslmode=require
   ```
   *(Direct PostgreSQL connection on port 5432 is also an acceptable alternative where network environment permits).*

### 4. Create Private Storage Bucket
1. In Supabase, open **Storage**.
2. Click **New bucket**, name it `evidence` (or your choice).
3. Ensure the **Public bucket** toggle remains **OFF**. The bucket **must remain private** to protect animal and reporter location privacy.

### 5. Enable S3 Protocol & Create S3 Credentials
1. Navigate to **Project Settings** → **Storage**.
2. Locate the **S3 Connection** section and click **Generate new key**.

### 6. Record Exact S3 Endpoint and Region
Record the generated values:
- **S3 Endpoint URL**: `https://<project-ref>.supabase.co/storage/v1/s3`
- **Access Key ID**: `<access_key_id>`
- **Secret Access Key**: `<secret_access_key>`
- **S3 Region**: Record the exact region displayed for your project (e.g., `ap-south-1` or `us-east-1`).

### 7. Create Upstash Redis Free
1. Go to [Upstash](https://upstash.com) and create a free account.
2. Create a new Redis database (free tier).

### 8. Copy Redis TCP/TLS `rediss://` Connection (NOT REST URL)
> [!CAUTION]
> **Do NOT use the REST URL for Celery**:
> Upstash provides a REST API URL (`https://...`) and a Redis TCP/TLS URL (`rediss://...`). Celery requires the native Redis protocol over TLS.
1. In the Upstash database details, copy the **rediss://** connection URL.
2. Ensure the URL format is:
   ```text
   rediss://default:<password>@<host>:<port>?ssl_cert_reqs=required
   ```
   *(PawReach automatically normalizes `rediss://` to append `ssl_cert_reqs=required` if omitted, ensuring secure certificate verification).*

### 9. Create Firebase Project (Optional)
*For initial deployment, `REQUIRE_FIREBASE=false` is preconfigured.*
*If web push notifications are desired later, create a Firebase project, generate a service account private key JSON, and retain it for `FIREBASE_CREDENTIALS_JSON`.*

### 10. Deploy Render Blueprint
1. In [Render](https://render.com), click **New** → **Blueprint**.
2. Select your repository (`https://github.com/Abhiram-C-Divakaran/PawSOS`).
3. Render reads `render.yaml` and prepares two free resources:
   - `pawreach-api` (Free Python Web Service)
   - `pawreach-frontend` (Free Static Site)

### 11. Enter Required Secrets
In the Render dashboard under `pawreach-api` → **Environment**, supply:
- `DATABASE_URL`: Your Supabase Session pooler URI (from Step 3)
- `REDIS_URL`: Your Upstash `rediss://...` URI (from Step 8)
- `S3_ENDPOINT_URL`: Supabase S3 endpoint (from Step 6)
- `S3_BUCKET_NAME`: `evidence` (from Step 4)
- `AWS_ACCESS_KEY_ID`: Supabase S3 Access Key (from Step 6)
- `AWS_SECRET_ACCESS_KEY`: Supabase S3 Secret Key (from Step 6)
- `AWS_REGION`: Your Supabase project region (from Step 6)
- `JWT_SECRET_KEY`: (Auto-generated by Render Blueprint)

### 12. Obtain Real Backend & Frontend URLs
Render assigns public domains:
- Backend: `https://pawreach-api.onrender.com`
- Frontend: `https://pawreach-frontend.onrender.com`

### 13. Configure Exact `CORS_ORIGINS`
Under `pawreach-api` → **Environment**, set:
```text
CORS_ORIGINS=https://pawreach-frontend.onrender.com
```
*(No trailing slash; must match your deployed frontend origin exactly).*

### 14. Configure Exact `VITE_API_BASE_URL`
Under `pawreach-frontend` → **Environment**, set:
```text
VITE_API_BASE_URL=https://pawreach-api.onrender.com
```

### 15. Redeploy Services
Trigger a manual deployment of `pawreach-api` and `pawreach-frontend` so the newly configured environment variables and build steps take effect.

### 16. Verify `/api/v1/health`
Test the API liveness probe:
```bash
curl https://pawreach-api.onrender.com/api/v1/health
```
Expected response:
```json
{"status": "ok", "environment": "staging", "version": "2.0.0"}
```

### 17. Verify `/api/v1/health/ready`
Test downstream system connectivity:
```bash
curl https://pawreach-api.onrender.com/api/v1/health/ready
```
Expected response:
```json
{
  "status": "ready",
  "database": "connected",
  "postgis": "available",
  "redis": "connected",
  "storage": "connected"
}
```

### 18. Test Core User Flows
1. Register a Citizen account, report a test rescue with photo upload.
2. Verify image upload generates a canonical key in private S3 bucket and displays via temporary presigned GET URL.
3. Log in as an NGO Coordinator, inspect the triage dashboard.
4. Test foster home registration, offer acceptance, care logging, and adoption application submission.

### 19. Configure GitHub Staging Environment Secrets
In your GitHub repository under **Settings** → **Environments** → **staging**, configure:
- `RENDER_DEPLOY_HOOK_BACKEND`: Render deploy hook for `pawreach-api`
- `RENDER_DEPLOY_HOOK_FRONTEND`: Render deploy hook for `pawreach-frontend`
- `STAGING_API_URL`: `https://pawreach-api.onrender.com`
- `STAGING_FRONTEND_URL`: `https://pawreach-frontend.onrender.com`

### 20. Run Staging Workflow & Verify Real Smoke-Test Execution
Trigger the `staging-deploy.yml` workflow and verify that:
1. Cloud deployments trigger successfully.
2. The staging smoke test suite executes live against the deployed environment and passes.
