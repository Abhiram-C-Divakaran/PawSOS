"""Unit tests for staging smoke test suite (scripts/staging_smoke_test.py).
Mocks HTTP responses to verify deterministic failure and pass modes without network access.
"""
import sys
from pathlib import Path
import httpx
import pytest

# Add scripts directory to path to import staging_smoke_test
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from staging_smoke_test import run_smoke_tests


def make_mock_client(
    liveness_status=200,
    liveness_env="staging",
    liveness_sha="abc1234",
    liveness_state="ok",
    readiness_status=200,
    readiness_state="ready",
    subsystems_override=None,
    cors_allowed_origin="https://staging.pawreach.org",
    unauth_cors_allowed_origin=None,
    security_headers_override=None,
    fe_status=200,
    fe_body="<!DOCTYPE html><html><head><title>PawReach</title></head><body><div id='root'></div></body></html>",
    deep_route_status=200,
) -> httpx.Client:
    """Constructs a deterministic mock httpx.Client with configurable endpoint responses."""

    services = {
        "database": "healthy",
        "postgis": "healthy",
        "redis": "healthy",
        "celery": "healthy",
        "storage": "healthy",
        "firebase": "healthy",
    }
    if subsystems_override:
        services.update(subsystems_override)

    default_sec_headers = {
        "x-content-type-options": "nosniff",
        "referrer-policy": "strict-origin-when-cross-origin",
        "strict-transport-security": "max-age=31536000; includeSubDomains",
    }
    if security_headers_override is not None:
        default_sec_headers = security_headers_override

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        method = request.method

        # 1. Liveness endpoint
        if "/api/v1/health" in url and not url.endswith("/ready") and method == "GET":
            headers = dict(default_sec_headers)
            body = {
                "status": liveness_state,
                "environment": liveness_env,
                "version": "2.0.0",
                "git_sha": liveness_sha,
            }
            return httpx.Response(liveness_status, json=body, headers=headers)

        # 2. Readiness endpoint
        if url.endswith("/api/v1/health/ready") and method == "GET":
            body = {
                "status": readiness_state,
                "environment": liveness_env,
                "services": services,
            }
            return httpx.Response(readiness_status, json=body, headers=default_sec_headers)

        # 3. CORS preflight on /api/v1/auth/login
        if "/api/v1/auth/login" in url and method == "OPTIONS":
            origin = request.headers.get("origin")
            headers = {}
            if origin == "https://unauthorized.example":
                if unauth_cors_allowed_origin:
                    headers["access-control-allow-origin"] = unauth_cors_allowed_origin
            else:
                if cors_allowed_origin:
                    headers["access-control-allow-origin"] = cors_allowed_origin
                headers["access-control-allow-credentials"] = "true"
            return httpx.Response(204, headers=headers)

        # 4. Frontend root or deep routes
        if request.url.host in ["staging.pawreach.org", "localhost", "127.0.0.1"]:
            if request.url.path in ["/", ""]:
                return httpx.Response(
                    fe_status,
                    text=fe_body,
                    headers={"content-type": "text/html; charset=utf-8"},
                )
            else:
                # Deep route
                return httpx.Response(
                    deep_route_status,
                    text=fe_body if deep_route_status == 200 else "Not Found",
                    headers={"content-type": "text/html; charset=utf-8"},
                )

        return httpx.Response(404, text="Not Found")

    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


class TestSmokeTestUnitSuite:
    """Test suite covering all branch failure modes and pass mode in staging smoke test."""

    def test_all_valid_staging_smoke_test_passes(self):
        client = make_mock_client()
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            frontend_url="https://staging.pawreach.org",
            expected_sha="abc1234",
            expected_env="staging",
            allow_http=False,
            client=client,
        )
        assert passed is True

    def test_insecure_http_rejected_when_https_mandatory(self):
        client = make_mock_client()
        # Should fail immediately without making requests if HTTP used without allow_http
        passed = run_smoke_tests(
            api_url="http://api-staging.pawreach.org",
            frontend_url="https://staging.pawreach.org",
            allow_http=False,
            client=client,
        )
        assert passed is False

    def test_wrong_environment_fails(self):
        client = make_mock_client(liveness_env="development")
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            expected_env="staging",
            client=client,
        )
        assert passed is False

    def test_wrong_git_sha_fails(self):
        client = make_mock_client(liveness_sha="different_sha")
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            expected_sha="expected_sha_123",
            client=client,
        )
        assert passed is False

    def test_readiness_degraded_fails(self):
        client = make_mock_client(
            readiness_state="degraded",
            subsystems_override={"celery": "unavailable"},
        )
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            client=client,
        )
        assert passed is False

    def test_cors_mismatch_fails(self):
        client = make_mock_client(cors_allowed_origin="https://wrong-frontend.example")
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            frontend_url="https://staging.pawreach.org",
            client=client,
        )
        assert passed is False

    def test_cors_wildcard_fails(self):
        client = make_mock_client(cors_allowed_origin="*")
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            frontend_url="https://staging.pawreach.org",
            client=client,
        )
        assert passed is False

    def test_cors_unauthorized_origin_allowed_fails(self):
        # Unauthorized origin receives permission -> security violation, smoke test must fail
        client = make_mock_client(unauth_cors_allowed_origin="https://unauthorized.example")
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            frontend_url="https://staging.pawreach.org",
            client=client,
        )
        assert passed is False

    def test_missing_security_headers_fails(self):
        # Missing strict-transport-security
        client = make_mock_client(security_headers_override={"x-content-type-options": "nosniff"})
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            client=client,
        )
        assert passed is False

    def test_frontend_500_fails(self):
        client = make_mock_client(fe_status=500, fe_body="Internal Server Error")
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            frontend_url="https://staging.pawreach.org",
            client=client,
        )
        assert passed is False

    def test_frontend_deep_route_404_fails(self):
        client = make_mock_client(deep_route_status=404)
        passed = run_smoke_tests(
            api_url="https://api-staging.pawreach.org",
            frontend_url="https://staging.pawreach.org",
            client=client,
        )
        assert passed is False
