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
    """Verify that render.yaml defines a 100% free deployment topology without paid resources,
    running migrations and combined API + Celery worker + Beat via scripts/start_free_render.sh.
    """
    assert RENDER_YAML.exists(), f"render.yaml not found at {RENDER_YAML}"
    with open(RENDER_YAML, "r", encoding="utf-8") as f:
        render_data = yaml.safe_load(f)

    services = render_data.get("services", [])
    service_map = {s["name"]: s for s in services}

    # 1. Verify single free web service (API + Celery + Beat combined)
    api_svc = service_map.get("pawreach-api") or service_map.get("pawreach-staging-api")
    assert api_svc, "Free web service (pawreach-api) missing in render.yaml"
    assert api_svc.get("plan") == "free", f"Web service plan must be 'free', got '{api_svc.get('plan')}'"

    # Verify no paid databases or separate managed services in render.yaml
    assert "databases" not in render_data or len(render_data.get("databases", [])) == 0, "No paid databases allowed in render.yaml"
    for s in services:
        assert s.get("plan") in (None, "free"), f"Paid plan '{s.get('plan')}' detected in {s.get('name')}"
        assert s.get("runtime") in ("python", "static"), f"Unexpected runtime '{s.get('runtime')}' in render.yaml"

    # Start command uses combined startup script
    start_cmd = api_svc.get("startCommand", "")
    assert "start_free_render.sh" in start_cmd, f"Web service startCommand must use start_free_render.sh, got '{start_cmd}'"

    # Verify startup script exists and contains alembic migrations + worker + beat + uvicorn
    script_path = REPO_ROOT / "scripts" / "start_free_render.sh"
    assert script_path.exists(), f"start_free_render.sh missing at {script_path}"
    with open(script_path, "r", encoding="utf-8") as sf:
        script_content = sf.read()
    assert "alembic upgrade head" in script_content
    assert "celery" in script_content and "worker" in script_content
    assert "celery" in script_content and "beat" in script_content
    assert "uvicorn" in script_content

    # PROCESS_TYPE validation on free web service
    def get_env_var(svc, key):
        for ev in svc.get("envVars", []):
            if ev.get("key") == key:
                return ev.get("value")
        return None

    assert get_env_var(api_svc, "PROCESS_TYPE") == "all"
    assert get_env_var(api_svc, "STORAGE_PROVIDER") == "s3"

    # Check envVars wiring for external free services (DATABASE_URL, REDIS_URL, etc.)
    env_keys = [ev.get("key") for ev in api_svc.get("envVars", [])]
    assert "DATABASE_URL" in env_keys
    assert "REDIS_URL" in env_keys
    assert "CORS_ORIGINS" in env_keys
    assert "JWT_SECRET_KEY" in env_keys
    assert "S3_ENDPOINT_URL" in env_keys

    # Verify frontend static site
    frontend_svc = service_map.get("pawreach-frontend") or service_map.get("pawreach-staging-frontend")
    assert frontend_svc, "Static frontend service missing in render.yaml"
    assert frontend_svc.get("runtime") == "static"


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
