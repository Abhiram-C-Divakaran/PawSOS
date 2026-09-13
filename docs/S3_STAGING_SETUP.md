# AWS S3 Object Storage — Staging Setup & Security Guide
**PawReach MVP Phase 2.9 — Staging Configuration**

This document describes the configuration, IAM security policies, CORS rules, image transformation pipeline, and verification procedures for Amazon S3 (or S3-compatible MinIO) storage in the PawReach staging environment.

---

## 1. Storage Architecture Overview

PawReach stores rescue evidence photos, veterinary clinical documentation, and organization logos using an abstracted cloud storage service (`app/services/storage_service.py`).

In `staging` and `production` environments:
- `STORAGE_PROVIDER=s3` is enforced.
- The backend validates all required AWS credentials at startup; missing variables trigger an immediate fail-fast exit.
- All uploaded images pass through a strict security and optimization pipeline prior to S3 persistence.

```
Client (Browser / Mobile)
        |
        | multipart/form-data (Raw Image <= 10MB)
        v
Backend API (`POST /api/v1/uploads/image`)
        |
        +---> Decompression Bomb Check (< 25M pixels)
        +---> MIME Validation (image/jpeg, image/png, image/webp)
        +---> EXIF Orientation Auto-Transpose
        +---> Lanczos Downscale (max dimension <= 2048px)
        +---> WebP Format Conversion (85% quality)
        |
        v
AWS S3 Private Bucket (`s3://pawreach-staging-media/`)
        |
        +---> Pre-signed URLs or CDN endpoint returned to client
```

---

## 2. AWS S3 Bucket Setup

### Step 1: Create S3 Bucket
1. In the AWS Management Console, navigate to **Amazon S3**.
2. Click **Create bucket**.
3. Set **Bucket name**: `pawreach-staging-media` (must be globally unique).
4. Select **AWS Region**: e.g., `ap-south-1` (Mumbai) or your staging region.
5. **Object Ownership**: ACLs disabled (recommended).

### Step 2: Enforce Block Public Access
> [!IMPORTANT]
> Keep **Block all public access** checked (ON). All media files are private and accessed via signed URLs or application reverse proxies.

### Step 3: Configure CORS Rules
To allow browser uploads or direct asset retrieval from the staging frontend:
1. In the bucket, go to the **Permissions** tab.
2. Scroll to **Cross-origin resource sharing (CORS)** and click **Edit**.
3. Paste the following CORS configuration:
```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["GET", "PUT", "POST", "HEAD"],
    "AllowedOrigins": [
      "https://staging.pawreach.org",
      "https://admin.staging.pawreach.org",
      "http://localhost:5173",
      "http://localhost:3000"
    ],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3600
  }
]
```

---

## 3. IAM Security & Least-Privilege Policy

Create a dedicated IAM user (e.g., `pawreach-staging-s3-user`) with programmatic access and attach the following minimal policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PawReachS3BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::pawreach-staging-media"
    },
    {
      "Sid": "PawReachS3ObjectAccess",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::pawreach-staging-media/*"
    }
  ]
}
```

Generate an **Access Key ID** and **Secret Access Key** for this user.

---

## 4. Environment Variables Configuration

In `backend/.env`:
```bash
STORAGE_PROVIDER=s3
AWS_ACCESS_KEY_ID="AKIAIOSFODNN7EXAMPLE"
AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
AWS_REGION="ap-south-1"
S3_BUCKET_NAME="pawreach-staging-media"
```

---

## 5. Image Security & Processing Pipeline

The PawReach backend enforces strict guardrails against image-based vulnerabilities and resource exhaustion:

| Security Control | Implementation | Protection |
| :--- | :--- | :--- |
| **Max Payload Size** | 10 MB limit (`MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024`) | Prevents bandwidth and memory exhaustion |
| **Decompression Bomb Defense** | Pillow pixel ceiling (`Image.MAX_IMAGE_PIXELS = 25,000,000`) | Blocks gzip/zip bomb attacks |
| **MIME vs Format Check** | Pillow `image.format` vs Content-Type verification | Blocks spoofed extensions and polyglot files |
| **EXIF Orientation** | `ImageOps.exif_transpose` | Corrects orientation from mobile phone cameras |
| **Dimension Normalization** | Lanczos downscale to $\le 2048$px | Optimizes storage and mobile network bandwidth |
| **Canonical WebP Output** | Converts all JPEG/PNG uploads to WebP at 85% quality | Consistent, modern image compression |

---

## 6. Verification & Health Probes

### A. Subsystem Health Probe
```bash
curl -s http://localhost:8000/api/v1/health/readiness | jq .services.storage
# Expected output: "connected"
```
The health check executes a non-destructive `head_bucket` call via `boto3` without reading or writing data.

### B. Automated Standalone Verification Script
Run the verification script provided in the repository:
```bash
python scripts/verify_staging_upload.py
```
This script:
1. Generates a synthetic test image with EXIF orientation metadata.
2. Authenticates against the staging API.
3. Uploads the image via `POST /api/v1/uploads/image`.
4. Validates that the returned URL contains the S3 bucket path and `.webp` extension.
5. Verifies image headers and dimensions.

### C. Emergency Local Fallback Procedure
If AWS S3 becomes unreachable during a staging pilot session:
1. Edit `backend/.env`:
   ```bash
   STORAGE_PROVIDER=local
   UPLOAD_DIR=/app/uploads
   ```
2. Restart backend:
   ```bash
   docker restart pawsos_backend
   ```
3. Uploads will immediately be persisted locally to the filesystem and served via `/uploads/`.

---

## 7. Staging Readiness Status

| Requirement | Implementation | Status |
| :--- | :--- | :--- |
| Abstract storage interface | `app/services/storage_service.py` | Verified (Automated unit tests pass) |
| S3 client integration (`boto3`) | `S3StorageProvider` class | Verified (Mocked S3 tests pass) |
| Image transformation pipeline | WebP + Lanczos + EXIF transpose | Verified (Automated tests pass) |
| Decompression bomb protection | `MAX_IMAGE_PIXELS = 25M` | Verified (Automated tests pass) |
| Startup validation for staging | Fails fast if AWS keys missing in staging | Verified (Automated tests pass) |
| Staging S3 Bucket provisioned | Operator must provide AWS credentials | **Status: REQUIRES_EXTERNAL_CREDENTIALS** |
