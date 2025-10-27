"""Tests for user history API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime
from decimal import Decimal

from ..main import app
from ..models import Base, User, Room, RoomCost
from ..jwt_tools import JWT_SECRET, ALGO
from jose import jwt
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey


# Define Segment model for testing (segments table exists in production but not in models.py)
class Segment(Base):
    __tablename__ = "segments"
    id = Column(Integer, primary_key=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)
    speaker_id = Column(String(64), nullable=False)
    segment_id = Column(String(64), nullable=False)
    revision = Column(Integer, nullable=False)
    ts_iso = Column(String(40), nullable=False)
    text = Column(Text, nullable=False)
    lang = Column(String(8), nullable=False)
    final = Column(Boolean, nullable=False)
    stt_provider = Column(String(50))
    latency_ms = Column(Integer)


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
    from ..user_history_api import get_db
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


class TestUserHistoryAPI:
    """Test user history API endpoints."""

    def test_get_history_no_rooms(self, client, test_user, auth_token):
        """Test getting history with no rooms."""
        response = client.get(
            "/api/user/history",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 0
        assert data["total_stt_minutes"] == 0
        assert data["total_cost_usd"] == 0
        assert len(data["rooms"]) == 0

    def test_get_history_with_recorded_rooms(self, client, test_user, auth_token, setup_database):
        """Test getting history with recorded rooms."""
        db = TestingSessionLocal()

        # Create recorded room
        room = Room(
            code="recorded-room",
            owner_id=test_user.id,
            recording=True,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add(room)
        db.commit()

        # Add costs
        cost = RoomCost(
            id=1,
            room_id="recorded-room",
            ts=datetime.utcnow(),
            pipeline="stt_final",
            mode="whisper",
            units=180,  # 3 minutes
            unit_type="seconds",
            amount_usd=Decimal("0.018")
        )
        db.add(cost)
        db.commit()
        db.close()

        response = client.get(
            "/api/user/history",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 1
        assert data["total_stt_minutes"] == 3.0
        assert len(data["rooms"]) == 1
        assert data["rooms"][0]["room_code"] == "recorded-room"
        assert data["rooms"][0]["recording"] is True
        assert data["rooms"][0]["stt_minutes"] == 3.0

    def test_get_history_exclude_unrecorded(self, client, test_user, auth_token, setup_database):
        """Test that unrecorded rooms are excluded by default."""
        db = TestingSessionLocal()

        # Create unrecorded room
        room = Room(
            code="unrecorded-room",
            owner_id=test_user.id,
            recording=False,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add(room)
        db.commit()
        db.close()

        response = client.get(
            "/api/user/history?only_recorded=true",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 0

    def test_get_history_include_unrecorded(self, client, test_user, auth_token, setup_database):
        """Test including unrecorded rooms."""
        db = TestingSessionLocal()

        # Create unrecorded room
        room = Room(
            code="unrecorded-room",
            owner_id=test_user.id,
            recording=False,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add(room)
        db.commit()
        db.close()

        response = client.get(
            "/api/user/history?only_recorded=false",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 1
        assert data["rooms"][0]["recording"] is False

    def test_get_history_pagination(self, client, test_user, auth_token, setup_database):
        """Test pagination of history."""
        db = TestingSessionLocal()

        # Create multiple rooms
        for i in range(15):
            room = Room(
                code=f"room-{i}",
                owner_id=test_user.id,
                recording=True,
                is_public=False,
                requires_login=False,
                max_participants=10,
                created_at=datetime.utcnow()
            )
            db.add(room)
        db.commit()
        db.close()

        # Get first page
        response = client.get(
            "/api/user/history?limit=10&offset=0",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 15
        assert len(data["rooms"]) == 10

        # Get second page
        response = client.get(
            "/api/user/history?limit=10&offset=10",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 15
        assert len(data["rooms"]) == 5

    def test_get_user_stats(self, client, test_user, auth_token, setup_database):
        """Test getting user statistics."""
        db = TestingSessionLocal()

        # Create recorded room
        room1 = Room(
            code="stats-room-1",
            owner_id=test_user.id,
            recording=True,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        # Create unrecorded room
        room2 = Room(
            code="stats-room-2",
            owner_id=test_user.id,
            recording=False,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add_all([room1, room2])
        db.commit()

        # Add costs to first room
        cost = RoomCost(
            id=2,
            room_id="stats-room-1",
            ts=datetime.utcnow(),
            pipeline="stt_final",
            mode="whisper",
            units=240,  # 4 minutes
            unit_type="seconds",
            amount_usd=Decimal("0.024")
        )
        db.add(cost)
        db.commit()
        db.close()

        response = client.get(
            "/api/user/history/stats",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 2
        assert data["total_recorded_rooms"] == 1
        assert data["total_stt_minutes"] == 4.0
        assert data["total_stt_cost_usd"] == 0.024
        assert "member_since" in data

    def test_history_only_own_rooms(self, client, test_user, auth_token, setup_database):
        """Test that users only see their own rooms."""
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

        # Create room for other user
        other_room = Room(
            code="other-room",
            owner_id=other_user.id,
            recording=True,
            is_public=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )
        db.add(other_room)
        db.commit()
        db.close()

        response = client.get(
            "/api/user/history",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total_rooms"] == 0

    def test_history_no_auth(self, client):
        """Test accessing history without authentication."""
        response = client.get("/api/user/history")
        assert response.status_code == 401
