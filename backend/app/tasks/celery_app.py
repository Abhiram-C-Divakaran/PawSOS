import logging
from celery import Celery
from app.config import settings

logger = logging.getLogger(__name__)

redis_url = settings.REDIS_URL or "redis://localhost:6379/0"

celery_app = Celery(
    "pawsos_dispatch",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.dispatch_tasks",
        "app.tasks.notification_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Periodic Celery Beat Schedule
    beat_schedule={
        "expire-dispatch-offers": {
            "task": "app.tasks.dispatch_tasks.expire_dispatch_offers_task",
            "schedule": float(settings.DISPATCH_BEAT_INTERVAL_SECONDS),
        },
        "worker-heartbeat": {
            "task": "app.tasks.dispatch_tasks.worker_heartbeat_task",
            "schedule": float(settings.CELERY_HEARTBEAT_INTERVAL_SECONDS),
        },
    },
)

try:
    from celery.signals import worker_ready

    @worker_ready.connect
    def on_worker_ready(sender=None, **kwargs):
        logger.info("Celery worker ready, publishing initial heartbeat.")
        try:
            from app.tasks.dispatch_tasks import worker_heartbeat_task
            worker_heartbeat_task()
        except Exception as err:
            logger.warning(f"Could not record initial worker heartbeat: {err}")
except Exception as e:
    logger.warning(f"Could not bind worker_ready signal: {e}")

# Test/eager mode fallback if ENVIRONMENT is test or development without active broker
if settings.ENVIRONMENT in ["test", "testing"]:
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
