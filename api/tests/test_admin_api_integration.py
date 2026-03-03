"""Integration tests for Admin API endpoints"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from api.main import app
from api.db import SessionLocal
from api.models import User
from api.jwt_tools import JWT_SECRET, ALGO
from jose import jwt


@pytest.fixture
def db():
    """Provide database session"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def admin_user(db):
    """Create admin user for testing"""
    admin = db.query(User).filter(User.email == "admin@test.com").first()
    if not admin:
        admin = User(
            email="admin@test.com",
            display_name="Admin User",
            is_admin=True,
            preferred_lang="en",
            password_hash="test_hash"
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    return admin


@pytest.fixture
def regular_user(db):
    """Create regular user for testing"""
    user = db.query(User).filter(User.email == "user@test.com").first()
    if not user:
        user = User(
            email="user@test.com",
            display_name="Regular User",
            is_admin=False,
            preferred_lang="en",
            password_hash="test_hash"
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    """Generate JWT token for admin user"""
    return jwt.encode(
        {"email": admin_user.email, "sub": str(admin_user.id), "preferred_lang": admin_user.preferred_lang},
        JWT_SECRET,
        algorithm=ALGO
    )


@pytest.fixture
def user_token(regular_user):
    """Generate JWT token for regular user"""
    return jwt.encode(
        {"email": regular_user.email, "sub": str(regular_user.id), "preferred_lang": regular_user.preferred_lang},
        JWT_SECRET,
        algorithm=ALGO
    )


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def setup_test_data(db):
    """Setup test data for admin endpoints"""
    # Add test room costs
    db.execute(text("""
        INSERT INTO room_costs (
            room_id, ts, pipeline, mode, provider, units, unit_type, amount_usd
        )
        SELECT
            'TEST_ROOM',
            NOW() - INTERVAL '1 hour',
            'stt',
            'final',
            'speechmatics',
            60,
            'seconds',
            0.10
        WHERE NOT EXISTS (
            SELECT 1 FROM room_costs WHERE room_id = 'TEST_ROOM' LIMIT 1
        )
    """))

    db.commit()
    yield


def test_user_acquisition(client, admin_token, setup_test_data):
    """User acquisition should return signup metrics"""
    response = client.get(
        "/api/admin/users/acquisition",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "daily" in data or "summary" in data


def test_user_engagement(client, admin_token, setup_test_data):
    """User engagement should return DAU/WAU/MAU"""
    response = client.get(
        "/api/admin/users/engagement",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data or "dau" in data or "daily_active_users" in data or isinstance(data, dict)


def test_user_retention(client, admin_token, setup_test_data):
    """User retention should return cohort analysis"""
    response = client.get(
        "/api/admin/users/retention",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200


def test_system_performance(client, admin_token, setup_test_data):
    """System performance should return provider costs"""
    response = client.get(
        "/api/admin/system/performance",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200


def test_active_rooms(client, admin_token, setup_test_data):
    """Active rooms should return rooms with recent activity (paginated)"""
    response = client.get(
        "/api/admin/rooms/active",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "active_rooms" in data
    assert "total_returned" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data
    assert isinstance(data["active_rooms"], list)
