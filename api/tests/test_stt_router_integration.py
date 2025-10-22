"""
Integration tests for STT Router with database settings.
Tests that the router correctly fetches and uses room-specific and global settings.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from datetime import datetime
from jose import jwt

from ..main import app
from ..models import Base, Room, User, SystemSettings
from ..db import SessionLocal
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


@pytest.fixture(autouse=True)
def setup_db():
    """Setup test database before each test."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_db():
    """Create a test database session."""
    db = TestingSessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_user(test_db):
    """Create a test user."""
    user = User(email="test@example.com", password_hash="test", created_at=datetime.utcnow())
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_room(test_db, test_user):
    """Create a test room."""
    room = Room(
        code="TESTROOM",
        name="Test Room",
        owner_id=test_user.id,
        created_at=datetime.utcnow()
    )
    test_db.add(room)
    test_db.commit()
    test_db.refresh(room)
    return room


@pytest.fixture
def global_defaults(test_db):
    """Create global default settings."""
    # Clear existing settings
    test_db.query(SystemSettings).filter(
        SystemSettings.key.in_(["stt_partial_provider_default", "stt_final_provider_default"])
    ).delete()

    # Create new defaults
    partial = SystemSettings(key="stt_partial_provider_default", value="openai_chunked")
    final = SystemSettings(key="stt_final_provider_default", value="openai")
    test_db.add(partial)
    test_db.add(final)
    test_db.commit()
    return partial, final


class TestSTTRouterSettings:
    """Test STT Router settings fetching."""

    def test_fetch_global_defaults(self, test_db, global_defaults):
        """Test fetching global default STT settings."""
        partial_row = test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_partial_provider_default"
        ).first()
        final_row = test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_final_provider_default"
        ).first()

        assert partial_row is not None
        assert partial_row.value == "openai_chunked"
        assert final_row is not None
        assert final_row.value == "openai"

    def test_fetch_room_with_defaults(self, test_db, test_room, global_defaults):
        """Test fetching room settings that uses global defaults (NULL overrides)."""
        # Room should have NULL for stt_partial_provider and stt_final_provider
        room = test_db.query(Room).filter(Room.code == test_room.code).first()
        assert room is not None
        assert room.stt_partial_provider is None
        assert room.stt_final_provider is None

        # When NULL, should use global defaults
        partial_default = test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_partial_provider_default"
        ).first().value
        final_default = test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_final_provider_default"
        ).first().value

        # In router logic, NULL means use defaults
        partial = room.stt_partial_provider or partial_default
        final = room.stt_final_provider or final_default

        assert partial == "openai_chunked"
        assert final == "openai"

    def test_fetch_room_with_overrides(self, test_db, test_room, global_defaults):
        """Test fetching room settings with specific overrides."""
        # Set room-specific overrides
        room = test_db.query(Room).filter(Room.code == test_room.code).first()
        room.stt_partial_provider = "deepgram"
        room.stt_final_provider = "elevenlabs"
        test_db.commit()
        test_db.refresh(room)

        # Fetch and verify
        assert room.stt_partial_provider == "deepgram"
        assert room.stt_final_provider == "elevenlabs"

    def test_room_setting_priority(self, test_db, test_room, global_defaults):
        """Test that room-specific settings override global defaults."""
        # Set only partial provider override
        room = test_db.query(Room).filter(Room.code == test_room.code).first()
        room.stt_partial_provider = "local"
        room.stt_final_provider = None  # Keep default
        test_db.commit()
        test_db.refresh(room)

        # Fetch defaults
        final_default = test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_final_provider_default"
        ).first().value

        # Resolve settings (room-specific takes priority)
        partial = room.stt_partial_provider or test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_partial_provider_default"
        ).first().value
        final = room.stt_final_provider or final_default

        assert partial == "local"  # Room override
        assert final == "openai"  # Global default


class TestSTTSettingsAPI:
    """Test STT settings API endpoints."""

    @pytest.fixture
    def client(self):
        from ..main import app
        from ..db import SessionLocal
        app.dependency_overrides[SessionLocal] = override_get_db
        return TestClient(app)

    @pytest.fixture
    def admin_token(self, test_db):
        """Create an admin user and return JWT token."""
        admin = User(
            email="admin@test.com",
            password_hash="test",
            is_admin=True,
            created_at=datetime.utcnow()
        )
        test_db.add(admin)
        test_db.commit()
        test_db.refresh(admin)

        # Create JWT token
        token = jwt.encode({"email": admin.email, "sub": str(admin.id)}, JWT_SECRET, algorithm=ALGO)
        return token

    @pytest.fixture
    def regular_token(self, test_user):
        """Create a regular user token."""
        token = jwt.encode({"email": test_user.email, "sub": str(test_user.id)}, JWT_SECRET, algorithm=ALGO)
        return token

    def test_admin_can_update_global_defaults(self, client, test_db, admin_token, global_defaults):
        """Test that admin can update global STT defaults."""
        response = client.post(
            "/api/admin/settings/stt",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "stt_partial_provider": "deepgram",
                "stt_final_provider": "elevenlabs"
            }
        )
        assert response.status_code == 200

        # Verify database was updated
        partial = test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_partial_provider_default"
        ).first()
        final = test_db.query(SystemSettings).filter(
            SystemSettings.key == "stt_final_provider_default"
        ).first()

        assert partial.value == "deepgram"
        assert final.value == "elevenlabs"

    def test_owner_can_update_room_settings(self, client, test_db, test_room, regular_token):
        """Test that room owner can update room-specific STT settings."""
        response = client.patch(
            f"/api/rooms/{test_room.code}/stt-settings",
            headers={"Authorization": f"Bearer {regular_token}"},
            json={
                "stt_partial_provider": "local",
                "stt_final_provider": "none"
            }
        )
        assert response.status_code == 200

        # Verify database was updated
        room = test_db.query(Room).filter(Room.code == test_room.code).first()
        assert room.stt_partial_provider == "local"
        assert room.stt_final_provider == "none"

    def test_reset_room_to_defaults(self, client, test_db, test_room, regular_token, global_defaults):
        """Test resetting room settings to global defaults."""
        # First set room-specific settings
        room = test_db.query(Room).filter(Room.code == test_room.code).first()
        room.stt_partial_provider = "local"
        room.stt_final_provider = "none"
        test_db.commit()

        # Reset to defaults by sending NULL
        response = client.patch(
            f"/api/rooms/{test_room.code}/stt-settings",
            headers={"Authorization": f"Bearer {regular_token}"},
            json={
                "stt_partial_provider": None,
                "stt_final_provider": None
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_using_defaults"] is True

        # Verify database was updated
        test_db.refresh(room)
        assert room.stt_partial_provider is None
        assert room.stt_final_provider is None
