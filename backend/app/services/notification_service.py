import json
import logging
import os
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.models.notification import Notification
from app.models.device_token import DeviceToken
from app.models.user import User

logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except ImportError:
    firebase_admin = None
    credentials = None
    messaging = None

# Firebase App Initialization (graceful fallback if credentials not found)
_firebase_initialized = False

def initialize_firebase_admin() -> bool:
    global _firebase_initialized
    if firebase_admin is None or credentials is None:
        _firebase_initialized = False
        return False
    try:
        # If already initialized in this process
        if firebase_admin._apps:
            _firebase_initialized = True
            return True

        cred_json = settings.FIREBASE_CREDENTIALS_JSON
        cred_path = settings.FIREBASE_CREDENTIALS_PATH

        # Precedence: FIREBASE_CREDENTIALS_JSON takes precedence over file path
        if cred_json and cred_json.strip():
            try:
                parsed = json.loads(cred_json)
                if not isinstance(parsed, dict):
                    raise ValueError("Firebase credentials JSON must parse to an object/dict")
                cred = credentials.Certificate(parsed)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info("Firebase Admin SDK initialized successfully from secure JSON secret.")
                return True
            except Exception as ex:
                logger.error(f"Failed to initialize Firebase Admin SDK from FIREBASE_CREDENTIALS_JSON: {type(ex).__name__}")
                _firebase_initialized = False
                return False
        elif cred_path and cred_path.strip() and os.path.exists(cred_path):
            try:
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                _firebase_initialized = True
                logger.info(f"Firebase Admin SDK initialized successfully with credentials file at: {cred_path}")
                return True
            except Exception as ex:
                logger.error(f"Failed to initialize Firebase Admin SDK from file path {cred_path}: {type(ex).__name__}")
                _firebase_initialized = False
                return False
        else:
            _firebase_initialized = False
            if settings.REQUIRE_FIREBASE:
                logger.error("REQUIRE_FIREBASE is enabled but Firebase credentials are not configured.")
            else:
                if settings.ENVIRONMENT in ["production", "staging"]:
                    logger.info("Firebase credentials not configured in staging/production. Web push is unconfigured.")
                else:
                    logger.info("Firebase credentials not configured. Operating in push-fallback mock mode.")
            return False
    except Exception as e:
        logger.warning(f"Could not load or initialize Firebase Admin SDK: {e}")
        _firebase_initialized = False
        return False

# Initialize at module load
initialize_firebase_admin()



class NotificationService:
    @staticmethod
    def _send_fcm(db: Session, user_id: uuid.UUID, title: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Send push notification to all active devices registered for user."""
        active_tokens = (
            db.query(DeviceToken)
            .filter(DeviceToken.user_id == user_id, DeviceToken.is_active == True)
            .all()
        )
        if not active_tokens:
            return

        payload_data = {}
        if data:
            for k, v in data.items():
                payload_data[str(k)] = str(v)

        if not _firebase_initialized:
            logger.info(
                f"[FCM MOCK PUSH] -> User {user_id} ({len(active_tokens)} devices) | Title: '{title}' | Body: '{message}' | Payload: {payload_data}"
            )
            return

        try:
            for device in active_tokens:
                try:
                    fcm_msg = messaging.Message(
                        notification=messaging.Notification(title=title, body=message),
                        data=payload_data,
                        token=device.token,
                    )
                    messaging.send(fcm_msg)
                    device.last_seen_at = datetime.now(timezone.utc)
                except messaging.UnregisteredError:
                    logger.warning(f"FCM token {device.token[:12]}... is unregistered. Deactivating device.")
                    device.is_active = False
                except messaging.SenderIdMismatchError:
                    logger.warning(f"FCM sender mismatch for token {device.token[:12]}... Deactivating.")
                    device.is_active = False
                except Exception as ex:
                    logger.error(f"FCM delivery error for device {device.id}: {ex}")
            db.commit()
        except Exception as e:
            logger.error(f"Error during FCM push distribution: {e}")

    @classmethod
    def notify_user(
        cls,
        db: Session,
        user_id: uuid.UUID,
        title: str,
        message: str,
        notification_type: str,
        rescue_case_id: Optional[uuid.UUID] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        """Create in-app notification record and send push notification to user's registered devices."""
        data_json = json.dumps(data) if data else None

        notif = Notification(
            user_id=user_id,
            type=notification_type,
            title=title,
            message=message,
            rescue_case_id=rescue_case_id,
            data=data_json,
            is_read=False,
            created_at=datetime.now(timezone.utc)
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)

        # Trigger FCM push
        cls._send_fcm(db, user_id=user_id, title=title, message=message, data=data)
        return notif

    @classmethod
    def notify_users(
        cls,
        db: Session,
        user_ids: List[uuid.UUID],
        title: str,
        message: str,
        notification_type: str,
        rescue_case_id: Optional[uuid.UUID] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> List[Notification]:
        """Bulk notify multiple users with the same event."""
        created = []
        for uid in user_ids:
            notif = cls.notify_user(
                db=db,
                user_id=uid,
                title=title,
                message=message,
                notification_type=notification_type,
                rescue_case_id=rescue_case_id,
                data=data,
            )
            created.append(notif)
        return created

    @classmethod
    def notify_rescue_participants(
        cls,
        db: Session,
        rescue_case_id: uuid.UUID,
        event_type: str,
        title: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Notify all relevant participants of a case (reporter, assigned responder, facility staff).
        """
        from app.models.rescue_case import RescueCase
        from app.models.rescue_assignment import RescueAssignment
        from app.core.constants import AssignmentStatus

        case = db.query(RescueCase).filter(RescueCase.id == rescue_case_id).first()
        if not case:
            return

        payload = {
            "type": event_type,
            "case_id": str(case.id),
            "case_number": case.case_number,
            "route": f"/cases/{case.id}",
        }
        if extra_data:
            payload.update(extra_data)

        # 1. Notify citizen reporter
        if case.reporter_id:
            cls.notify_user(
                db=db,
                user_id=case.reporter_id,
                title=title,
                message=message,
                notification_type=event_type,
                rescue_case_id=case.id,
                data=payload,
            )

        # 2. Notify assigned responder
        assignment = (
            db.query(RescueAssignment)
            .filter(
                RescueAssignment.rescue_case_id == case.id,
                RescueAssignment.assignment_status == AssignmentStatus.ACCEPTED,
            )
            .first()
        )
        if assignment and assignment.rescuer_id and assignment.rescuer_id != case.reporter_id:
            cls.notify_user(
                db=db,
                user_id=assignment.rescuer_id,
                title=title,
                message=message,
                notification_type=event_type,
                rescue_case_id=case.id,
                data=payload,
            )

    @classmethod
    def notify_organization(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        title: str,
        message: str,
        notification_type: str,
        rescue_case_id: Optional[uuid.UUID] = None,
        data: Optional[Dict[str, Any]] = None,
    ):
        """Notify all NGO/Org admins of an organization."""
        from app.core.constants import UserRole

        admins = (
            db.query(User)
            .filter(
                User.organization_id == organization_id,
                User.role.in_([UserRole.NGO_ADMIN, UserRole.SUPER_ADMIN]),
                User.is_active == True,
            )
            .all()
        )
        admin_ids = [u.id for u in admins]
        if admin_ids:
            cls.notify_users(
                db=db,
                user_ids=admin_ids,
                title=title,
                message=message,
                notification_type=notification_type,
                rescue_case_id=rescue_case_id,
                data=data,
            )

    @classmethod
    def get_critical_alert_recipients(
        cls,
        db: Session,
        organization_id: Optional[uuid.UUID] = None,
    ) -> List[User]:
        """Resolve authorized recipients for critical rescue alerts.
        
        Policy:
        - SUPER_ADMIN: global (always selected if active).
        - NGO_ADMIN: strictly scoped to case.organization_id (only if active and organization_id is non-null).
        - If organization_id is None, no NGO_ADMINs are selected (fail-closed tenant policy).
        - Inactive users are excluded.
        """
        from app.core.constants import UserRole

        # 1. Global Super Admins
        super_admins = (
            db.query(User)
            .filter(
                User.role == UserRole.SUPER_ADMIN,
                User.is_active == True,
            )
            .all()
        )

        # 2. Scoped NGO Admins for this specific organization
        ngo_admins: List[User] = []
        if organization_id is not None:
            ngo_admins = (
                db.query(User)
                .filter(
                    User.role == UserRole.NGO_ADMIN,
                    User.organization_id == organization_id,
                    User.is_active == True,
                )
                .all()
            )

        seen_ids = set()
        recipients = []
        for user in super_admins + ngo_admins:
            if user.id not in seen_ids:
                seen_ids.add(user.id)
                recipients.append(user)

        return recipients

