import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status, Response
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
def health_liveness():
    """Basic liveness probe verifying the API process is alive and responsive with build metadata."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "2.0.0",
        "git_sha": settings.GIT_SHA,
    }

@router.get("/health/ready")
@router.get("/health/readiness")
def health_readiness(response: Response, db: Session = Depends(get_db)):
    """Readiness probe checking critical downstream dependencies: Database, PostGIS, Redis, Worker, Storage, Firebase."""
    require_full = (
        settings.ENVIRONMENT in ["production", "staging"]
        or os.getenv("REQUIRE_FULL_READINESS", "").lower() == "true"
    )
    checks = {
        "database": "unknown",
        "postgis": "unknown",
        "redis": "skipped",
        "worker": "skipped",
        "storage": "unknown",
        "firebase": "unconfigured",
    }
    healthy = True

    # 1. Database check & PostGIS verification
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "connected"

        dialect_name = db.bind.dialect.name if db.bind else "sqlite"
        if dialect_name == "postgresql":
            try:
                db.execute(text("SELECT PostGIS_Version();"))
                checks["postgis"] = "available"
            except Exception as e:
                logger.error(f"PostGIS check failed on PostgreSQL: {e}")
                checks["postgis"] = "unavailable"
                if require_full:
                    healthy = False
        else:
            checks["postgis"] = "simulated"
    except Exception as e:
        logger.error(f"Health check failed on database: {e}")
        checks["database"] = "disconnected"
        healthy = False

    # 2. Redis and Worker Heartbeat check (fail-closed)
    if settings.REDIS_URL:
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            checks["redis"] = "connected"

            heartbeat = r.get("celery_worker_heartbeat")
            if heartbeat is not None:
                try:
                    hb_str = heartbeat.decode("utf-8") if isinstance(heartbeat, bytes) else str(heartbeat)
                    hb_time = datetime.fromisoformat(hb_str)
                    if hb_time.tzinfo is None:
                        hb_time = hb_time.replace(tzinfo=timezone.utc)
                    now_utc = datetime.now(timezone.utc)
                    age_sec = (now_utc - hb_time).total_seconds()
                    if age_sec < 0:
                        age_sec = 0.0

                    if age_sec <= settings.CELERY_HEARTBEAT_THRESHOLD_SECONDS:
                        checks["worker"] = "active"
                    else:
                        checks["worker"] = "stale"
                        logger.warning(
                            f"Celery worker heartbeat is stale: age {age_sec:.1f}s exceeds "
                            f"threshold {settings.CELERY_HEARTBEAT_THRESHOLD_SECONDS}s"
                        )
                        if require_full:
                            healthy = False
                except Exception as parse_err:
                    logger.warning(f"Invalid Celery worker heartbeat content in Redis: {parse_err}")
                    checks["worker"] = "invalid_heartbeat"
                    if require_full:
                        healthy = False
            else:
                checks["worker"] = "missing"
                logger.warning("Celery worker heartbeat key is missing in Redis")
                if require_full:
                    healthy = False
        except Exception as e:
            logger.warning(f"Health check warning on Redis/Worker: {e}")
            checks["redis"] = "disconnected"
            checks["worker"] = "unavailable"
            if require_full:
                healthy = False
    else:
        if require_full:
            checks["redis"] = "unconfigured"
            checks["worker"] = "unavailable"
            healthy = False

    # 3. Storage Provider check
    try:
        from app.services.storage_service import storage_service
        is_storage_ok = storage_service.check_health()
        checks["storage"] = "healthy" if is_storage_ok else "unhealthy"
        if not is_storage_ok and require_full:
            healthy = False
    except Exception as e:
        logger.warning(f"Storage readiness check warning: {e}")
        checks["storage"] = "unhealthy"
        if require_full:
            healthy = False

    # 4. Firebase Cloud Messaging configuration check (environment-aware)
    try:
        from app.services.notification_service import _firebase_initialized
        if _firebase_initialized:
            checks["firebase"] = "healthy"
        else:
            if settings.REQUIRE_FIREBASE:
                checks["firebase"] = "unavailable"
                healthy = False
            else:
                checks["firebase"] = "unconfigured"
    except Exception:
        if settings.REQUIRE_FIREBASE:
            checks["firebase"] = "unavailable"
            healthy = False
        else:
            checks["firebase"] = "unconfigured"


    # Map to standardized operational status strings
    if checks["worker"] == "active":
        celery_status = "healthy"
    elif checks["worker"] == "stale":
        celery_status = "degraded"
    else:
        celery_status = "unavailable"

    services = {
        "database": "healthy" if checks["database"] == "connected" else "unavailable",
        "postgis": "healthy" if checks["postgis"] in ["available", "simulated"] else "unavailable",
        "redis": "healthy" if checks["redis"] == "connected" else "unavailable",
        "celery": celery_status,
        "storage": checks["storage"] if checks["storage"] == "healthy" else "unavailable",
        "firebase": checks["firebase"],
    }

    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    overall_status = "ready" if healthy else "degraded"
    if checks["database"] == "disconnected":
        overall_status = "offline"

    return {
        "status": overall_status,
        "environment": settings.ENVIRONMENT,
        "services": services,
        "checks": checks,
    }
