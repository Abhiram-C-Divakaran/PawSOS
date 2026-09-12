import os
from datetime import datetime
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
    """Basic liveness probe verifying the API process is alive and responsive."""
    return {
        "status": "ok",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }

@router.get("/health/ready")
@router.get("/health/readiness")
def health_readiness(response: Response, db: Session = Depends(get_db)):
    """Readiness probe checking critical downstream dependencies: Database, PostGIS, Redis, Worker, Storage, Firebase."""
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
                if settings.ENVIRONMENT in ["production", "staging"]:
                    healthy = False
        else:
            checks["postgis"] = "simulated"
    except Exception as e:
        logger.error(f"Health check failed on database: {e}")
        checks["database"] = "disconnected"
        healthy = False

    # 2. Redis and Worker Heartbeat check
    if settings.REDIS_URL:
        try:
            import redis
            r = redis.from_url(settings.REDIS_URL, socket_timeout=2)
            r.ping()
            checks["redis"] = "connected"

            heartbeat = r.get("celery_worker_heartbeat")
            if heartbeat:
                try:
                    hb_str = heartbeat.decode("utf-8") if isinstance(heartbeat, bytes) else str(heartbeat)
                    hb_time = datetime.fromisoformat(hb_str)
                    age_sec = (datetime.utcnow() - hb_time).total_seconds()
                    if age_sec <= settings.CELERY_HEARTBEAT_THRESHOLD_SECONDS:
                        checks["worker"] = "active"
                    else:
                        checks["worker"] = "stale"
                        if settings.ENVIRONMENT in ["production", "staging"] or os.getenv("REQUIRE_FULL_READINESS", "").lower() == "true":
                            healthy = False
                except Exception:
                    checks["worker"] = "active"
            else:
                checks["worker"] = "no_heartbeat"
                if settings.ENVIRONMENT in ["production", "staging"] or os.getenv("REQUIRE_FULL_READINESS", "").lower() == "true":
                    checks["worker"] = "degraded"
                    healthy = False
        except Exception as e:
            logger.warning(f"Health check warning on Redis/Worker: {e}")
            checks["redis"] = "disconnected"
            checks["worker"] = "unavailable"
            if settings.ENVIRONMENT in ["production", "staging"] or os.getenv("REQUIRE_FULL_READINESS", "").lower() == "true":
                healthy = False

    # 3. Storage Provider check
    try:
        from app.services.storage_service import storage_service
        is_storage_ok = storage_service.check_health()
        checks["storage"] = "healthy" if is_storage_ok else "unhealthy"
        if not is_storage_ok and settings.ENVIRONMENT in ["production", "staging"]:
            healthy = False
    except Exception as e:
        logger.warning(f"Storage readiness check warning: {e}")
        checks["storage"] = "unhealthy"
        if settings.ENVIRONMENT in ["production", "staging"]:
            healthy = False

    # 4. Firebase Cloud Messaging configuration check
    try:
        from app.services.notification_service import _firebase_initialized
        checks["firebase"] = "healthy" if _firebase_initialized else "unconfigured"
    except Exception:
        checks["firebase"] = "unconfigured"

    # Map to standardized operational status strings
    celery_status = (
        "healthy" if checks["worker"] == "active"
        else ("degraded" if checks["worker"] in ["stale", "no_heartbeat"] else "unavailable")
    )

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
