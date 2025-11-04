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

    @pytest.mark.skip(reason="Deprecated: Room-level STT provider fields removed in favor of language-based routing (Migration 006)")
    def test_room_has_stt_provider_fields(self, setup_database, admin_user):
        """
        DEPRECATED TEST - Room model no longer has STT provider override fields.

        Replaced by language-based routing system (stt_routing_config table).
        See Migration 006 for details.
        """
        pass

    @pytest.mark.skip(reason="Deprecated: Room-level STT provider fields removed in favor of language-based routing (Migration 006)")
    def test_room_stt_providers_can_be_null(self, setup_database, admin_user):
        """
        DEPRECATED TEST - Room model no longer has STT provider override fields.

        Replaced by language-based routing system (stt_routing_config table).
        See Migration 006 for details.
        """
        pass

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


class TestUserSearch:
    """Test user search endpoint for US-009."""

    def test_search_by_email_exact_match(self, client, admin_token, setup_database):
        """Should find users by exact email match"""
        # Create test users
        db = TestingSessionLocal()
        user1 = User(
            email="john@example.com",
            display_name="John Doe",
            preferred_lang="en",
            created_at=datetime.utcnow()
        )
        user2 = User(
            email="jane@example.com",
            display_name="Jane Smith",
            preferred_lang="en",
            created_at=datetime.utcnow()
        )
        db.add(user1)
        db.add(user2)
        db.commit()
        db.close()

        response = client.get(
            "/api/admin/users/search?q=john@example.com",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) >= 1
        assert any("john@example.com" in r["email"].lower() for r in data["results"])

    def test_search_by_email_partial_match(self, client, admin_token, setup_database):
        """Should find users by partial email match (case-insensitive)"""
        db = TestingSessionLocal()
        user = User(
            email="test.user@example.com",
            display_name="Test User",
            preferred_lang="en",
            created_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.close()

        response = client.get(
            "/api/admin/users/search?q=test.user",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) >= 1

    def test_search_by_user_id(self, client, admin_token, admin_user):
        """Should find user by exact user ID"""
        response = client.get(
            f"/api/admin/users/search?q={admin_user.id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) >= 1
        assert any(r["user_id"] == admin_user.id for r in data["results"])

    def test_search_requires_admin(self, client, regular_token):
        """Should return 403 for non-admin users"""
        response = client.get(
            "/api/admin/users/search?q=test",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Admin access required"

    def test_search_without_auth(self, client):
        """Should return 401 without authentication"""
        response = client.get("/api/admin/users/search?q=test")
        assert response.status_code == 401

    def test_search_limits_results(self, client, admin_token, setup_database):
        """Should limit results to 50 users max"""
        # Create 60 test users
        db = TestingSessionLocal()
        for i in range(60):
            user = User(
                email=f"user{i}@example.com",
                display_name=f"User {i}",
                preferred_lang="en",
                created_at=datetime.utcnow()
            )
            db.add(user)
        db.commit()
        db.close()

        response = client.get(
            "/api/admin/users/search?q=user",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) <= 50

    def test_search_empty_query(self, client, admin_token):
        """Should return empty results for empty query"""
        response = client.get(
            "/api/admin/users/search?q=",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []

    def test_search_no_results(self, client, admin_token):
        """Should return empty results when no users match"""
        response = client.get(
            "/api/admin/users/search?q=nonexistent@example.com",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []

    def test_search_includes_tier_info(self, client, admin_token, setup_database):
        """Should include tier and quota information in results"""
        # This test will verify the response schema includes tier_name, quota_used_hours, etc.
        db = TestingSessionLocal()
        user = User(
            email="tieruser@example.com",
            display_name="Tier User",
            preferred_lang="en",
            created_at=datetime.utcnow()
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Create subscription (if tables exist)
        from sqlalchemy import text
        result = db.execute(text("""
            SELECT id FROM subscription_tiers WHERE tier_name = 'free' LIMIT 1
        """)).fetchone()

        if result:
            tier_id = result[0]
            db.execute(text("""
                INSERT INTO user_subscriptions (user_id, tier_id, status, billing_period_end)
                VALUES (:user_id, :tier_id, 'active', NOW() + INTERVAL '30 days')
                ON CONFLICT (user_id) DO NOTHING
            """), {"user_id": user.id, "tier_id": tier_id})
            db.commit()

        db.close()

        response = client.get(
            "/api/admin/users/search?q=tieruser",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()

        if len(data["results"]) > 0:
            result = data["results"][0]
            assert "user_id" in result
            assert "email" in result
            assert "display_name" in result
            assert "tier_name" in result
            assert "quota_used_hours" in result
            assert "signup_date" in result
