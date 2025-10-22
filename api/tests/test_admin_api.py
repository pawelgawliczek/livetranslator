"""Tests for admin API endpoints and authentication."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from passlib.hash import bcrypt_sha256 as bcrypt

from ..main import app
from ..models import Base, User, Room, SystemSettings
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
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


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

    # Store user data before closing session
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
def regular_user(setup_database):
    """Create a test regular (non-admin) user."""
    db = TestingSessionLocal()
    user = User(
        email="user@example.com",
        password_hash=bcrypt.hash("userpass123"),
        display_name="Regular User",
        preferred_lang="en",
        is_admin=False,
        created_at=datetime.utcnow()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Store user data before closing session
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
def system_settings(setup_database):
    """Create test system settings."""
    db = TestingSessionLocal()
    settings = [
        SystemSettings(key="stt_partial_provider_default", value="openai_chunked"),
        SystemSettings(key="stt_final_provider_default", value="openai")
    ]
    for setting in settings:
        db.add(setting)
    db.commit()
    db.close()


class TestAdminModels:
    """Test admin-related database models."""

    def test_user_has_is_admin_field(self, setup_database):
        """Test that User model has is_admin field."""
        db = TestingSessionLocal()
        user = User(
            email="test@example.com",
            display_name="Test",
            preferred_lang="en",
            is_admin=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert hasattr(user, 'is_admin')
        assert user.is_admin is True
        db.close()

    def test_user_is_admin_defaults_to_false(self, setup_database):
        """Test that is_admin defaults to False."""
        db = TestingSessionLocal()
        user = User(
            email="test@example.com",
            display_name="Test",
            preferred_lang="en"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.is_admin is False
        db.close()

    def test_room_has_stt_provider_fields(self, setup_database, admin_user):
        """Test that Room model has STT provider override fields."""
        db = TestingSessionLocal()
        room = Room(
            code="TEST123",
            owner_id=admin_user.id,
            stt_partial_provider="deepgram",
            stt_final_provider="elevenlabs"
        )
        db.add(room)
        db.commit()
        db.refresh(room)

        assert hasattr(room, 'stt_partial_provider')
        assert hasattr(room, 'stt_final_provider')
        assert room.stt_partial_provider == "deepgram"
        assert room.stt_final_provider == "elevenlabs"
        db.close()

    def test_room_stt_providers_can_be_null(self, setup_database, admin_user):
        """Test that STT provider fields can be NULL (use global default)."""
        db = TestingSessionLocal()
        room = Room(
            code="TEST123",
            owner_id=admin_user.id
        )
        db.add(room)
        db.commit()
        db.refresh(room)

        assert room.stt_partial_provider is None
        assert room.stt_final_provider is None
        db.close()

    def test_system_settings_model(self, setup_database):
        """Test SystemSettings model."""
        db = TestingSessionLocal()
        setting = SystemSettings(
            key="test_key",
            value="test_value"
        )
        db.add(setting)
        db.commit()
        db.refresh(setting)

        assert setting.key == "test_key"
        assert setting.value == "test_value"
        assert hasattr(setting, 'updated_at')
        db.close()


class TestAdminAuthentication:
    """Test admin authentication and authorization."""

    def test_admin_test_endpoint_with_admin_user(self, client, admin_user, admin_token):
        """Test admin endpoint with admin user."""
        response = client.get(
            "/api/admin/test",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Admin access verified"
        assert data["admin_email"] == admin_user.email
        assert data["admin_id"] == admin_user.id

    def test_admin_test_endpoint_with_regular_user(self, client, regular_user, regular_token):
        """Test admin endpoint with regular (non-admin) user."""
        response = client.get(
            "/api/admin/test",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    def test_admin_test_endpoint_without_auth(self, client):
        """Test admin endpoint without authentication."""
        response = client.get("/api/admin/test")
        assert response.status_code == 401
        assert response.json()["detail"] == "Not authenticated"

    def test_admin_test_endpoint_with_invalid_token(self, client):
        """Test admin endpoint with invalid token."""
        response = client.get(
            "/api/admin/test",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"

    def test_admin_test_endpoint_without_bearer_prefix(self, client, admin_token):
        """Test admin endpoint without Bearer prefix."""
        response = client.get(
            "/api/admin/test",
            headers={"Authorization": admin_token}
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid authorization header"

    def test_admin_test_endpoint_with_malformed_header(self, client):
        """Test admin endpoint with malformed authorization header."""
        response = client.get(
            "/api/admin/test",
            headers={"Authorization": "Bearer"}
        )
        assert response.status_code == 401


class TestAdminSTTSettings:
    """Test admin STT settings API."""

    def test_get_stt_settings_as_admin(self, client, admin_token, system_settings):
        """Test getting STT settings as admin."""
        response = client.get(
            "/api/admin/settings/stt",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert len(data["settings"]) == 2

        # Check settings values
        settings_dict = {s["key"]: s["value"] for s in data["settings"]}
        assert settings_dict["stt_partial_provider_default"] == "openai_chunked"
        assert settings_dict["stt_final_provider_default"] == "openai"

    def test_get_stt_settings_as_regular_user(self, client, regular_token, system_settings):
        """Test getting STT settings as regular user (should fail)."""
        response = client.get(
            "/api/admin/settings/stt",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    def test_get_stt_settings_without_auth(self, client, system_settings):
        """Test getting STT settings without authentication."""
        response = client.get("/api/admin/settings/stt")
        assert response.status_code == 401

    def test_get_stt_settings_when_empty(self, client, admin_token, setup_database):
        """Test getting STT settings when no settings exist."""
        response = client.get(
            "/api/admin/settings/stt",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "settings" in data
        assert len(data["settings"]) == 0


class TestAdminWorkflow:
    """Test complete admin workflows."""

    def test_create_admin_and_access_protected_endpoint(self, client, setup_database):
        """Test complete workflow: create admin user, login, access admin endpoint."""
        db = TestingSessionLocal()

        # Create admin user
        admin = User(
            email="workflow_admin@example.com",
            password_hash=bcrypt.hash("password123"),
            display_name="Workflow Admin",
            preferred_lang="en",
            is_admin=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        admin_id = admin.id
        admin_email = admin.email
        db.close()

        # Generate token
        token = jwt.encode(
            {"email": admin_email, "sub": str(admin_id)},
            JWT_SECRET,
            algorithm=ALGO
        )

        # Access admin endpoint
        response = client.get(
            "/api/admin/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["admin_email"] == admin_email

    def test_regular_user_cannot_access_admin_endpoints(self, client, setup_database):
        """Test that regular user cannot access any admin endpoint."""
        db = TestingSessionLocal()

        # Create regular user
        user = User(
            email="regular@example.com",
            password_hash=bcrypt.hash("password123"),
            display_name="Regular User",
            preferred_lang="en",
            is_admin=False
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
        user_email = user.email
        db.close()

        # Generate token
        token = jwt.encode(
            {"email": user_email, "sub": str(user_id)},
            JWT_SECRET,
            algorithm=ALGO
        )

        # Try to access admin endpoints
        test_response = client.get(
            "/api/admin/test",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert test_response.status_code == 403

        settings_response = client.get(
            "/api/admin/settings/stt",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert settings_response.status_code == 403
