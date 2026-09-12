import logging
import uuid
from typing import Any, Dict, Optional
from app.tasks.celery_app import celery_app
from app.database import SessionLocal
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.notification_tasks.send_push_notification_task")
def send_push_notification_task(
    user_id: str,
    title: str,
    message: str,
    notification_type: str,
    rescue_case_id: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
) -> dict:
    """Background worker task to distribute push and in-app notifications asynchronously."""
    db = SessionLocal()
    try:
        case_uuid = uuid.UUID(rescue_case_id) if rescue_case_id else None
        notif = NotificationService.notify_user(
            db=db,
            user_id=uuid.UUID(user_id),
            title=title,
            message=message,
            notification_type=notification_type,
            rescue_case_id=case_uuid,
            data=data,
        )
        return {"status": "sent", "notification_id": str(notif.id)}
    except Exception as e:
        logger.error(f"Error in send_push_notification_task for user {user_id}: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}
    finally:
        db.close()
