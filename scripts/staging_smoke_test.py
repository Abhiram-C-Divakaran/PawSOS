#!/usr/bin/env python3
"""PawReach Post-Deployment Staging Smoke Test Suite.
Idempotent, non-destructive verification of staging backend, frontend, CORS, and subsystem readiness.
"""
import argparse
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    print("Error: 'httpx' is required. Install via: pip install httpx")
    sys.exit(1)


def run_smoke_tests(
    api_url: str,
    frontend_url: Optional[str] = None,
    expected_sha: Optional[str] = None,
    expected_env: Optional[str] = "staging",
    allow_http: bool = False,
    require_firebase: bool = False,
    client: Optional[httpx.Client] = None,
) -> bool:
    print("==================================================")
    print("      PawReach Staging Post-Deployment Smoke Test ")
    print("==================================================")
    print(f"API Target URL:      {api_url}")
    print(f"Frontend Target URL: {frontend_url or 'Skipped'}")
    print(f"Expected Git SHA:    {expected_sha or 'Not enforced'}")
    print(f"Expected Env:        {expected_env or 'Not enforced'}")
    print(f"HTTPS Enforced:      {not allow_http}")
    print(f"Firebase Required:   {require_firebase}")
    print("--------------------------------------------------")

    all_passed = True

    # 0. Protocol Validation (HTTPS mandatory in staging)
    if not allow_http:
        if not api_url.startswith("https://"):
            print(f"[FAIL] Insecure API URL '{api_url}'. Staging requires HTTPS (https://).")
            all_passed = False
        if frontend_url and not frontend_url.startswith("https://"):
            print(f"[FAIL] Insecure Frontend URL '{frontend_url}'. Staging requires HTTPS (https://).")
            all_passed = False
        if not all_passed:
            print("Aborting smoke tests: Insecure HTTP detected when HTTPS is mandatory.")
            return False

    owns_client = False
    if client is None:
        client = httpx.Client(timeout=15.0, follow_redirects=True)
        owns_client = True

    try:
        # 1. Backend Liveness & Metadata (/api/v1/health)
        print("[1/5] Testing Backend Liveness & Version Telemetry (/api/v1/health)...")
        liveness_url = f"{api_url.rstrip('/')}/api/v1/health"
        resp = client.get(liveness_url)
        if resp.status_code == 200:
            data = resp.json()
            status_val = data.get("status")
            version_val = data.get("version")
            env_val = data.get("environment")
            deployed_sha = data.get("git_sha")

            print(f"      HTTP 200 OK | status: '{status_val}', env: '{env_val}', version: '{version_val}', sha: '{deployed_sha}'")

            if status_val != "ok":
                print(f"      [FAIL] Expected status 'ok', got '{status_val}'")
                all_passed = False
            else:
                print("      [PASS] Liveness status is 'ok'")

            if expected_env:
                if env_val == expected_env:
                    print(f"      [PASS] Environment '{env_val}' matches expected '{expected_env}'")
                else:
                    print(f"      [FAIL] Environment '{env_val}' does NOT match expected '{expected_env}'")
                    all_passed = False

            if expected_sha:
                if deployed_sha == expected_sha:
                    print(f"      [PASS] Deployed git_sha matches expected '{expected_sha}'")
                else:
                    print(f"      [FAIL] Deployed git_sha '{deployed_sha}' does NOT match expected '{expected_sha}'")
                    all_passed = False
        else:
            print(f"      [FAIL] HTTP {resp.status_code} | Response: {resp.text}")
            all_passed = False

        # 2. Backend Subsystem Readiness (/api/v1/health/ready) with bounded polling
        print("\n[2/5] Testing Subsystem Deep Readiness (/api/v1/health/ready)...")
        readiness_url = f"{api_url.rstrip('/')}/api/v1/health/ready"
        
        max_ready_attempts = 15  # 15 attempts * 3s = 45s max grace period
        ready_poll_interval = 3.0
        ready_success = False
        last_ready_resp = None
        last_ready_data = {}

        import time

        for attempt in range(1, max_ready_attempts + 1):
            try:
                ready_resp = client.get(readiness_url)
                last_ready_resp = ready_resp
                if ready_resp.status_code == 200:
                    ready_data = ready_resp.json()
                    last_ready_data = ready_data
                    ready_status = ready_data.get("status")
                    services = ready_data.get("services", {})
                    checks = ready_data.get("checks", {})
                    
                    mandatory_subsystems = ["database", "postgis", "redis", "celery", "storage"]
                    subsystems_healthy = all(services.get(s) == "healthy" for s in mandatory_subsystems)
                    
                    if ready_status in ["ready", "ok"] and subsystems_healthy:
                        ready_success = True
                        print(f"      HTTP 200 | Overall Status: '{ready_status}' (poll attempt {attempt}/{max_ready_attempts})")
                        for s_name, s_stat in services.items():
                            age = checks.get("worker_heartbeat_age_seconds")
                            extra = f" (age: {age}s)" if s_name == "celery" and age is not None else ""
                            print(f"            - {s_name}: {s_stat}{extra}")
                        break
                    else:
                        print(f"      [Poll {attempt}/{max_ready_attempts}] Readiness not yet fully healthy: status='{ready_status}', services={services}")
                else:
                    try:
                        last_ready_data = ready_resp.json()
                    except Exception:
                        last_ready_data = {"raw_text": ready_resp.text}
                    print(f"      [Poll {attempt}/{max_ready_attempts}] HTTP {ready_resp.status_code} | Body: {ready_resp.text}")
            except Exception as req_err:
                print(f"      [Poll {attempt}/{max_ready_attempts}] Readiness probe error: {type(req_err).__name__}")

            if attempt < max_ready_attempts:
                time.sleep(ready_poll_interval)

        if ready_success:
            print("      [PASS] Overall readiness status is 'ready' and all mandatory subsystems are healthy.")
            # Firebase requirement check
            services = last_ready_data.get("services", {})
            fb_stat = services.get("firebase")
            if require_firebase:
                if fb_stat != "healthy":
                    print(f"      [FAIL] Firebase is required but reported status: '{fb_stat}'")
                    all_passed = False
                else:
                    print("      [PASS] Firebase is required and healthy")
            else:
                print(f"      [INFO] Firebase status: '{fb_stat}' (REQUIRE_FIREBASE=false)")
        else:
            print(f"      [FAIL] Subsystem readiness failed after {max_ready_attempts * ready_poll_interval:.0f}s timeout.")
            if last_ready_data:
                services = last_ready_data.get("services", {})
                checks = last_ready_data.get("checks", {})
                print("      Sanitized Diagnostics:")
                print(f"            - Overall Status: {last_ready_data.get('status', 'unknown')}")
                print(f"            - Worker Check:   {checks.get('worker', 'unknown')}")
                for s_name, s_stat in services.items():
                    print(f"            - Subsystem '{s_name}': {s_stat}")
            all_passed = False

        # 3. CORS Preflight & Security Headers Validation
        print("\n[3/5] Testing CORS Preflight & Security Headers...")
        cors_origin = frontend_url.rstrip('/') if frontend_url else "https://staging.pawreach.org"
        cors_headers = {
            "Origin": cors_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        cors_resp = client.options(f"{api_url.rstrip('/')}/api/v1/auth/login", headers=cors_headers)
        allowed_origin = cors_resp.headers.get("access-control-allow-origin")

        if allowed_origin == cors_origin:
            print(f"      [PASS] Authorized origin '{cors_origin}' granted CORS access.")
        elif allowed_origin == "*":
            print("      [FAIL] Wildcard '*' CORS origin is forbidden in staging!")
            all_passed = False
        else:
            print(f"      [FAIL] Expected Access-Control-Allow-Origin '{cors_origin}', got '{allowed_origin}'")
            all_passed = False

        # Test unauthorized origin
        unauth_headers = {
            "Origin": "https://unauthorized.example",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        unauth_resp = client.options(f"{api_url.rstrip('/')}/api/v1/auth/login", headers=unauth_headers)
        unauth_allow = unauth_resp.headers.get("access-control-allow-origin")
        if unauth_allow == "https://unauthorized.example" or unauth_allow == "*":
            print(f"      [FAIL] Unauthorized origin received permissive CORS header: '{unauth_allow}'")
            all_passed = False
        else:
            print("      [PASS] Unauthorized origin https://unauthorized.example was denied CORS permission.")

        # Security Headers assertion on API
        sec_header_checks = {
            "x-content-type-options": "nosniff",
            "referrer-policy": None,
        }
        for header_name, expected_val in sec_header_checks.items():
            header_val = resp.headers.get(header_name)
            if not header_val:
                print(f"      [FAIL] Missing required security header: '{header_name}'")
                all_passed = False
            elif expected_val and expected_val.lower() not in header_val.lower():
                print(f"      [FAIL] Header '{header_name}' expected '{expected_val}', got '{header_val}'")
                all_passed = False
            else:
                print(f"      [PASS] Security header '{header_name}': '{header_val}'")

        if api_url.startswith("https://"):
            hsts_val = resp.headers.get("strict-transport-security")
            if not hsts_val:
                print("      [FAIL] Missing Strict-Transport-Security header on HTTPS API.")
                all_passed = False
            else:
                print(f"      [PASS] Strict-Transport-Security: '{hsts_val}'")

        # 4. Frontend SPA Root & Deep Routing Fallback
        if frontend_url:
            print(f"\n[4/5] Testing Frontend Root SPA ({frontend_url})...")
            fe_resp = client.get(frontend_url)
            if fe_resp.status_code == 200:
                print(f"      PASS: HTTP 200 OK | Content-Type: {fe_resp.headers.get('content-type')}")
                if "PawReach" in fe_resp.text or "root" in fe_resp.text or "index" in fe_resp.text or "<!DOCTYPE" in fe_resp.text or "<!doctype" in fe_resp.text:
                    print("      [PASS] SPA HTML payload contains application entry point.")
                else:
                    print("      [FAIL] SPA HTML does not contain expected application markers.")
                    all_passed = False
            else:
                print(f"      [FAIL] Frontend Root returned HTTP {fe_resp.status_code}")
                all_passed = False

            # 5. Frontend Deep Routing Tests
            routes = ["/login", "/report", "/rescuer", "/vet", "/ngo"]
            print(f"\n[5/5] Testing Frontend Deep Route Fallbacks: {', '.join(routes)}...")
            for route in routes:
                route_url = f"{frontend_url.rstrip('/')}{route}"
                route_resp = client.get(route_url)
                if route_resp.status_code == 200 and ("PawReach" in route_resp.text or "root" in route_resp.text or "index" in route_resp.text or "<!DOCTYPE" in route_resp.text or "<!doctype" in route_resp.text):
                    print(f"      [PASS] {route} -> HTTP 200 OK (Served SPA index)")
                else:
                    print(f"      [FAIL] {route} -> HTTP {route_resp.status_code}")
                    all_passed = False
        else:
            print("\n[4/5] Skipping Frontend Root check (no URL provided).")
            print("[5/5] Skipping Frontend Deep Route checks (no URL provided).")

    except Exception as e:
        print(f"\n[ERROR] Smoke test encountered unexpected error: {e}")
        all_passed = False
    finally:
        if owns_client:
            client.close()

    print("\n--------------------------------------------------")
    if all_passed:
        print(">>> ALL STAGING SMOKE TESTS PASSED SUCCESSFULLY <<<")
    else:
        print(">>> STAGING SMOKE TESTS FAILED OR REPORTED DEGRADATION <<<")
    print("==================================================")
    return all_passed


def main():
    parser = argparse.ArgumentParser(description="PawReach Staging Smoke Test")
    parser.add_argument("--api-url", default="https://api-staging.pawreach.org", help="Staging API Base URL")
    parser.add_argument("--frontend-url", default=None, help="Staging Frontend Base URL")
    parser.add_argument("--expected-sha", default=None, help="Expected Git commit SHA from /api/v1/health")
    parser.add_argument("--environment", default="staging", help="Expected environment name (default: staging)")
    parser.add_argument("--allow-http", action="store_true", default=False, help="Allow HTTP instead of mandatory HTTPS (local dev only)")
    parser.add_argument("--require-firebase", action="store_true", default=False, help="Fail smoke test if Firebase is unconfigured")
    args = parser.parse_args()

    success = run_smoke_tests(
        api_url=args.api_url,
        frontend_url=args.frontend_url,
        expected_sha=args.expected_sha,
        expected_env=args.environment,
        allow_http=args.allow_http,
        require_firebase=args.require_firebase,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
