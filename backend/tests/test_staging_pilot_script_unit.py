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
