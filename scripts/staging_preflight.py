#!/usr/bin/env python3
"""PawReach Staging Preflight Environment Validation Script.
Non-mutating diagnostic script to check environment configuration before staging deployment.
Validates environment variables, database scheme, Redis scheme, storage configuration,
Firebase settings, and process types without initiating external network mutations.
"""
import os
import sys
import json

def run_preflight_checks(proc_type: str | None = None) -> bool:
    print("==================================================")
    print("      PawReach Staging Preflight Diagnostics      ")
    print("==================================================")

    env_name = os.getenv("ENVIRONMENT", "development").lower()
    process_type = (proc_type or os.getenv("PROCESS_TYPE", "api")).lower()
    print(f"Target Environment: {env_name}")
    print(f"Target Process Type: {process_type}")
    print("--------------------------------------------------")

    passed = True

    # 1. Check PROCESS_TYPE
    valid_processes = ["api", "web", "worker", "beat", "all"]
    if process_type not in valid_processes:
        print(f"[FAIL] Invalid PROCESS_TYPE '{process_type}'. Expected one of: {valid_processes}")
        passed = False
    else:
        print(f"[PASS] Process type '{process_type}' is valid.")

    # 2. Check Database URL
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("[FAIL] DATABASE_URL is missing or empty.")
        passed = False
    else:
        if env_name in ["production", "staging"]:
            if "sqlite" in db_url.lower():
                print("[FAIL] SQLite is prohibited in staging/production. PostgreSQL+PostGIS required.")
                passed = False
            elif not (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
                print(f"[FAIL] Unexpected DATABASE_URL scheme: {db_url.split('://')[0] if '://' in db_url else 'none'}")
                passed = False
            else:
                print("[PASS] DATABASE_URL PostgreSQL/PostGIS scheme verified.")
        else:
            print(f"[PASS] DATABASE_URL set for {env_name}.")

    # 3. Check Redis URL
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        print("[FAIL] REDIS_URL is missing or empty.")
        passed = False
    elif not (redis_url.startswith("redis://") or redis_url.startswith("rediss://")):
        print(f"[FAIL] REDIS_URL scheme invalid: '{redis_url}'. Must start with redis:// or rediss://")
        passed = False
    else:
        print("[PASS] REDIS_URL scheme verified.")

    # 4. Check JWT Secret
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    if env_name in ["production", "staging"]:
        insecure_keys = ["secret", "dev_secret_key_change_in_production", "changeme", "default_jwt_secret_key_32chars!!"]
        if not jwt_secret or len(jwt_secret) < 32 or jwt_secret in insecure_keys or "dev_secret" in jwt_secret.lower():
            print("[FAIL] Insecure or short (<32 chars) JWT_SECRET_KEY in staging/production.")
            passed = False
        else:
            print("[PASS] JWT_SECRET_KEY length and strength validated.")
    else:
        print("[PASS] JWT_SECRET_KEY checked.")

    # 5. Process-specific checks
    if process_type in ["api", "web", "all"]:
        cors = os.getenv("CORS_ORIGINS", "")
        if env_name in ["production", "staging"]:
            if not cors or cors.strip() == "*":
                print("[FAIL] Wildcard '*' or empty CORS_ORIGINS forbidden for API in staging/production.")
                passed = False
            else:
                print(f"[PASS] CORS_ORIGINS configured: {cors}")

    # 6. Storage Provider checks
    storage_provider = os.getenv("STORAGE_PROVIDER", "local").lower()
    print(f"Storage Provider: {storage_provider}")
    if storage_provider == "s3" and process_type in ["api", "web", "worker", "all"]:
        s3_keys = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_REGION", "S3_BUCKET_NAME"]
        for key in s3_keys:
            val = os.getenv(key, "")
            if not val:
                print(f"[FAIL] Missing required S3 setting: {key}")
                passed = False
            else:
                print(f"[PASS] S3 configuration '{key}' present.")

    # 7. Firebase Configuration checks
    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON", "")
    cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH", "")
    require_fb = os.getenv("REQUIRE_FIREBASE", "false").lower() == "true"

    if cred_json:
        try:
            parsed = json.loads(cred_json)
            if not isinstance(parsed, dict):
                print("[FAIL] FIREBASE_CREDENTIALS_JSON must parse to a JSON object.")
                passed = False
            else:
                print("[PASS] FIREBASE_CREDENTIALS_JSON successfully parsed as JSON object.")
        except Exception as e:
            print(f"[FAIL] FIREBASE_CREDENTIALS_JSON parse error: {e}")
            passed = False
    elif cred_path:
        if os.path.exists(cred_path):
            print(f"[PASS] FIREBASE_CREDENTIALS_PATH verified at: {cred_path}")
        else:
            print(f"[FAIL] FIREBASE_CREDENTIALS_PATH points to non-existent file: {cred_path}")
            passed = False

    if require_fb and not cred_json and not (cred_path and os.path.exists(cred_path)):
        print("[FAIL] REQUIRE_FIREBASE is enabled but no valid Firebase credentials found.")
        passed = False

    # 8. Git SHA check
    git_sha = (
        os.getenv("GIT_SHA")
        or os.getenv("RENDER_GIT_COMMIT")
        or os.getenv("VERCEL_GIT_COMMIT_SHA")
        or os.getenv("GITHUB_SHA")
    )
    if git_sha:
        print(f"[PASS] Git SHA resolved: {git_sha}")
    else:
        print("[WARN] Git SHA environment variable not found (will report 'unknown' on health).")

    print("--------------------------------------------------")
    if passed:
        print(">>> PREFLIGHT VERIFICATION SUCCESSFUL: Ready for deployment. <<<")
    else:
        print(">>> PREFLIGHT VERIFICATION FAILED: Fix the above configuration errors. <<<")
    print("==================================================")
    return passed


if __name__ == "__main__":
    proc = sys.argv[1] if len(sys.argv) > 1 else None
    ok = run_preflight_checks(proc_type=proc)
    sys.exit(0 if ok else 1)
