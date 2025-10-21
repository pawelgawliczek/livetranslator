"""Tests for profile API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from passlib.hash import bcrypt_sha256 as bcrypt

from ..main import app
from ..models import Base, User
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
    from ..profile_api import get_db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(setup_database):
    """Create a test user."""
    db = TestingSessionLocal()
    user = User(
        email="test@example.com",
        password_hash=bcrypt.hash("testpass123"),
        display_name="Test User",
        preferred_lang="en",
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
        'password_hash': user.password_hash
    })()

    db.close()
    return user_data


@pytest.fixture
def auth_token(test_user):
    """Create authentication token for test user."""
    token = jwt.encode(
        {"email": test_user.email, "sub": str(test_user.id)},
        JWT_SECRET,
        algorithm=ALGO
    )
    return token


class TestProfileAPI:
    """Test profile API endpoints."""

    def test_get_profile_success(self, client, test_user, auth_token):
        """Test getting user profile."""
        response = client.get(
            "/api/profile",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["display_name"] == test_user.display_name
        assert data["preferred_lang"] == test_user.preferred_lang
        assert data["has_password"] is True
        assert "created_at" in data

    def test_get_profile_no_auth(self, client):
        """Test getting profile without authentication."""
        response = client.get("/api/profile")
        assert response.status_code == 401

    def test_get_profile_invalid_token(self, client):
        """Test getting profile with invalid token."""
        response = client.get(
            "/api/profile",
            headers={"Authorization": "Bearer invalid_token"}
        )
        assert response.status_code == 401

    def test_update_profile_display_name(self, client, test_user, auth_token):
        """Test updating profile display name."""
        response = client.patch(
            "/api/profile",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"display_name": "Updated Name"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["display_name"] == "Updated Name"

    def test_update_profile_language(self, client, test_user, auth_token):
        """Test updating preferred language."""
        response = client.patch(
            "/api/profile",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"preferred_lang": "pl"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["preferred_lang"] == "pl"

    def test_change_password_success(self, client, test_user, auth_token):
        """Test changing password with correct current password."""
        response = client.post(
            "/api/profile/password",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "current_password": "testpass123",
                "new_password": "newpass456"
            }
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Password changed successfully"

    def test_change_password_wrong_current(self, client, test_user, auth_token):
        """Test changing password with wrong current password."""
        response = client.post(
            "/api/profile/password",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "current_password": "wrongpass",
                "new_password": "newpass456"
            }
        )
        assert response.status_code == 401
        assert "Invalid current password" in response.json()["detail"]

    def test_change_password_no_current_required(self, client, auth_token, setup_database):
        """Test setting password when user has no password (OAuth user)."""
        # Create OAuth user without password
        db = TestingSessionLocal()
        oauth_user = User(
            email="oauth@example.com",
            google_id="google123",
            display_name="OAuth User",
            preferred_lang="en",
            created_at=datetime.utcnow()
        )
        db.add(oauth_user)
        db.commit()
        db.refresh(oauth_user)

        # Store user data before closing session
        user_id = oauth_user.id
        user_email = oauth_user.email

        db.close()

        # Create token for OAuth user
        oauth_token = jwt.encode(
            {"email": user_email, "sub": str(user_id)},
            JWT_SECRET,
            algorithm=ALGO
        )

        response = client.post(
            "/api/profile/password",
            headers={"Authorization": f"Bearer {oauth_token}"},
            json={"new_password": "newpass456"}
        )
        assert response.status_code == 200

    def test_delete_account(self, client, test_user, auth_token):
        """Test deleting user account."""
        response = client.delete(
            "/api/profile",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

        # Verify user is deleted
        db = TestingSessionLocal()
        user = db.query(User).filter(User.email == test_user.email).first()
        assert user is None
        db.close()
