"""Tests for billing API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from ..main import app
from ..models import Base, User, UserSubscription, Room, RoomCost
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
    from ..billing_api import get_db
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user_with_subscription(setup_database):
    """Create a test user with subscription."""
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

    # Create subscription
    billing_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    subscription = UserSubscription(
        user_id=user.id,
        plan="free",
        status="active",
        monthly_quota_minutes=60,
        billing_period_start=billing_start,
        billing_period_end=billing_start + relativedelta(months=1)
    )
    db.add(subscription)
    db.commit()
    db.close()
    return user_data


@pytest.fixture
def auth_token(test_user_with_subscription):
    """Create authentication token for test user."""
    token = jwt.encode(
        {"email": test_user_with_subscription.email, "sub": str(test_user_with_subscription.id)},
        JWT_SECRET,
        algorithm=ALGO
    )
    return token


class TestBillingAPI:
    """Test billing API endpoints."""

    def test_get_usage_no_rooms(self, client, test_user_with_subscription, auth_token):
        """Test getting usage with no rooms."""
        response = client.get(
            "/api/billing/usage",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_stt_minutes"] == 0
        assert data["total_cost_usd"] == 0
        assert data["quota_minutes"] == 60
        assert data["quota_remaining_minutes"] == 60
        assert len(data["rooms"]) == 0

    def test_get_usage_with_room_and_costs(self, client, test_user_with_subscription, auth_token, setup_database):
        """Test getting usage with room and costs."""
        db = TestingSessionLocal()

        # Create room
        room = Room(
            code="test-room",
            owner_id=test_user_with_subscription.id,
            recording=True,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add(room)
        db.commit()

        # Add costs
        cost1 = RoomCost(
            id=1,
            room_id="test-room",
            ts=datetime.utcnow(),
            pipeline="stt_final",
            mode="whisper",
            units=300,  # 5 minutes in seconds
            unit_type="seconds",
            amount_usd=Decimal("0.03")
        )
        cost2 = RoomCost(
            id=2,
            room_id="test-room",
            ts=datetime.utcnow(),
            pipeline="mt",
            mode="gpt-4o-mini",
            units=1000,
            unit_type="tokens",
            amount_usd=Decimal("0.0006")
        )
        db.add(cost1)
        db.add(cost2)
        db.commit()
        db.close()

        response = client.get(
            "/api/billing/usage",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_stt_minutes"] == 5.0
        assert data["total_stt_cost_usd"] == 0.03
        assert data["total_mt_cost_usd"] == 0.0006
        assert data["quota_remaining_minutes"] == 55.0
        assert len(data["rooms"]) == 1
        assert data["rooms"][0]["room_code"] == "test-room"

    def test_get_room_usage(self, client, test_user_with_subscription, auth_token, setup_database):
        """Test getting usage for specific room."""
        db = TestingSessionLocal()

        # Create room
        room = Room(
            code="specific-room",
            owner_id=test_user_with_subscription.id,
            recording=True,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add(room)
        db.commit()

        # Add cost
        cost = RoomCost(
            id=3,
            room_id="specific-room",
            ts=datetime.utcnow(),
            pipeline="stt_final",
            mode="whisper",
            units=120,  # 2 minutes
            unit_type="seconds",
            amount_usd=Decimal("0.012")
        )
        db.add(cost)
        db.commit()
        db.close()

        response = client.get(
            f"/api/billing/usage/room/specific-room",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["room_code"] == "specific-room"
        assert data["stt_minutes"] == 2.0
        assert data["stt_cost_usd"] == 0.012

    def test_get_room_usage_not_owner(self, client, auth_token, setup_database):
        """Test getting usage for room not owned by user."""
        db = TestingSessionLocal()

        # Create another user
        other_user = User(
            email="other@example.com",
            display_name="Other User",
            preferred_lang="en",
            created_at=datetime.utcnow()
        )
        db.add(other_user)
        db.commit()
        db.refresh(other_user)

        # Create room owned by other user
        room = Room(
            code="other-room",
            owner_id=other_user.id,
            recording=True,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add(room)
        db.commit()
        db.close()

        response = client.get(
            f"/api/billing/usage/room/other-room",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404

    def test_get_quota_status(self, client, test_user_with_subscription, auth_token):
        """Test getting quota status."""
        response = client.get(
            "/api/billing/quota",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["plan"] == "free"
        assert data["quota_minutes"] == 60
        assert data["used_minutes"] == 0
        assert data["remaining_minutes"] == 60
        assert data["is_unlimited"] is False

    def test_billing_no_auth(self, client):
        """Test accessing billing without authentication."""
        response = client.get("/api/billing/usage")
        assert response.status_code == 401
