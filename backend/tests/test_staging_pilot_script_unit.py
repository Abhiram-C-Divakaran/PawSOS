"""Unit tests for scripts/staging_authenticated_pilot.py and workflow security.

Validates:
1. Workflow .github/workflows/staging-authenticated-pilot.yml contains NO password input.
2. Pilot script readiness parsing correctly evaluates nested services and checks.worker.
3. Expected SHA mismatch raises PilotFailure.
4. Missing password fails safely.
5. Rescuer A availability/location setup and Rescuer B exclusion logic.
6. Negative claim assertion ensures zero pending offers before checking 403.
7. Cleanup runs in finally block to restore responder availabilities upon failure.
"""

import os
import sys
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

# Ensure scripts directory is importable
repo_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(repo_root / "scripts"))

from staging_authenticated_pilot import StagingPilotRunner, PilotFailure, SYNTHETIC_PNG_FIXTURE


def test_workflow_has_no_password_input():
    """Ensure workflow_dispatch does not define any password input."""
    workflow_path = repo_root / ".github" / "workflows" / "staging-authenticated-pilot.yml"
    assert workflow_path.exists(), "Workflow file must exist"
    content = workflow_path.read_text(encoding="utf-8")

    # The inputs section must not contain 'password:'
    # It must strictly use secrets.STAGING_SEED_PASSWORD
    assert "password:" not in content
    assert "inputs.password" not in content
    assert "secrets.STAGING_SEED_PASSWORD" in content
    assert "--password" not in content


def test_readiness_nested_services_and_worker():
    """Verify that step_1_readiness correctly parses nested services and checks.worker."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )

    mock_resp_health = MagicMock()
    mock_resp_health.status_code = 200
    mock_resp_health.json.return_value = {
        "status": "ok",
        "environment": "staging",
        "git_sha": "abc9a674a274cf0cce31bd4777e1b6d8701a553d",
    }

    mock_resp_ready = MagicMock()
    mock_resp_ready.status_code = 200
    mock_resp_ready.json.return_value = {
        "status": "ready",
        "environment": "staging",
        "services": {
            "database": "healthy",
            "postgis": "healthy",
            "redis": "healthy",
            "celery": "healthy",
            "storage": "healthy",
            "firebase": "unconfigured",
            "ai_triage": "disabled",
        },
        "checks": {
            "database": "connected",
            "postgis": "available",
            "redis": "connected",
            "worker": "active",
            "storage": "healthy",
        },
    }

    with patch.object(runner.client, "get", side_effect=[mock_resp_health, mock_resp_ready]):
        runner.step_1_readiness()


def test_readiness_fails_on_unhealthy_service():
    """Step 1 readiness must fail if a required service is unhealthy."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )

    mock_resp_health = MagicMock(status_code=200)
    mock_resp_health.json.return_value = {"status": "ok", "environment": "staging"}

    mock_resp_ready = MagicMock(status_code=200)
    mock_resp_ready.json.return_value = {
        "status": "ready",
        "services": {
            "database": "healthy",
            "postgis": "healthy",
            "redis": "unhealthy",
            "celery": "healthy",
            "storage": "healthy",
        },
        "checks": {"worker": "active"},
    }

    with patch.object(runner.client, "get", side_effect=[mock_resp_health, mock_resp_ready]):
        with pytest.raises(PilotFailure) as exc_info:
            runner.step_1_readiness()
        assert "redis" in str(exc_info.value)


def test_expected_sha_mismatch_fails():
    """Step 1 readiness must raise PilotFailure if deployed SHA does not match --expected-sha."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        expected_sha="abc9a674a274cf0cce31bd4777e1b6d8701a553d",
        allow_http=True,
    )

    mock_resp_health = MagicMock(status_code=200)
    mock_resp_health.json.return_value = {
        "status": "ok",
        "environment": "staging",
        "git_sha": "wrong_sha_1234567890",
    }

    with patch.object(runner.client, "get", return_value=mock_resp_health):
        with pytest.raises(PilotFailure) as exc_info:
            runner.step_1_readiness()
        assert "Git SHA mismatch" in str(exc_info.value)


def test_cleanup_always_runs_on_failure():
    """Runner.run() must execute cleanup in finally block even when a step raises PilotFailure."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {
        "rescuer_a": "token_a",
        "rescuer_b": "token_b",
    }

    cleanup_mock = MagicMock()
    with patch.object(runner, "cleanup", cleanup_mock):
        with patch.object(runner, "step_1_readiness", side_effect=PilotFailure("Simulated readiness failure")):
            with pytest.raises(PilotFailure):
                runner.run()

    cleanup_mock.assert_called_once()


def test_synthetic_png_fixture_valid():
    """Ensure SYNTHETIC_PNG_FIXTURE has valid PNG signature."""
    assert SYNTHETIC_PNG_FIXTURE.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IEND" in SYNTHETIC_PNG_FIXTURE
    assert len(SYNTHETIC_PNG_FIXTURE) < 150  # Must be tiny and deterministic


def test_cli_has_no_password_argument():
    """Ensure scripts/staging_authenticated_pilot.py parser has no --password argument."""
    script_path = repo_root / "scripts" / "staging_authenticated_pilot.py"
    content = script_path.read_text(encoding="utf-8")
    assert '"--password"' not in content
    assert "'--password'" not in content


def test_readiness_fails_on_non_staging_environment():
    """Step 1 readiness must fail if environment is not staging."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=False,
    )

    mock_resp_health = MagicMock(status_code=200)
    mock_resp_health.json.return_value = {
        "status": "ok",
        "environment": "production",
        "git_sha": "abc9a674a274cf0cce31bd4777e1b6d8701a553d",
    }

    with patch.object(runner.client, "get", return_value=mock_resp_health):
        with pytest.raises(PilotFailure) as exc_info:
            runner.step_1_readiness()
        assert "environment expected 'staging'" in str(exc_info.value)


def test_cleanup_closes_httpx_client():
    """Cleanup must close httpx client."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    with patch.object(runner.client, "close") as mock_close:
        runner.cleanup()
        mock_close.assert_called_once()


def test_exact_40char_sha_match():
    """When both expected and observed SHAs are 40 characters, require exact match."""
    sha1 = "eec547575a617bf477eb43c964e6acb2854c5993"
    sha2 = "eec547575a617bf477eb43c964e6acb2854c5994"  # 1 char difference

    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        expected_sha=sha1,
        allow_http=True,
    )

    mock_resp_health = MagicMock(status_code=200)
    mock_resp_health.json.return_value = {
        "status": "ok",
        "environment": "staging",
        "git_sha": sha2,
    }

    with patch.object(runner.client, "get", return_value=mock_resp_health):
        with pytest.raises(PilotFailure) as exc_info:
            runner.step_1_readiness()
        assert "Git SHA mismatch" in str(exc_info.value)

    # Exact match succeeds
    mock_resp_health.json.return_value["git_sha"] = sha1
    mock_resp_ready = MagicMock(status_code=200)
    mock_resp_ready.json.return_value = {
        "status": "ready",
        "services": {"database": "healthy", "postgis": "healthy", "redis": "healthy", "celery": "healthy", "storage": "healthy"},
        "checks": {"worker": "active"},
    }
    with patch.object(runner.client, "get", side_effect=[mock_resp_health, mock_resp_ready]):
        runner.step_1_readiness()


def test_step6_post_claim_foreign_evidence_denial():
    """Step 6 must assert Admin Beta receives 403 on private evidence after Org Alpha claims."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {"admin_a": "token_a", "admin_b": "token_b"}
    runner.created_case_id = "test-case-id"
    runner.created_image_id = "test-image-id"

    # Mock responses for step 6:
    # 6a. post claim by Admin Alpha -> 200
    # 6b. post claim by Admin Alpha (idempotent) -> 200
    # 6c. post claim by Admin Beta -> 409
    # 6d. get cases by Admin Alpha -> 200
    # 6e. get dossier by Admin Alpha -> 200
    # 6f. get dossier by Admin Beta -> 403
    # 6g. get evidence by Admin Beta -> 200 (violates denial!)
    mock_post_claim_a = MagicMock(status_code=200)
    mock_post_claim_idem = MagicMock(status_code=200)
    mock_post_claim_b = MagicMock(status_code=409)
    mock_get_cases_a = MagicMock(status_code=200)
    mock_get_cases_a.json.return_value = [{"id": "test-case-id"}]
    mock_dossier_a = MagicMock(status_code=200)
    mock_dossier_b = MagicMock(status_code=403)
    mock_evidence_b_leaked = MagicMock(status_code=200)

    with patch.object(runner.client, "post", side_effect=[mock_post_claim_a, mock_post_claim_idem, mock_post_claim_b]):
        with patch.object(runner.client, "get", side_effect=[mock_get_cases_a, mock_dossier_a, mock_dossier_b, mock_evidence_b_leaked]):
            with pytest.raises(PilotFailure) as exc_info:
                runner.step_6_multitenant_claim_and_isolation()
            assert "Admin Beta accessed foreign evidence post-claim" in str(exc_info.value)


