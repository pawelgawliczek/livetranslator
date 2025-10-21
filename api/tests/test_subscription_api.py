"""Tests for subscription API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from dateutil.relativedelta import relativedelta

from ..main import app
from ..models import Base, User, UserSubscription
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
    from ..subscription_api import get_db
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
        'preferred_lang': user.preferred_lang
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


class TestSubscriptionAPI:
    """Test subscription API endpoints."""

    def test_get_subscription_creates_default(self, client, test_user, auth_token):
        """Test getting subscription creates default free subscription."""
        response = client.get(
            "/api/subscription",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "free"
        assert data["status"] == "active"
        assert data["monthly_quota_minutes"] == 60
        assert "billing_period_start" in data
        assert "billing_period_end" in data

    def test_get_subscription_existing(self, client, test_user, auth_token, setup_database):
        """Test getting existing subscription."""
        # Create subscription
        db = TestingSessionLocal()
        subscription = UserSubscription(
            user_id=test_user.id,
            plan="plus",
            status="active",
            monthly_quota_minutes=None,
            billing_period_start=datetime.utcnow(),
            billing_period_end=datetime.utcnow() + relativedelta(months=1)
        )
        db.add(subscription)
        db.commit()
        db.close()

        response = client.get(
            "/api/subscription",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "plus"
        assert data["monthly_quota_minutes"] is None

    def test_update_subscription_to_plus(self, client, test_user, auth_token):
        """Test upgrading subscription to plus."""
        # First create default subscription
        client.get(
            "/api/subscription",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Upgrade to plus
        response = client.patch(
            "/api/subscription",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"plan": "plus"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "plus"
        assert data["monthly_quota_minutes"] is None  # Unlimited

    def test_update_subscription_to_pro(self, client, test_user, auth_token):
        """Test upgrading subscription to pro."""
        # First create default subscription
        client.get(
            "/api/subscription",
            headers={"Authorization": f"Bearer {auth_token}"}
        )

        # Upgrade to pro
        response = client.patch(
            "/api/subscription",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"plan": "pro"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "pro"
        assert data["monthly_quota_minutes"] is None  # Unlimited

    def test_update_subscription_invalid_plan(self, client, test_user, auth_token):
        """Test updating to invalid plan."""
        response = client.patch(
            "/api/subscription",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={"plan": "invalid"}
        )
        assert response.status_code == 400
        assert "Invalid plan" in response.json()["detail"]

    def test_get_plans(self, client):
        """Test getting available subscription plans."""
        response = client.get("/api/subscription/plans")
        assert response.status_code == 200
        data = response.json()
        assert "free" in data
        assert "plus" in data
        assert "pro" in data
        assert data["free"]["monthly_quota_minutes"] == 60
        assert data["plus"]["monthly_quota_minutes"] is None
        assert data["pro"]["monthly_quota_minutes"] is None

    def test_subscription_no_auth(self, client):
        """Test accessing subscription without authentication."""
        response = client.get("/api/subscription")
        assert response.status_code == 401
