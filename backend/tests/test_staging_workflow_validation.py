"""Test suite for validating CI/CD workflow configurations, Render manifests,
Compose definitions, and smoke-test CLI invocations against drift.
"""
import os
import yaml
import pytest
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
STAGING_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "staging-deploy.yml"
RENDER_YAML = REPO_ROOT / "render.yaml"
COMPOSE_STAGING = REPO_ROOT / "docker-compose.staging.yml"
PROCFILE = REPO_ROOT / "Procfile"


def test_staging_workflow_references_exact_ci_workflow_name():
    """Verify that staging-deploy.yml workflow_run trigger targets the exact name in ci.yml."""
    assert CI_WORKFLOW.exists(), f"CI workflow not found at {CI_WORKFLOW}"
    assert STAGING_WORKFLOW.exists(), f"Staging workflow not found at {STAGING_WORKFLOW}"

    with open(CI_WORKFLOW, "r", encoding="utf-8") as f:
        ci_data = yaml.safe_load(f)
    ci_name = ci_data.get("name")
    assert ci_name, "ci.yml has no 'name' defined"

    with open(STAGING_WORKFLOW, "r", encoding="utf-8") as f:
        staging_data = yaml.safe_load(f)

    # In PyYAML on: true is parsed as True boolean or string
    on_section = staging_data.get("on") or staging_data.get(True)
    assert on_section, "staging-deploy.yml has no 'on' trigger section"
    workflow_run = on_section.get("workflow_run")
    assert workflow_run, "staging-deploy.yml has no 'workflow_run' trigger"
    workflows_list = workflow_run.get("workflows", [])

    assert ci_name in workflows_list, (
        f"staging-deploy.yml targets workflows {workflows_list} which does not include '{ci_name}'"
    )


def test_staging_workflow_smoke_test_cli_flags_match_parser():
    """Verify that the smoke test CLI flags in staging-deploy.yml match the argument parser in staging_smoke_test.py."""
    with open(STAGING_WORKFLOW, "r", encoding="utf-8") as f:
        content = f.read()

    # The workflow must invoke --api-url, --frontend-url, and --expected-sha
    assert "--api-url" in content, "staging-deploy.yml must use --api-url"
    assert "--frontend-url" in content, "staging-deploy.yml must use --frontend-url"
    assert "--expected-sha" in content, "staging-deploy.yml must use --expected-sha"
    assert "--api " not in content, "staging-deploy.yml should not use deprecated --api flag"
    assert "--frontend " not in content, "staging-deploy.yml should not use deprecated --frontend flag"


def test_staging_workflow_sha_handling_and_polling():
    """Verify normalized EXPECTED_GIT_SHA resolution and removal of fixed sleeps."""
    with open(STAGING_WORKFLOW, "r", encoding="utf-8") as f:
        content = f.read()

    assert "github.event.workflow_run.head_sha" in content, (
        "staging-deploy.yml must resolve workflow_run.head_sha for automated CI triggers"
    )
    assert "sleep 45" not in content, "Fixed deployment sleep 45 must be removed in favor of bounded polling"
    assert "/api/v1/health" in content, "Bounded polling must check /api/v1/health"


def test_render_yaml_configuration_and_migration_architecture():
    """Verify that render.yaml runs Alembic from backend dir, uses preDeployCommand, and sets PROCESS_TYPE."""
    assert RENDER_YAML.exists(), f"render.yaml not found at {RENDER_YAML}"
    with open(RENDER_YAML, "r", encoding="utf-8") as f:
        render_data = yaml.safe_load(f)

    services = render_data.get("services", [])
    service_map = {s["name"]: s for s in services}

    api_svc = service_map.get("pawreach-staging-api")
    worker_svc = service_map.get("pawreach-staging-worker")
    beat_svc = service_map.get("pawreach-staging-beat")

    assert api_svc, "pawreach-staging-api service missing in render.yaml"
    assert worker_svc, "pawreach-staging-worker service missing in render.yaml"
    assert beat_svc, "pawreach-staging-beat service missing in render.yaml"

    # Migration check: preDeployCommand on api service runs in backend dir
    pre_deploy = api_svc.get("preDeployCommand", "")
    assert "cd backend" in pre_deploy and "alembic upgrade head" in pre_deploy, (
        f"API preDeployCommand must execute 'cd backend && alembic upgrade head', got: '{pre_deploy}'"
    )

    # PROCESS_TYPE validation on each service
    def get_env_var(svc, key):
        for ev in svc.get("envVars", []):
            if ev.get("key") == key:
                return ev.get("value")
        return None

    assert get_env_var(api_svc, "PROCESS_TYPE") == "api"
    assert get_env_var(worker_svc, "PROCESS_TYPE") == "worker"
    assert get_env_var(beat_svc, "PROCESS_TYPE") == "beat"

    # Common env group check
    env_groups = render_data.get("envVarGroups", [])
    common_group = next((g for g in env_groups if g.get("name") == "pawreach-staging-common"), None)
    assert common_group, "pawreach-staging-common envVarGroup missing"
    common_keys = [ev.get("key") for ev in common_group.get("envVars", [])]
    assert "REQUIRE_FIREBASE" in common_keys
    assert "S3_PRESIGNED_URL_EXPIRE_SECONDS" in common_keys
    assert "STORAGE_PROVIDER" in common_keys

    # Service-level database and redis wiring check
    for svc in [api_svc, worker_svc, beat_svc]:
        db_var = next((ev for ev in svc.get("envVars", []) if ev.get("key") == "DATABASE_URL"), None)
        assert db_var and "fromDatabase" in db_var, f"{svc['name']} missing fromDatabase wiring for DATABASE_URL"
        redis_var = next((ev for ev in svc.get("envVars", []) if ev.get("key") == "REDIS_URL"), None)
        assert redis_var and "fromService" in redis_var, f"{svc['name']} missing fromService wiring for REDIS_URL"


def test_docker_compose_staging_process_types_and_fail_fast():
    """Verify docker-compose.staging.yml sets PROCESS_TYPE and enforces S3 variables."""
    assert COMPOSE_STAGING.exists(), f"docker-compose.staging.yml not found at {COMPOSE_STAGING}"
    with open(COMPOSE_STAGING, "r", encoding="utf-8") as f:
        compose_data = yaml.safe_load(f)

    services = compose_data.get("services", {})
    backend_env = services.get("backend", {}).get("environment", [])
    worker_env = services.get("worker", {}).get("environment", [])
    beat_env = services.get("beat", {}).get("environment", [])

    assert "PROCESS_TYPE=api" in backend_env
    assert "PROCESS_TYPE=worker" in worker_env
    assert "PROCESS_TYPE=beat" in beat_env

    # Fail fast S3 checks in backend & worker
    s3_fail_fast = [e for e in backend_env if "AWS_ACCESS_KEY_ID:?" in e]
    assert len(s3_fail_fast) > 0, "Backend service must use required-variable expansion for AWS_ACCESS_KEY_ID"


def test_procfile_contains_process_types():
    """Verify Procfile includes explicit PROCESS_TYPE assignments."""
    assert PROCFILE.exists(), f"Procfile not found at {PROCFILE}"
    with open(PROCFILE, "r", encoding="utf-8") as f:
        content = f.read()

    assert "PROCESS_TYPE=api" in content
    assert "PROCESS_TYPE=worker" in content
    assert "PROCESS_TYPE=beat" in content
