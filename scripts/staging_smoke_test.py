#!/usr/bin/env python3
"""PawReach Post-Deployment Staging Smoke Test Suite.
Idempotent, non-destructive verification of staging backend, frontend, CORS, and subsystem readiness.
"""
import argparse
import sys

try:
    import httpx
except ImportError:
    print("Error: 'httpx' is required. Install via: pip install httpx")
    sys.exit(1)


def run_smoke_tests(
    api_url: str,
    frontend_url: str | None = None,
    expected_sha: str | None = None,
) -> bool:
    print("==================================================")
    print("      PawReach Staging Post-Deployment Smoke Test ")
    print("==================================================")
    print(f"API Target URL:      {api_url}")
    print(f"Frontend Target URL: {frontend_url or 'Skipped'}")
    print(f"Expected Git SHA:    {expected_sha or 'Not enforced'}")
    print("--------------------------------------------------")

    all_passed = True
    client = httpx.Client(timeout=15.0, follow_redirects=True)

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

            print(f"      PASS: HTTP 200 OK | status: '{status_val}', env: '{env_val}', version: '{version_val}', sha: '{deployed_sha}'")

            if status_val != "ok":
                print(f"      FAIL: Expected status 'ok', got '{status_val}'")
                all_passed = False

            if expected_sha:
                if deployed_sha == expected_sha:
                    print(f"      PASS: Deployed git_sha matches expected '{expected_sha}'")
                else:
                    print(f"      FAIL: Deployed git_sha '{deployed_sha}' does NOT match expected '{expected_sha}'")
                    all_passed = False
        else:
            print(f"      FAIL: HTTP {resp.status_code} | Response: {resp.text}")
            all_passed = False

        # 2. Backend Subsystem Readiness (/api/v1/health/ready)
        print("\n[2/5] Testing Subsystem Readiness (/api/v1/health/ready)...")
        readiness_url = f"{api_url.rstrip('/')}/api/v1/health/ready"
        resp = client.get(readiness_url)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status")
            services = data.get("services", {})
            print(f"      PASS: HTTP 200 | Overall Status: '{status}'")
            for s_name, s_stat in services.items():
                print(f"            - {s_name}: {s_stat}")
            if status not in ["ready", "ok"]:
                print(f"      WARN: Overall readiness is '{status}' (expected 'ready')")
        else:
            print(f"      FAIL: HTTP {resp.status_code} | Body: {resp.text}")
            all_passed = False

        # 3. CORS Preflight & Security Headers Validation
        print("\n[3/5] Testing CORS Configuration & Security Headers...")
        cors_origin = frontend_url.rstrip('/') if frontend_url else "https://staging.pawreach.org"
        cors_headers = {
            "Origin": cors_origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        cors_resp = client.options(f"{api_url.rstrip('/')}/api/v1/auth/login", headers=cors_headers)
        print(f"      OPTIONS preflight status: {cors_resp.status_code}")
        allowed_origin = cors_resp.headers.get("access-control-allow-origin")
        if allowed_origin:
            print(f"      Access-Control-Allow-Origin: {allowed_origin}")

        sec_headers = [
            "x-content-type-options",
            "x-frame-options",
            "strict-transport-security",
        ]
        for sh in sec_headers:
            val = resp.headers.get(sh)
            if val:
                print(f"      Security header '{sh}': {val}")

        # 4. Frontend SPA Root & Deep Routing Fallback
        if frontend_url:
            print(f"\n[4/5] Testing Frontend Root SPA ({frontend_url})...")
            fe_resp = client.get(frontend_url)
            if fe_resp.status_code == 200:
                print(f"      PASS: HTTP 200 OK | Content-Type: {fe_resp.headers.get('content-type')}")
                if "PawReach" in fe_resp.text or "root" in fe_resp.text or "index" in fe_resp.text:
                    print("      PASS: SPA HTML payload contains application entry point.")
            else:
                print(f"      FAIL: HTTP {fe_resp.status_code}")
                all_passed = False

            # 5. Frontend Deep Routing Tests
            routes = ["/login", "/report", "/rescuer", "/vet", "/ngo"]
            print(f"\n[5/5] Testing Frontend Deep Route Fallbacks: {', '.join(routes)}...")
            for route in routes:
                route_url = f"{frontend_url.rstrip('/')}{route}"
                route_resp = client.get(route_url)
                if route_resp.status_code == 200 and ("PawReach" in route_resp.text or "root" in route_resp.text or "index" in route_resp.text or "<!DOCTYPE" in route_resp.text or "<!doctype" in route_resp.text):
                    print(f"      PASS: {route} -> HTTP 200 OK (Served SPA index)")
                else:
                    print(f"      FAIL: {route} -> HTTP {route_resp.status_code}")
                    all_passed = False
        else:
            print("\n[4/5] Skipping Frontend Root check (no URL provided).")
            print("[5/5] Skipping Frontend Deep Route checks (no URL provided).")

    except Exception as e:
        print(f"\n[ERROR] Smoke test encountered unexpected error: {e}")
        all_passed = False
    finally:
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
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Staging API Base URL")
    parser.add_argument("--frontend-url", default=None, help="Staging Frontend Base URL")
    parser.add_argument("--expected-sha", default=None, help="Expected Git commit SHA from /api/v1/health")
    args = parser.parse_args()

    success = run_smoke_tests(
        api_url=args.api_url,
        frontend_url=args.frontend_url,
        expected_sha=args.expected_sha,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
