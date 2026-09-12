import pytest
from app.services.notification_service import NotificationService
from app.models.device_token import DeviceToken

def test_device_token_registration_and_deactivation(client, citizen_token, citizen_user, db):
    """Test registering and deactivating push device tokens."""
    # Register device token
    headers = {"Authorization": f"Bearer {citizen_token}"}
    reg_res = client.post(
        "/api/v1/notifications/devices",
        json={"token": "test_fcm_token_12345", "platform": "WEB", "device_name": "Chrome on MacOS"},
        headers=headers
    )
    assert reg_res.status_code == 200
    data = reg_res.json()
    assert data["token"] == "test_fcm_token_12345"
    assert data["is_active"] is True

    # Check database record
    dt = db.query(DeviceToken).filter(DeviceToken.token == "test_fcm_token_12345").first()
    assert dt is not None
    assert dt.user_id == citizen_user.id

    # Unregister / deactivate token
    del_res = client.delete("/api/v1/notifications/devices/test_fcm_token_12345", headers=headers)
    assert del_res.status_code == 200
    db.refresh(dt)
    assert dt.is_active is False

def test_in_app_notification_lifecycle(client, citizen_token, citizen_user, db):
    """Test notification list, unread count, single read, and mark all read."""
    headers = {"Authorization": f"Bearer {citizen_token}"}

    # Generate 2 test notifications
    NotificationService.notify_user(
        db=db,
        user_id=citizen_user.id,
        title="Test Alert 1",
        message="Message 1",
        notification_type="TEST_EVENT"
    )
    NotificationService.notify_user(
        db=db,
        user_id=citizen_user.id,
        title="Test Alert 2",
        message="Message 2",
        notification_type="TEST_EVENT"
    )

    # Fetch notifications
    list_res = client.get("/api/v1/notifications", headers=headers)
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["unread_count"] >= 2
    items = list_data["items"]
    assert len(items) >= 2
    first_id = items[0]["id"]

    # Mark first read
    read_res = client.patch(f"/api/v1/notifications/{first_id}/read", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True

    # Mark all read
    read_all_res = client.patch("/api/v1/notifications/read-all", headers=headers)
    assert read_all_res.status_code == 200

    # Verify unread count is 0
    final_res = client.get("/api/v1/notifications", headers=headers)
    assert final_res.json()["unread_count"] == 0
