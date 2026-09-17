import logging
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from celery import Celery
from app.config import settings

logger = logging.getLogger(__name__)


def normalize_celery_redis_url(url: str) -> str:
    """
    Normalize Redis connection URL for Celery and redis-py.
    Ensures that TLS rediss:// connections enforce certificate verification (ssl_cert_reqs=required)
    without duplicating parameters, corrupting existing queries, or altering plain redis:// URLs.
    """
    if not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme.lower() != "rediss":
        return url

    query_params = parse_qsl(parsed.query, keep_blank_values=True)
    param_dict = dict(query_params)
    if "ssl_cert_reqs" not in param_dict:
        query_params.append(("ssl_cert_reqs", "required"))

    new_query = urlencode(query_params)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment,
    ))


def get_redis_client(url: str | None = None, socket_timeout: int = 2):
    """
    Return a configured redis-py Client with canonical URL normalization.
    Ensures rediss:// TLS settings (e.g. ssl_cert_reqs=required) are consistently applied
    across Celery, health checks, and worker heartbeat tasks without leaking credentials.
    """
    import redis
    target_url = url or settings.REDIS_URL or "redis://localhost:6379/0"
    normalized = normalize_celery_redis_url(target_url)
    return redis.from_url(normalized, socket_timeout=socket_timeout)


raw_redis_url = settings.REDIS_URL or "redis://localhost:6379/0"
redis_url = normalize_celery_redis_url(raw_redis_url)

celery_app = Celery(
    "pawsos_dispatch",
    broker=redis_url,
    backend=redis_url,
    include=[
        "app.tasks.dispatch_tasks",
        "app.tasks.notification_tasks",
        "app.tasks.ai_triage_tasks",
    ],
)

celery_app.conf.update(
    task_default_queue="default",
    task_routes={
        "app.tasks.dispatch_tasks.dispatch_case_task": {"queue": "dispatch"},
        "app.tasks.dispatch_tasks.expire_dispatch_offers_task": {"queue": "dispatch"},
        "app.tasks.dispatch_tasks.worker_heartbeat_task": {"queue": "default"},
        "app.tasks.notification_tasks.send_push_notification_task": {"queue": "notifications"},
        "app.tasks.ai_triage_tasks.perform_ai_triage_task": {"queue": "ai_triage"},
    },
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
            "options": {"queue": "dispatch"},
        },
        "worker-heartbeat": {
            "task": "app.tasks.dispatch_tasks.worker_heartbeat_task",
            "schedule": float(settings.CELERY_HEARTBEAT_INTERVAL_SECONDS),
            "options": {"queue": "default"},
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
            res = worker_heartbeat_task(is_initial=True)
            if res.get("status") == "ok":
                logger.info("Initial worker heartbeat recorded successfully on worker_ready.")
            else:
                logger.warning(
                    f"Initial worker heartbeat reporting returned error code: {res.get('error_code')}"
                )
        except Exception as err:
            logger.warning(f"Could not record initial worker heartbeat ({type(err).__name__})")
except Exception as e:
    logger.warning(f"Could not bind worker_ready signal ({type(e).__name__})")

# Test/eager mode fallback if ENVIRONMENT is test or development without active broker
if settings.ENVIRONMENT in ["test", "testing"]:
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
