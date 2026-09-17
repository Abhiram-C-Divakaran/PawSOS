#!/usr/bin/env bash
set -e

echo "[start_free_render] Starting PawReach combined free-tier deployment container..."
export PROCESS_TYPE="${PROCESS_TYPE:-all}"

# Move to backend directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR/backend"

# Ensure stale Celery beat pidfile is cleaned up
rm -f /tmp/celerybeat.pid

WORKER_PID=""
BEAT_PID=""
UVICORN_PID=""
TERMINATING=0

# Cleanup function to terminate all child processes cleanly on container stop or failure
cleanup() {
    TERMINATING=1
    local sig="${1:-TERM}"
    echo "[start_free_render] Received shutdown or cleanup signal ($sig). Terminating child processes..."
    
    for pid in "$UVICORN_PID" "$BEAT_PID" "$WORKER_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done
    
    # Grace period for processes to exit cleanly
    local grace=5
    while [ "$grace" -gt 0 ]; do
        local any_alive=0
        for pid in "$UVICORN_PID" "$BEAT_PID" "$WORKER_PID"; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                any_alive=1
                break
            fi
        done
        if [ "$any_alive" -eq 0 ]; then
            break
        fi
        sleep 1
        grace=$((grace - 1))
    done
    
    # Force kill any remaining stubborn processes
    for pid in "$UVICORN_PID" "$BEAT_PID" "$WORKER_PID"; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo "[start_free_render] Forcefully killing PID $pid..."
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done

    wait "$WORKER_PID" 2>/dev/null || true
    wait "$BEAT_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
    echo "[start_free_render] All child processes stopped cleanly."
}

trap 'cleanup TERM; exit 0' SIGTERM
trap 'cleanup INT; exit 0' SIGINT

# 1. Run database migrations
echo "[start_free_render] Applying database migrations with Alembic..."
alembic upgrade head

# 2. Start lightweight Celery worker
echo "[start_free_render] Starting lightweight Celery worker (solo pool, concurrency 1)..."
celery -A app.tasks.celery_app.celery_app worker \
  --loglevel=INFO \
  --concurrency=1 \
  --pool=solo \
  -Q dispatch,notifications,ai_triage,default &
WORKER_PID=$!

# 3. Start Celery Beat scheduler
echo "[start_free_render] Starting Celery Beat periodic scheduler..."
celery -A app.tasks.celery_app.celery_app beat \
  --loglevel=INFO \
  --pidfile=/tmp/celerybeat.pid &
BEAT_PID=$!

# 4. Start Uvicorn API server
echo "[start_free_render] Starting Uvicorn API server on 0.0.0.0:${PORT:-8000}..."
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1 &
UVICORN_PID=$!

# 5. Short bounded startup verification
echo "[start_free_render] Verifying process startup..."
sleep 2
for role in "Celery Worker:$WORKER_PID" "Celery Beat:$BEAT_PID" "Uvicorn API:$UVICORN_PID"; do
    NAME="${role%%:*}"
    PID="${role##*:}"
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "[start_free_render] CRITICAL: $NAME process (PID $PID) failed during startup!"
        cleanup TERM
        exit 1
    fi
    echo "[start_free_render] $NAME is running (PID: $PID)."
done

# 6. Active process supervision loop
echo "[start_free_render] All processes verified healthy. Entering process supervisor loop..."
while [ "${TERMINATING:-0}" -eq 0 ]; do
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
        set +e
        wait "$WORKER_PID" 2>/dev/null
        CODE=$?
        set -e
        echo "[start_free_render] CRITICAL: Celery Worker (PID $WORKER_PID) exited unexpectedly with code $CODE!"
        cleanup TERM
        exit 1
    fi

    if ! kill -0 "$BEAT_PID" 2>/dev/null; then
        set +e
        wait "$BEAT_PID" 2>/dev/null
        CODE=$?
        set -e
        echo "[start_free_render] CRITICAL: Celery Beat (PID $BEAT_PID) exited unexpectedly with code $CODE!"
        cleanup TERM
        exit 1
    fi

    if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
        set +e
        wait "$UVICORN_PID" 2>/dev/null
        CODE=$?
        set -e
        echo "[start_free_render] CRITICAL: Uvicorn API server (PID $UVICORN_PID) exited with code $CODE."
        cleanup TERM
        exit 1
    fi

    sleep 2
done
