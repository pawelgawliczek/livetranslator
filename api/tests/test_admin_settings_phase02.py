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


@pytest.mark.skip(reason="Deprecated: Global STT provider settings replaced by language-based routing (Migration 006)")
class TestAdminProviders:
    """
    DEPRECATED TEST CLASS - /api/admin/providers endpoint removed.

    Replaced by language-based routing system (stt_routing_config table).
    See Migration 006 for details.
    New endpoints: /api/admin/languages, /api/admin/languages/{language}
    """

    def test_get_providers_as_admin(self, client, admin_token):
        """DEPRECATED - See class docstring."""
        pass

    def test_get_providers_without_auth(self, client):
        """DEPRECATED - See class docstring."""
        pass


@pytest.mark.skip(reason="Deprecated: Global STT settings endpoint replaced by language-based routing (Migration 006)")
class TestAdminSTTSettingsUpdate:
    """
    DEPRECATED TEST CLASS - /api/admin/settings/stt endpoint removed.

    Replaced by language-based routing system (stt_routing_config table).
    See Migration 006 for details.
    New endpoints use per-language configuration.
    """

    def test_update_stt_settings_as_admin(self, client, admin_token, system_settings):
        """DEPRECATED - See class docstring."""
        pass

    def test_update_partial_provider_only(self, client, admin_token, system_settings):
        """DEPRECATED - See class docstring."""
        pass

    def test_update_final_provider_only(self, client, admin_token, system_settings):
        """DEPRECATED - See class docstring."""
        pass

    def test_create_settings_if_not_exist(self, client, admin_token, setup_database):
        """DEPRECATED - See class docstring."""
        pass

    def test_update_settings_without_auth(self, client, system_settings):
        """DEPRECATED - See class docstring."""
        pass
