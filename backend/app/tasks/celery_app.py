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
        "expire-dispatch-offers-every-20s": {
            "task": "app.tasks.dispatch_tasks.expire_dispatch_offers_task",
            "schedule": 20.0,
        },
        "worker-heartbeat-every-10s": {
            "task": "app.tasks.dispatch_tasks.worker_heartbeat_task",
            "schedule": 10.0,
        },
    },
)

# Test/eager mode fallback if ENVIRONMENT is test or development without active broker
if settings.ENVIRONMENT in ["test", "testing"]:
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
