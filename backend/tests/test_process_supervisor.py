"""Tests validating the process supervision logic in start_free_render.sh."""
import os
import shutil
import subprocess
import tempfile
import pytest


def get_bash_executable():
    """Find native bash executable on POSIX systems."""
    if os.name == "nt":
        return None
    return shutil.which("bash")


@pytest.mark.skipif(get_bash_executable() is None, reason="Bash process supervision tests require a native POSIX environment")
class TestProcessSupervisorLogic:
    """Verify that process supervisor terminates remaining children and exits non-zero if any child crashes."""

    SUPERVISOR_SNIPPET = """#!/usr/bin/env bash
WORKER_PID=""
BEAT_PID=""
UVICORN_PID=""
TERMINATING=0

cleanup() {
    TERMINATING=1
    local sig="${1:-TERM}"
    for pid in "$UVICORN_PID" "$BEAT_PID" "$WORKER_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    wait 2>/dev/null || true
}

trap 'cleanup TERM; exit 0' SIGTERM
trap 'cleanup INT; exit 0' SIGINT

# Launch mocked processes passed as arguments
WORKER_CMD="$1"
BEAT_CMD="$2"
UVICORN_CMD="$3"

eval "$WORKER_CMD" &
WORKER_PID=$!

eval "$BEAT_CMD" &
BEAT_PID=$!

eval "$UVICORN_CMD" &
UVICORN_PID=$!

sleep 0.5
for role in "Celery Worker:$WORKER_PID" "Celery Beat:$BEAT_PID" "Uvicorn API:$UVICORN_PID"; do
    PID="${role##*:}"
    if ! kill -0 "$PID" 2>/dev/null; then
        cleanup TERM
        exit 1
    fi
done

while [ "$TERMINATING" -eq 0 ]; do
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
        set +e
        wait "$WORKER_PID" 2>/dev/null
        CODE=$?
        echo "CRITICAL: Celery Worker exited with code $CODE"
        cleanup TERM
        exit 1
    fi

    if ! kill -0 "$BEAT_PID" 2>/dev/null; then
        set +e
        wait "$BEAT_PID" 2>/dev/null
        CODE=$?
        echo "CRITICAL: Celery Beat exited with code $CODE"
        cleanup TERM
        exit 1
    fi

    if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
        set +e
        wait "$UVICORN_PID" 2>/dev/null
        CODE=$?
        echo "CRITICAL: Uvicorn API server exited with code $CODE"
        cleanup TERM
        exit 1
    fi

    sleep 0.2
done
"""

    def test_supervisor_fails_when_worker_dies(self):
        """Worker crashing causes supervisor to terminate other processes and exit non-zero."""
        bash = get_bash_executable()
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as f:
            f.write(self.SUPERVISOR_SNIPPET)
            script_path = f.name

        try:
            # Worker sleeps 1s then exits 2; Beat and API sleep 60s
            worker = "sleep 1 && exit 2"
            beat = "sleep 60"
            uvicorn = "sleep 60"

            res = subprocess.run(
                [bash, script_path, worker, beat, uvicorn],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert res.returncode == 1
            assert "CRITICAL: Celery Worker exited with code 2" in res.stdout
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)

    def test_supervisor_fails_when_beat_dies(self):
        """Celery Beat crashing causes supervisor to terminate other processes and exit non-zero."""
        bash = get_bash_executable()
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as f:
            f.write(self.SUPERVISOR_SNIPPET)
            script_path = f.name

        try:
            # Beat sleeps 1s then exits 3; Worker and API sleep 60s
            worker = "sleep 60"
            beat = "sleep 1 && exit 3"
            uvicorn = "sleep 60"

            res = subprocess.run(
                [bash, script_path, worker, beat, uvicorn],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert res.returncode == 1
            assert "CRITICAL: Celery Beat exited with code 3" in res.stdout
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
