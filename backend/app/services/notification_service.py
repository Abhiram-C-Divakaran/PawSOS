import logging
import uuid

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    def send_push_notification(user_id: uuid.UUID, title: str, message: str, payload: dict = None):
        """
        Abstraction for Firebase Cloud Messaging (FCM).
        Currently mocks the "sent" notification via console logger as per MVP instructions.
        """
        logger.info(f"FCM PUSH -> User {user_id}: {title} | {message} | {payload}")
        # In the future, integrate firebase_admin.messaging here
        return True
