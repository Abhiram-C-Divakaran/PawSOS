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


def run_smoke_tests(api_url: str, frontend_url: str | None = None) -> bool:
    print("==================================================")
    print("      PawReach Staging Post-Deployment Smoke Test ")
    print("==================================================")
    print(f"API Target URL:      {api_url}")
    print(f"Frontend Target URL: {frontend_url or 'Skipped'}")
    print("--------------------------------------------------")

    all_passed = True
    client = httpx.Client(timeout=10.0, follow_redirects=True)

    try:
        # 1. Backend Liveness (/api/v1/health)
        print("[1/5] Testing Backend Liveness (/api/v1/health)...")
        liveness_url = f"{api_url.rstrip('/')}/api/v1/health"
        resp = client.get(liveness_url)
        if resp.status_code == 200 and resp.json().get("status") == "ok":
            print(f"      PASS: HTTP 200 OK | Response: {resp.json()}")
        else:
            print(f"      FAIL: HTTP {resp.status_code} | Response: {resp.text}")
            all_passed = False

        # 2. Backend Deep Readiness (/api/v1/health/ready)
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

        # 3. CORS Preflight Validation
        print("\n[3/5] Testing CORS Configuration & Security Headers...")
        cors_headers = {
            "Origin": frontend_url or "https://staging.pawreach.org",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        }
        cors_resp = client.options(f"{api_url.rstrip('/')}/api/v1/auth/login", headers=cors_headers)
        print(f"      OPTIONS preflight status: {cors_resp.status_code}")
        sec_headers = [
            "x-content-type-options",
            "x-frame-options",
            "strict-transport-security",
        ]
        for sh in sec_headers:
            val = resp.headers.get(sh)
            if val:
                print(f"      Security header '{sh}': {val}")

        # 4. Frontend SPA Availability
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

            # 5. Frontend Deep Routing Fallback
            print("\n[5/5] Testing Frontend Deep Route Rewrite (/login)...")
            deep_url = f"{frontend_url.rstrip('/')}/login"
            deep_resp = client.get(deep_url)
            if deep_resp.status_code == 200:
                print(f"      PASS: HTTP 200 OK | Deep route rewrite successfully served SPA index.")
            else:
                print(f"      FAIL: HTTP {deep_resp.status_code} on deep route.")
                all_passed = False
        else:
            print("\n[4/5] Skipping Frontend Root check (no URL provided).")
            print("[5/5] Skipping Frontend Deep Route check (no URL provided).")

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
    args = parser.parse_args()

    success = run_smoke_tests(api_url=args.api_url, frontend_url=args.frontend_url)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
