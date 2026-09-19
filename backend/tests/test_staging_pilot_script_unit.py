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

import io
import os
import sys
from pathlib import Path
import httpx
import pytest
from PIL import Image
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


def test_readiness_retries_transient_timeout_then_succeeds():
    """A free-tier cold-start timeout should be retried before strict validation."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        expected_sha="abc9a674a274cf0cce31bd4777e1b6d8701a553d",
        allow_http=True,
    )

    health = MagicMock(status_code=200)
    health.json.return_value = {
        "status": "ok",
        "environment": "staging",
        "git_sha": "abc9a674a274cf0cce31bd4777e1b6d8701a553d",
    }
    ready = MagicMock(status_code=200)
    ready.json.return_value = {
        "status": "ready",
        "services": {
            "database": "healthy",
            "postgis": "healthy",
            "redis": "healthy",
            "celery": "healthy",
            "storage": "healthy",
        },
        "checks": {"worker": "active"},
    }

    with patch.object(
        runner.client,
        "get",
        side_effect=[httpx.ReadTimeout("cold start"), health, ready],
    ) as mock_get:
        with patch("staging_authenticated_pilot.time.sleep") as mock_sleep:
            runner.step_1_readiness()

    assert mock_get.call_count == 3
    mock_sleep.assert_called_once_with(5.0)


def test_readiness_persistent_timeout_exhausts_bounded_retries():
    """Persistent transport failure must still terminate after the bounded wake-up window."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )

    with patch.object(
        runner.client,
        "get",
        side_effect=httpx.ReadTimeout("still sleeping"),
    ) as mock_get:
        with patch("staging_authenticated_pilot.time.sleep") as mock_sleep:
            with pytest.raises(PilotFailure, match=r"/health after 4 attempts .*ReadTimeout"):
                runner.step_1_readiness()

    assert mock_get.call_count == 4
    assert mock_sleep.call_count == 3


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
    """Ensure the synthetic evidence fixture is a genuinely decodable PNG."""
    assert SYNTHETIC_PNG_FIXTURE.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IEND" in SYNTHETIC_PNG_FIXTURE
    assert len(SYNTHETIC_PNG_FIXTURE) < 150  # Must be tiny and deterministic

    # Mirror the hosted storage service's Pillow integrity check so a fixture
    # with a valid signature but corrupt chunks cannot pass CI again.
    with Image.open(io.BytesIO(SYNTHETIC_PNG_FIXTURE)) as image:
        assert image.format == "PNG"
        image.verify()

    # Reopen after verify() and force pixel decoding, matching the optimizer's
    # second pass before it saves the normalized upload.
    with Image.open(io.BytesIO(SYNTHETIC_PNG_FIXTURE)) as image:
        assert image.size == (1, 1)
        image.load()


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


def test_rescuer_a_baseline_fetch_failure_aborts_without_mutation():
    """A. Rescuer A baseline fetch failure aborts pilot; no PATCH occurs in step 3 or cleanup."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {"rescuer_a": "token_a", "rescuer_b": "token_b"}

    mock_prof_a_fail = MagicMock(status_code=500)
    mock_patch = MagicMock()

    with patch.object(runner.client, "get", return_value=mock_prof_a_fail):
        with patch.object(runner.client, "patch", mock_patch):
            with pytest.raises(PilotFailure) as exc_info:
                runner.step_3_deterministic_setup_and_create_case()
            assert "Failed fetching baseline profile for Rescuer A" in str(exc_info.value)
            runner.cleanup()

    mock_patch.assert_not_called()
    assert runner.rescuer_a_availability_mutated is False
    assert runner.rescuer_a_location_mutated is False
    assert runner.rescuer_b_availability_mutated is False


def test_rescuer_b_baseline_fetch_failure_aborts_without_mutation():
    """B. Rescuer A baseline succeeds but Rescuer B baseline fails: aborts without mutating A or B."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {"rescuer_a": "token_a", "rescuer_b": "token_b"}

    mock_prof_a = MagicMock(status_code=200)
    mock_prof_a.json.return_value = {"availability_status": "OFFLINE", "latitude": 9.9, "longitude": 76.2}

    mock_prof_b_fail = MagicMock(status_code=502)
    mock_patch = MagicMock()

    with patch.object(runner.client, "get", side_effect=[mock_prof_a, mock_prof_b_fail]):
        with patch.object(runner.client, "patch", mock_patch):
            with pytest.raises(PilotFailure) as exc_info:
                runner.step_3_deterministic_setup_and_create_case()
            assert "Failed fetching baseline profile for Rescuer B" in str(exc_info.value)
            runner.cleanup()

    mock_patch.assert_not_called()
    assert runner.rescuer_a_orig_state is not None
    assert runner.rescuer_b_orig_state is None
    assert runner.rescuer_a_availability_mutated is False
    assert runner.rescuer_b_availability_mutated is False


def test_availability_and_location_mutations_set_flags_and_restore_exactly():
    """C, D, F. Successful mutations set flags; cleanup restores exact original statuses and coordinates."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {"rescuer_a": "token_a", "rescuer_b": "token_b", "citizen": "token_cit"}

    mock_prof_a = MagicMock(status_code=200)
    mock_prof_a.json.return_value = {"availability_status": "OFFLINE", "latitude": 10.05, "longitude": 76.35}

    mock_prof_b = MagicMock(status_code=200)
    mock_prof_b.json.return_value = {"availability_status": "BUSY", "latitude": None, "longitude": None}

    mock_patch_avail_a = MagicMock(status_code=200)
    mock_patch_loc_a = MagicMock(status_code=200)
    mock_patch_avail_b = MagicMock(status_code=200)

    mock_upload = MagicMock(status_code=200)
    mock_upload.json.return_value = {"image_url": "cases/test.png"}

    mock_case = MagicMock(status_code=201)
    mock_case.json.return_value = {
        "id": "case-123",
        "triage_priority": "CRITICAL",
        "triage_score": 85,
        "status": "REPORTED",
        "images": [{"id": "img-123"}],
    }

    with patch.object(runner.client, "get", side_effect=[mock_prof_a, mock_prof_b]):
        with patch.object(runner.client, "patch", side_effect=[mock_patch_avail_a, mock_patch_loc_a, mock_patch_avail_b]):
            with patch.object(runner.client, "post", side_effect=[mock_upload, mock_case]):
                runner.step_3_deterministic_setup_and_create_case()

    assert runner.rescuer_a_availability_mutated is True
    assert runner.rescuer_a_location_mutated is True
    assert runner.rescuer_b_availability_mutated is True

    patch_restore_calls = []
    def mock_restore(url, **kwargs):
        patch_restore_calls.append((url, kwargs.get("json")))
        return MagicMock(status_code=200)

    with patch.object(runner.client, "patch", side_effect=mock_restore):
        with patch.object(runner.client, "close") as mock_close:
            runner.cleanup()
            mock_close.assert_called_once()

    assert len(patch_restore_calls) == 3
    assert patch_restore_calls[0][0].endswith("/api/v1/rescuers/me/availability")
    assert patch_restore_calls[0][1] == {"availability_status": "OFFLINE"}

    assert patch_restore_calls[1][0].endswith("/api/v1/rescuers/me/location")
    assert patch_restore_calls[1][1] == {"latitude": 10.05, "longitude": 76.35}

    assert patch_restore_calls[2][0].endswith("/api/v1/rescuers/me/availability")
    assert patch_restore_calls[2][1] == {"availability_status": "BUSY"}


def test_mutation_patch_failure_leaves_flag_false_preventing_falsy_restore():
    """E. If mutation PATCH fails, flag remains False and cleanup does not restore unmutated state."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {"rescuer_a": "token_a", "rescuer_b": "token_b"}

    mock_prof_a = MagicMock(status_code=200)
    mock_prof_a.json.return_value = {"availability_status": "AVAILABLE", "latitude": 9.9, "longitude": 76.2}

    mock_prof_b = MagicMock(status_code=200)
    mock_prof_b.json.return_value = {"availability_status": "AVAILABLE", "latitude": None, "longitude": None}

    mock_patch_avail_fail = MagicMock(status_code=500)

    with patch.object(runner.client, "get", side_effect=[mock_prof_a, mock_prof_b]):
        with patch.object(runner.client, "patch", return_value=mock_patch_avail_fail):
            with pytest.raises(PilotFailure) as exc_info:
                runner.step_3_deterministic_setup_and_create_case()
            assert "Failed setting Rescuer A AVAILABLE" in str(exc_info.value)

    assert runner.rescuer_a_availability_mutated is False
    assert runner.rescuer_a_location_mutated is False
    assert runner.rescuer_b_availability_mutated is False

    mock_cleanup_patch = MagicMock()
    with patch.object(runner.client, "patch", mock_cleanup_patch):
        runner.cleanup()

    mock_cleanup_patch.assert_not_called()


def test_cleanup_logs_warn_on_non_200():
    """G. Cleanup must log WARN (not PASS) when restoration API call returns non-200."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {"rescuer_a": "token_a", "rescuer_b": "token_b"}
    runner.rescuer_a_orig_state = {"availability_status": "AVAILABLE", "latitude": None, "longitude": None}
    runner.rescuer_b_orig_state = {"availability_status": "AVAILABLE", "latitude": None, "longitude": None}
    runner.rescuer_a_availability_mutated = True
    runner.rescuer_b_availability_mutated = True

    mock_resp_fail = MagicMock(status_code=503)
    mock_log = MagicMock()

    with patch.object(runner.client, "patch", return_value=mock_resp_fail):
        with patch.object(runner, "log", mock_log):
            runner.cleanup()

    warn_calls = [c for c in mock_log.call_args_list if c.kwargs.get("status") == "WARN" or (len(c.args) >= 3 and c.args[2] == "WARN")]
    assert any("503" in str(c) for c in warn_calls)


def test_cleanup_closes_client_even_when_patch_raises():
    """H. Client must still close cleanly even if PATCH throws a network exception or after PilotFailure."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    runner.tokens = {"rescuer_a": "token_a", "rescuer_b": "token_b"}
    runner.rescuer_a_orig_state = {"availability_status": "AVAILABLE", "latitude": None, "longitude": None}
    runner.rescuer_a_availability_mutated = True

    with patch.object(runner.client, "patch", side_effect=RuntimeError("Network down")):
        with patch.object(runner.client, "close") as mock_close:
            runner.cleanup()
            mock_close.assert_called_once()

def test_step2_uses_oauth2_form_contract_for_all_seeded_actors():
    """Step 2 must send OAuth2 form fields username/password, never JSON email/password."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )

    responses = []
    for index in range(8):
        response = MagicMock(status_code=200)
        response.json.return_value = {"access_token": f"token-{index}"}
        responses.append(response)

    with patch.object(runner.client, "post", side_effect=responses) as mock_post:
        runner.step_2_authenticate()

    assert len(mock_post.call_args_list) == 8
    expected_emails = [
        "citizen@staging.pawsos.org",
        "rescuer.a@staging.pawsos.org",
        "rescuer.b@staging.pawsos.org",
        "vet@staging.pawsos.org",
        "vet.b@staging.pawsos.org",
        "admin@staging.pawsos.org",
        "admin.b@staging.pawsos.org",
        "superadmin@staging.pawsos.org",
    ]
    for call, expected_email in zip(mock_post.call_args_list, expected_emails):
        assert call.kwargs.get("json") is None
        assert call.kwargs["data"] == {
            "username": expected_email,
            "password": "TestPassword123!",
        }

    assert all(runner.tokens.values())


def test_step2_fails_on_auth_error_without_registering_dynamic_citizen():
    """A seeded actor auth failure must be surfaced, not masked by dynamic registration."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    failed = MagicMock(status_code=401)
    failed.text = '{"detail":"Incorrect email/phone or password"}'

    with patch.object(runner.client, "post", return_value=failed) as mock_post:
        with pytest.raises(PilotFailure, match="Failed login for citizen"):
            runner.step_2_authenticate()

    mock_post.assert_called_once()
    assert runner.tokens == {}


def test_step2_rejects_http_200_without_access_token():
    """A malformed success response must not be treated as authenticated."""
    runner = StagingPilotRunner(
        base_url="https://pawreach-api.onrender.com",
        seed_password="TestPassword123!",
        allow_http=True,
    )
    response = MagicMock(status_code=200)
    response.json.return_value = {"token_type": "bearer"}

    with patch.object(runner.client, "post", return_value=response):
        with pytest.raises(PilotFailure, match="without an access token"):
            runner.step_2_authenticate()

    assert runner.tokens == {}

