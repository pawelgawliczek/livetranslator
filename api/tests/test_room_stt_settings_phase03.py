"""Tests for Phase 0.3: Per-Room STT Override."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from passlib.hash import bcrypt_sha256 as bcrypt

from ..main import app
from ..models import Base, User, Room
from ..db import SessionLocal
from ..jwt_tools import JWT_SECRET, ALGO
from jose import jwt


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
    from ..rooms_api import get_db as rooms_get_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[rooms_get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(setup_database):
    """Create a test admin user."""
    db = TestingSessionLocal()
    user = User(
        email="admin@test.com",
        password_hash=bcrypt.hash("password123"),
        display_name="Admin User",
        preferred_lang="en",
        is_admin=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_data = type('UserData', (), {'id': user.id, 'email': user.email, 'is_admin': user.is_admin})()
    db.close()
    return user_data


@pytest.fixture
def regular_user(setup_database):
    """Create a test regular (non-admin) user."""
    db = TestingSessionLocal()
    user = User(
        email="user@test.com",
        password_hash=bcrypt.hash("password123"),
        display_name="Regular User",
        preferred_lang="en",
        is_admin=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_data = type('UserData', (), {'id': user.id, 'email': user.email, 'is_admin': user.is_admin})()
    db.close()
    return user_data


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
def regular_token(regular_user):
    """Create authentication token for regular user."""
    token = jwt.encode(
        {"email": regular_user.email, "sub": str(regular_user.id)},
        JWT_SECRET,
        algorithm=ALGO
    )
    return token


@pytest.fixture
def owner_room(setup_database, regular_user):
    """Create a room owned by regular user."""
    db = TestingSessionLocal()
    room = Room(
        code="TEST123",
        owner_id=regular_user.id,
        created_at=datetime.utcnow()
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    room_data = type('RoomData', (), {'id': room.id, 'code': room.code, 'owner_id': room.owner_id})()
    db.close()
    return room_data


class TestGetRoomSTTSettings:
    """Test GET /api/rooms/{room_code}/stt-settings endpoint."""

    def test_get_settings_default(self, client, owner_room, regular_token):
        """Test getting room STT settings when using defaults."""
        response = client.get(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] is None
        assert data["stt_final_provider"] is None
        assert data["is_using_defaults"] is True

    def test_get_settings_room_not_found(self, client, regular_token):
        """Test getting settings for non-existent room."""
        response = client.get(
            "/api/rooms/NONEXISTENT/stt-settings",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 404

    def test_get_settings_without_auth(self, client, owner_room):
        """Test getting settings without authentication."""
        response = client.get(f"/api/rooms/{owner_room.code}/stt-settings")
        assert response.status_code == 401


class TestUpdateRoomSTTSettings:
    """Test PATCH /api/rooms/{room_code}/stt-settings endpoint."""

    def test_owner_can_update_settings(self, client, owner_room, regular_token):
        """Test that room owner can update STT settings."""
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider": "deepgram",
                "stt_final_provider": "elevenlabs"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] == "deepgram"
        assert data["stt_final_provider"] == "elevenlabs"
        assert data["is_using_defaults"] is False

    def test_admin_can_update_any_room_settings(self, client, owner_room, admin_token):
        """Test that admin can update any room's STT settings."""
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider": "local",
                "stt_final_provider": "none"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] == "local"
        assert data["stt_final_provider"] == "none"

    def test_non_owner_cannot_update_settings(self, client, setup_database, owner_room):
        """Test that non-owner non-admin cannot update settings."""
        # Create another user who is not the owner
        db = TestingSessionLocal()
        other_user = User(
            email="other@test.com",
            password_hash=bcrypt.hash("password123"),
            display_name="Other User",
            preferred_lang="en",
            is_admin=False
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)
        other_user_id = other_user.id
        db.close()

        other_token = jwt.encode(
            {"email": "other@test.com", "sub": str(other_user_id)},
            JWT_SECRET,
            algorithm=ALGO
        )

        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {other_token}",
                "Content-Type": "application/json"
            },
            json={"stt_partial_provider": "deepgram"}
        )
        assert response.status_code == 403
        assert "admin" in response.json()["detail"].lower()

    def test_update_partial_provider_only(self, client, owner_room, regular_token):
        """Test updating only partial provider."""
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={"stt_partial_provider": "openai_chunked"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] == "openai_chunked"
        assert data["stt_final_provider"] is None

    def test_update_final_provider_only(self, client, owner_room, regular_token):
        """Test updating only final provider."""
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={"stt_final_provider": "openai"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] is None
        assert data["stt_final_provider"] == "openai"

    def test_reset_to_defaults(self, client, owner_room, regular_token):
        """Test resetting room settings to defaults (NULL)."""
        # First set some custom settings
        client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider": "deepgram",
                "stt_final_provider": "elevenlabs"
            }
        )

        # Now reset by sending empty strings
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider": "",
                "stt_final_provider": ""
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] is None
        assert data["stt_final_provider"] is None
        assert data["is_using_defaults"] is True

    def test_update_settings_room_not_found(self, client, regular_token):
        """Test updating settings for non-existent room."""
        response = client.patch(
            "/api/rooms/NONEXISTENT/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={"stt_partial_provider": "deepgram"}
        )
        assert response.status_code == 404

    def test_update_settings_without_auth(self, client, owner_room):
        """Test updating settings without authentication."""
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={"Content-Type": "application/json"},
            json={"stt_partial_provider": "deepgram"}
        )
        assert response.status_code == 401


class TestRoomSTTSettingsWorkflow:
    """Test complete workflow for room STT settings."""

    def test_complete_workflow(self, client, owner_room, regular_token, admin_token):
        """Test complete workflow: get defaults, update, verify, admin override, reset."""
        # 1. Check defaults
        response = client.get(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 200
        assert response.json()["is_using_defaults"] is True

        # 2. Owner updates settings
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider": "openai_chunked",
                "stt_final_provider": "openai"
            }
        )
        assert response.status_code == 200

        # 3. Verify settings persisted
        response = client.get(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] == "openai_chunked"
        assert data["stt_final_provider"] == "openai"
        assert data["is_using_defaults"] is False

        # 4. Admin overrides settings
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider": "deepgram",
                "stt_final_provider": "elevenlabs"
            }
        )
        assert response.status_code == 200

        # 5. Verify admin override
        response = client.get(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["stt_partial_provider"] == "deepgram"
        assert data["stt_final_provider"] == "elevenlabs"

        # 6. Reset to defaults
        response = client.patch(
            f"/api/rooms/{owner_room.code}/stt-settings",
            headers={
                "Authorization": f"Bearer {regular_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider": None,
                "stt_final_provider": None
            }
        )
        assert response.status_code == 200
        assert response.json()["is_using_defaults"] is True
