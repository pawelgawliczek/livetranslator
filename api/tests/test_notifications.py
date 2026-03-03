"""
Tests for Notification Management System (US-008)
Covers admin and user notification endpoints
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from passlib.hash import bcrypt_sha256 as bcrypt
from jose import jwt

from ..main import app
from ..models import Base, User, Notification, NotificationDelivery
from ..jwt_tools import JWT_SECRET, ALGO


# Test database setup
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def setup_database():
    """Create and drop test database for each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(setup_database):
    """Create test client."""
    from ..auth import get_db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def db_session(setup_database):
    """Get database session for test."""
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def admin_user(setup_database):
    """Create a test admin user."""
    db = TestingSessionLocal()
    user = User(
        email="admin@example.com",
        password_hash=bcrypt.hash("adminpass123"),
        display_name="Admin User",
        preferred_lang="en",
        is_admin=True,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_data = type('UserData', (), {
        'id': user.id,
        'email': user.email,
        'display_name': user.display_name,
        'preferred_lang': user.preferred_lang,
        'is_admin': user.is_admin
    })()

    db.close()
    return user_data


@pytest.fixture
def test_user(setup_database):
    """Create a test regular user."""
    db = TestingSessionLocal()
    user = User(
        email="user@example.com",
        password_hash=bcrypt.hash("userpass123"),
        display_name="Test User",
        preferred_lang="en",
        is_admin=False,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    user_data = type('UserData', (), {
        'id': user.id,
        'email': user.email,
        'display_name': user.display_name,
        'preferred_lang': user.preferred_lang,
        'is_admin': user.is_admin
    })()

    db.close()
    return user_data


@pytest.fixture
def test_users(setup_database):
    """Create multiple test users."""
    db = TestingSessionLocal()

    users = []
    for i, name in enumerate(["alpha", "beta", "gamma"]):
        user = User(
            email=f"{name}{i}@example.com",
            password_hash=bcrypt.hash("pass123"),
            display_name=f"{name.title()} User {i}",
            preferred_lang="en",
            is_admin=False,
            created_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        users.append(user)

    db.close()
    return users


@pytest.fixture
def admin_token(admin_user):
    """Create authentication token for admin user."""
    token = jwt.encode(
        {"email": admin_user.email, "sub": str(admin_user.id)},
        JWT_SECRET,
        algorithm=ALGO
    )
    return token


@pytest.fixture
def user_token(test_user):
    """Create authentication token for regular user."""
    token = jwt.encode(
        {"email": test_user.email, "sub": str(test_user.id)},
        JWT_SECRET,
        algorithm=ALGO
    )
    return token


class TestNotificationCreation:
    """Test notification creation (admin endpoints)"""

    def test_create_immediate_notification_all_users(self, client, admin_token, db_session):
        """TC-001: Create immediate notification for all users"""
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "System Announcement",
                "message": "Welcome to LiveTranslator!",
                "type": "info",
                "target": "all",
                "schedule_type": "immediate",
                "is_dismissible": True
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "notification_id" in data
        assert data["status"] == "sent"
        assert data["target_user_count"] >= 1

        # Verify in database
        notification = db_session.get(Notification, data["notification_id"])
        assert notification is not None
        assert notification.title == "System Announcement"
        assert notification.status == "sent"
        assert notification.sent_at is not None

    def test_create_scheduled_notification(self, client, admin_token, db_session):
        """TC-002: Create scheduled notification"""
        scheduled_time = datetime.utcnow() + timedelta(hours=1)

        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Maintenance Notice",
                "message": "System maintenance in 1 hour",
                "type": "warning",
                "target": "all",
                "schedule_type": "scheduled",
                "scheduled_for": scheduled_time.isoformat(),
                "expires_in_seconds": 3600
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "scheduled"

        # Verify notification is NOT sent yet
        notification = db_session.get(Notification, data["notification_id"])
        assert notification.status == "scheduled"
        assert notification.sent_at is None

    def test_create_notification_all_targeting(self, client, admin_token, db_session, test_users):
        """TC-003: Target notification to all users"""
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Feature Update",
                "message": "New feature available!",
                "type": "success",
                "target": "all",
                "schedule_type": "immediate"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["target_user_count"] >= len(test_users)

    def test_create_notification_individual_targeting(self, client, admin_token, db_session, test_user):
        """TC-009: Individual user targeting"""
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Personal Message",
                "message": "This is just for you!",
                "type": "info",
                "target": "individual",
                "target_user_id": test_user.id,
                "schedule_type": "immediate"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["target_user_count"] == 1

        # Verify only target user received notification
        deliveries = db_session.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.notification_id == data["notification_id"]
            )
        ).all()
        assert len(deliveries) == 1
        assert deliveries[0].user_id == test_user.id

    def test_create_notification_validation_errors(self, client, admin_token):
        """Test validation errors"""

        # Missing title
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 422

        # Title too long
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "x" * 101,
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 422

        # Message too long
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Test",
                "message": "x" * 501,
                "type": "info",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 422

        # Invalid type
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Test",
                "message": "Test",
                "type": "invalid",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 422

        # Scheduled without scheduled_for
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Test",
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "scheduled"
            }
        )
        assert response.status_code == 422

        # Scheduled_for in past
        past_time = datetime.utcnow() - timedelta(hours=1)
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Test",
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "scheduled",
                "scheduled_for": past_time.isoformat()
            }
        )
        assert response.status_code == 422

        # Individual target without target_user_id
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Test",
                "message": "Test",
                "type": "info",
                "target": "individual",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 422

    def test_create_notification_non_admin(self, client, user_token):
        """TC-014: Non-admin cannot create notifications"""
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "title": "Test",
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 403

    def test_rate_limiting(self, client, admin_token):
        """TC-015: Rate limit notification creation"""
        # First notification should succeed
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "First",
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 201

        # Second notification within 60s should fail
        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Second",
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 429


class TestNotificationManagement:
    """Test notification update/delete/list operations"""

    def test_list_notifications_with_filters(self, client, admin_token, db_session, admin_user):
        """TC-010: List notifications with filters"""
        # Create test notifications
        notifications = [
            Notification(
                title="Info 1",
                message="Test info",
                type="info",
                target="all",
                schedule_type="immediate",
                status="sent",
                created_by=admin_user.id
            ),
            Notification(
                title="Warning 1",
                message="Test warning",
                type="warning",
                target="pro",
                schedule_type="immediate",
                status="sent",
                created_by=admin_user.id
            ),
        ]
        db_session.add_all(notifications)
        db_session.commit()

        # List all
        response = client.get(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data
        assert data["total"] >= 2

        # Filter by type
        response = client.get(
            "/api/admin/notifications?type=warning",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert all(n["type"] == "warning" for n in data["notifications"])

        # Filter by target
        response = client.get(
            "/api/admin/notifications?target=pro",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert all(n["target"] == "pro" for n in data["notifications"])

    def test_get_notification_detail(self, client, admin_token, db_session, admin_user):
        """Test get notification detail with delivery stats"""
        # Create notification
        notification = Notification(
            title="Test Detail",
            message="Test",
            type="info",
            target="all",
            schedule_type="immediate",
            status="sent",
            created_by=admin_user.id,
            sent_at=datetime.utcnow()
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        response = client.get(
            f"/api/admin/notifications/{notification.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "notification" in data
        assert "delivery_stats" in data
        assert data["notification"]["id"] == notification.id

    def test_update_scheduled_notification(self, client, admin_token, db_session, admin_user):
        """TC-007: Edit scheduled notification"""
        # Create scheduled notification
        scheduled_time = datetime.utcnow() + timedelta(hours=2)
        notification = Notification(
            title="Original Title",
            message="Original message",
            type="info",
            target="all",
            schedule_type="scheduled",
            scheduled_for=scheduled_time,
            status="scheduled",
            created_by=admin_user.id
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        # Update notification
        new_time = datetime.utcnow() + timedelta(hours=3)
        response = client.put(
            f"/api/admin/notifications/{notification.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "title": "Updated Title",
                "scheduled_for": new_time.isoformat()
            }
        )
        assert response.status_code == 200

        # Verify update
        db_session.refresh(notification)
        assert notification.title == "Updated Title"
        assert abs((notification.scheduled_for - new_time).total_seconds()) < 1

    def test_cannot_update_sent_notification(self, client, admin_token, db_session, admin_user):
        """Test cannot edit sent notification"""
        notification = Notification(
            title="Sent",
            message="Already sent",
            type="info",
            target="all",
            schedule_type="immediate",
            status="sent",
            created_by=admin_user.id,
            sent_at=datetime.utcnow()
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        response = client.put(
            f"/api/admin/notifications/{notification.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"title": "New Title"}
        )
        assert response.status_code == 400

    def test_cancel_scheduled_notification(self, client, admin_token, db_session, admin_user):
        """TC-008: Cancel scheduled notification"""
        scheduled_time = datetime.utcnow() + timedelta(hours=2)
        notification = Notification(
            title="Cancel Me",
            message="Test",
            type="info",
            target="all",
            schedule_type="scheduled",
            scheduled_for=scheduled_time,
            status="scheduled",
            created_by=admin_user.id
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        response = client.delete(
            f"/api/admin/notifications/{notification.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

        # Verify cancelled
        db_session.refresh(notification)
        assert notification.status == "cancelled"

    def test_cannot_cancel_sent_notification(self, client, admin_token, db_session, admin_user):
        """Test cannot cancel sent notification"""
        notification = Notification(
            title="Sent",
            message="Already sent",
            type="info",
            target="all",
            schedule_type="immediate",
            status="sent",
            created_by=admin_user.id,
            sent_at=datetime.utcnow()
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        response = client.delete(
            f"/api/admin/notifications/{notification.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400


class TestUserNotifications:
    """Test user notification endpoints"""

    def test_get_user_notifications(self, client, user_token, db_session, test_user, admin_user):
        """TC-006: User can view their notifications"""
        # Create notification
        notification = Notification(
            title="User Notification",
            message="Test message",
            type="info",
            target="all",
            schedule_type="immediate",
            status="sent",
            created_by=admin_user.id,
            sent_at=datetime.utcnow()
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        # Create delivery
        delivery = NotificationDelivery(
            notification_id=notification.id,
            user_id=test_user.id,
            delivered_at=datetime.utcnow()
        )
        db_session.add(delivery)
        db_session.commit()

        response = client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "notifications" in data
        assert "unread_count" in data
        assert len(data["notifications"]) >= 1

    def test_dismiss_notification(self, client, user_token, db_session, test_user, admin_user):
        """TC-004: User dismisses notification"""
        # Create notification and delivery
        notification = Notification(
            title="Dismissible",
            message="Test",
            type="info",
            target="all",
            schedule_type="immediate",
            status="sent",
            created_by=admin_user.id,
            sent_at=datetime.utcnow()
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        delivery = NotificationDelivery(
            notification_id=notification.id,
            user_id=test_user.id,
            delivered_at=datetime.utcnow()
        )
        db_session.add(delivery)
        db_session.commit()
        db_session.refresh(delivery)

        # Dismiss
        response = client.post(
            f"/api/notifications/{notification.id}/dismiss",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200

        # Verify dismissed
        db_session.refresh(delivery)
        assert delivery.dismissed_at is not None

    def test_mark_notification_read(self, client, user_token, db_session, test_user, admin_user):
        """Test mark notification as read"""
        # Create notification and delivery
        notification = Notification(
            title="Read Me",
            message="Test",
            type="info",
            target="all",
            schedule_type="immediate",
            status="sent",
            created_by=admin_user.id,
            sent_at=datetime.utcnow()
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        delivery = NotificationDelivery(
            notification_id=notification.id,
            user_id=test_user.id,
            delivered_at=datetime.utcnow()
        )
        db_session.add(delivery)
        db_session.commit()
        db_session.refresh(delivery)

        # Mark read
        response = client.post(
            f"/api/notifications/{notification.id}/mark-read",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200

        # Verify read
        db_session.refresh(delivery)
        assert delivery.read_at is not None

    def test_user_cannot_access_admin_endpoints(self, client, user_token):
        """Test user cannot access admin endpoints"""
        response = client.get(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403

        response = client.post(
            "/api/admin/notifications",
            headers={"Authorization": f"Bearer {user_token}"},
            json={
                "title": "Test",
                "message": "Test",
                "type": "info",
                "target": "all",
                "schedule_type": "immediate"
            }
        )
        assert response.status_code == 403


class TestNotificationExpiration:
    """Test notification expiration logic"""

    def test_expired_notifications_not_shown(self, client, user_token, db_session, test_user, admin_user):
        """TC-005: Expired notifications auto-removed"""
        # Create expired notification
        notification = Notification(
            title="Expired",
            message="Old news",
            type="info",
            target="all",
            schedule_type="immediate",
            status="sent",
            created_by=admin_user.id,
            sent_at=datetime.utcnow() - timedelta(hours=2),
            expires_in_seconds=3600  # 1 hour
        )
        db_session.add(notification)
        db_session.commit()
        db_session.refresh(notification)

        delivery = NotificationDelivery(
            notification_id=notification.id,
            user_id=test_user.id,
            delivered_at=datetime.utcnow() - timedelta(hours=2)
        )
        db_session.add(delivery)
        db_session.commit()

        # Get notifications - should not include expired
        response = client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 200
        data = response.json()

        # Verify expired notification not in list
        notification_ids = [n["id"] for n in data["notifications"]]
        assert notification.id not in notification_ids
