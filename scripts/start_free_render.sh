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

# Cleanup function to terminate all child processes cleanly on container stop
cleanup() {
    echo "[start_free_render] Received shutdown signal. Terminating child processes..."
    if [ -n "$UVICORN_PID" ] && kill -0 "$UVICORN_PID" 2>/dev/null; then
        kill -TERM "$UVICORN_PID" 2>/dev/null || true
    fi
    if [ -n "$WORKER_PID" ] && kill -0 "$WORKER_PID" 2>/dev/null; then
        kill -TERM "$WORKER_PID" 2>/dev/null || true
    fi
    if [ -n "$BEAT_PID" ] && kill -0 "$BEAT_PID" 2>/dev/null; then
        kill -TERM "$BEAT_PID" 2>/dev/null || true
    fi
    wait 2>/dev/null || true
    echo "[start_free_render] All processes stopped cleanly."
}

trap cleanup SIGTERM SIGINT EXIT

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

# 4. Start Uvicorn API server in foreground
echo "[start_free_render] Starting Uvicorn API server on 0.0.0.0:${PORT:-8000}..."
uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 1 &
UVICORN_PID=$!

# Wait for Uvicorn process; if Uvicorn exits or a signal is caught, trap triggers cleanup
wait "$UVICORN_PID"
