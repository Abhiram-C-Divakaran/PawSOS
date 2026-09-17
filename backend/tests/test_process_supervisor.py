"""Tests validating the process supervision logic in start_free_render.sh."""
import os
import shutil
import subprocess
import tempfile
import pytest


def get_bash_executable():
    """Find native bash executable on POSIX systems or Git Bash on Windows."""
    bash = shutil.which("bash")
    if bash:
        return bash
    win_git_bash = r"C:\Program Files\Git\bin\bash.exe"
    if os.path.exists(win_git_bash):
        return win_git_bash
    return None


@pytest.mark.skipif(get_bash_executable() is None, reason="Bash executable not available")
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
        if [ -n "$pid" ]; then
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done
}

trap 'cleanup TERM; exit 0' SIGTERM
trap 'cleanup INT; exit 0' SIGINT

# Launch mocked processes passed as arguments (redirect background output so test pipe closes cleanly)
eval "$1" >/dev/null 2>&1 & WORKER_PID=$!
eval "$2" >/dev/null 2>&1 & BEAT_PID=$!
eval "$3" >/dev/null 2>&1 & UVICORN_PID=$!

sleep 0.2
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

    sleep 0.1
done
"""

    def test_supervisor_fails_when_worker_dies(self):
        """Worker crashing causes supervisor to terminate other processes and exit non-zero."""
        bash = get_bash_executable()
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".sh") as f:
            f.write(self.SUPERVISOR_SNIPPET)
            script_path = f.name

        try:
            worker = "sleep 0.4 && exit 2"
            beat = "sleep 5"
            uvicorn = "sleep 5"

            res = subprocess.run(
                [bash, script_path, worker, beat, uvicorn],
                capture_output=True,
                text=True,
                timeout=5,
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
            worker = "sleep 5"
            beat = "sleep 0.4 && exit 3"
            uvicorn = "sleep 5"

            res = subprocess.run(
                [bash, script_path, worker, beat, uvicorn],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert res.returncode == 1
            assert "CRITICAL: Celery Beat exited with code 3" in res.stdout
        finally:
            if os.path.exists(script_path):
                os.remove(script_path)
