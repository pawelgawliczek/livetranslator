"""Tests for Phase 0.2: Admin Settings UI backend endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from passlib.hash import bcrypt_sha256 as bcrypt

from ..main import app
from ..models import Base, User, SystemSettings
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
    from ..routers.admin_api import get_db as admin_get_db
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[admin_get_db] = override_get_db
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
def admin_token(admin_user):
    """Create authentication token for admin user."""
    token = jwt.encode(
        {"email": admin_user.email, "sub": str(admin_user.id)},
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


class TestAdminProviders:
    """Test GET /api/admin/providers endpoint."""

    def test_get_providers_as_admin(self, client, admin_token):
        """Test getting available providers as admin."""
        response = client.get(
            "/api/admin/providers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()

        # Check structure
        assert "stt_partial" in data
        assert "stt_final" in data
        assert "mt" in data

        # Check STT partial providers
        assert len(data["stt_partial"]) > 0
        provider_ids = [p["id"] for p in data["stt_partial"]]
        assert "openai_chunked" in provider_ids
        assert "deepgram" in provider_ids
        assert "local" in provider_ids

        # Check STT final providers
        assert len(data["stt_final"]) > 0
        final_ids = [p["id"] for p in data["stt_final"]]
        assert "openai" in final_ids
        assert "elevenlabs" in final_ids
        assert "none" in final_ids

        # Check MT providers
        assert len(data["mt"]) > 0
        mt_ids = [p["id"] for p in data["mt"]]
        assert "openai" in mt_ids

    def test_get_providers_without_auth(self, client):
        """Test getting providers without authentication."""
        response = client.get("/api/admin/providers")
        assert response.status_code == 401


class TestAdminSTTSettingsUpdate:
    """Test POST /api/admin/settings/stt endpoint."""

    def test_update_stt_settings_as_admin(self, client, admin_token, system_settings):
        """Test updating STT settings as admin."""
        response = client.post(
            "/api/admin/settings/stt",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider_default": "deepgram",
                "stt_final_provider_default": "elevenlabs"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "STT settings updated successfully"
        assert len(data["updated"]) == 2

        # Verify settings were updated
        verify_response = client.get(
            "/api/admin/settings/stt",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert verify_response.status_code == 200
        settings = verify_response.json()["settings"]
        settings_dict = {s["key"]: s["value"] for s in settings}
        assert settings_dict["stt_partial_provider_default"] == "deepgram"
        assert settings_dict["stt_final_provider_default"] == "elevenlabs"

    def test_update_partial_provider_only(self, client, admin_token, system_settings):
        """Test updating only partial provider."""
        response = client.post(
            "/api/admin/settings/stt",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={"stt_partial_provider_default": "local"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "stt_partial_provider_default" in data["updated"]

    def test_update_final_provider_only(self, client, admin_token, system_settings):
        """Test updating only final provider."""
        response = client.post(
            "/api/admin/settings/stt",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={"stt_final_provider_default": "none"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "stt_final_provider_default" in data["updated"]

    def test_create_settings_if_not_exist(self, client, admin_token, setup_database):
        """Test creating settings if they don't exist."""
        response = client.post(
            "/api/admin/settings/stt",
            headers={
                "Authorization": f"Bearer {admin_token}",
                "Content-Type": "application/json"
            },
            json={
                "stt_partial_provider_default": "openai_chunked",
                "stt_final_provider_default": "openai"
            }
        )
        assert response.status_code == 200
        assert response.json()["message"] == "STT settings updated successfully"

    def test_update_settings_without_auth(self, client, system_settings):
        """Test updating settings without authentication."""
        response = client.post(
            "/api/admin/settings/stt",
            headers={"Content-Type": "application/json"},
            json={"stt_partial_provider_default": "deepgram"}
        )
        assert response.status_code == 401
