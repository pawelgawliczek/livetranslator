"""
Integration tests for Quota API endpoints.

Tests:
- GET /api/quota/status - Real-time quota status
- POST /api/quota/deduct - Quota deduction (internal API)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, text
from fastapi.testclient import TestClient

from api.models import (
    User,
    SubscriptionTier,
    UserSubscription,
    QuotaTransaction,
    Room
)
from api.main import app
from api.auth import get_db
from api.db import SessionLocal
from api.settings import JWT_SECRET, INTERNAL_API_KEY
from jose import jwt


# Helper to create JWT token
def create_test_token(user_id: int, email: str = "test@example.com") -> str:
    """Create JWT token for testing."""
    claims = {
        "sub": str(user_id),
        "email": email,
        "preferred_lang": "en",
        "is_admin": False,
        "exp": datetime.utcnow() + timedelta(hours=12)
    }
    return jwt.encode(claims, JWT_SECRET, algorithm="HS256")


# Helper to create sync database session override
def get_sync_test_client(mock_user=None):
    """Create TestClient with sync database session and optional user override."""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Clear any previous overrides
    app.dependency_overrides.clear()

    # Use TEST database
    test_db_url = os.getenv("TEST_POSTGRES_DSN", "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator_test")
    # Convert async URL to sync URL for TestClient
    sync_test_db_url = test_db_url.replace("+asyncpg", "").replace("postgresql://", "postgresql://")

    test_engine = create_engine(sync_test_db_url, pool_pre_ping=True)
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # If mock_user provided, override authentication
    if mock_user:
        from api.auth import get_current_user
        from api.models import User

        # Create a new User object in the sync session to avoid detached instance issues
        def override_get_current_user():
            # Return a mock User-like object with the required attributes
            class MockUser:
                def __init__(self, user_id, email="test@example.com"):
                    self.id = user_id
                    self.email = email
                    self.display_name = "Test User"
                    self.preferred_lang = "en"

            return MockUser(user_id=mock_user.id)

        app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    return client


@pytest.mark.asyncio
async def test_quota_status_free_tier(test_db_session, test_user):
    """Test GET /api/quota/status for free tier user"""
    # Setup: Create free tier subscription
    # No action needed - seed data is already committed by test_db_session fixture

    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    )
    free_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="free",
        status="active",
        tier_id=free_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30),
        bonus_credits_seconds=0,
        grace_quota_seconds=0
    )
    test_db_session.add(subscription)
    await test_db_session.commit()
    await test_db_session.refresh(test_user)  # Refresh to ensure ID is accessible

    # Calculate expected quota
    monthly_quota_seconds = int(float(free_tier.monthly_quota_hours) * 3600)  # 612 seconds (0.17 hours)

    # Test: Get quota status via HTTP
    client = get_sync_test_client(mock_user=test_user)

    response = client.get("/api/quota/status")

    # Assert
    print(f"DEBUG free_tier: Response status={response.status_code}, body={response.text[:200]}")
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "free"
    assert data["quota_seconds_total"] == monthly_quota_seconds
    assert data["quota_seconds_used"] == 0
    assert data["quota_seconds_remaining"] == monthly_quota_seconds
    assert data["grace_quota_seconds"] == 0
    assert len(data["alerts"]) == 0

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quota_status_plus_tier_with_usage(test_db_session, test_user, test_room):
    """Test GET /api/quota/status for Plus tier with partial usage"""
    # Setup: Create Plus tier subscription
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    billing_start = datetime.utcnow() - timedelta(days=10)
    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=billing_start,
        billing_period_end=billing_start + timedelta(days=30),
        bonus_credits_seconds=1800,  # 30 min bonus credits
        grace_quota_seconds=0
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Create some usage (deduct 3600 seconds = 1 hour)
    transaction = QuotaTransaction(
        user_id=test_user.id,
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-3600,  # Negative for deduction
        quota_type="monthly",
        provider_used="speechmatics",
        service_type="stt",
        description="STT usage"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()

    # Calculate expected quota
    monthly_quota_seconds = int(float(plus_tier.monthly_quota_hours) * 3600)  # 7200 seconds (2 hr)
    total_quota = monthly_quota_seconds + 1800  # Plus bonus
    used_seconds = 3600
    remaining_seconds = total_quota - used_seconds

    # Test: Get quota status via HTTP
    client = get_sync_test_client(mock_user=test_user)

    response = client.get("/api/quota/status")

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["tier"] == "plus"
    assert data["quota_seconds_total"] == total_quota
    assert data["quota_seconds_used"] == used_seconds
    assert data["quota_seconds_remaining"] == remaining_seconds
    assert data["grace_quota_seconds"] == 0

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quota_status_80_percent_alert(test_db_session, test_user, test_room):
    """Test quota alert when 80% used"""
    # Setup: Free tier with 80% usage
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    )
    free_tier = tier_result.scalar_one()

    billing_start = datetime.utcnow()
    subscription = UserSubscription(
        user_id=test_user.id,
        plan="free",
        status="active",
        tier_id=free_tier.id,
        billing_period_start=billing_start,
        billing_period_end=billing_start + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Deduct 490 seconds (80% of 612)
    free_tier_seconds = int(float(free_tier.monthly_quota_hours) * 3600)  # 612 seconds
    deduct_amount = int(free_tier_seconds * 0.8)  # 80%
    transaction = QuotaTransaction(
        user_id=test_user.id,
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-deduct_amount,
        quota_type="monthly",
        provider_used="apple_stt",
        service_type="stt"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()

    # Test via HTTP
    client = get_sync_test_client(mock_user=test_user)

    response = client.get("/api/quota/status")

    # Assert: Warning alert triggered
    assert response.status_code == 200
    data = response.json()
    assert len(data["alerts"]) > 0
    assert data["alerts"][0]["type"] == "warning"
    assert data["alerts"][0]["threshold"] == "80_percent"

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quota_deduct_success(test_db_session, test_user, test_room):
    """Test POST /api/quota/deduct with sufficient quota"""
    # Setup: Plus tier with full quota
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Test: Deduct 300 seconds (5 minutes) via HTTP
    client = get_sync_test_client()

    request_data = {
        "user_id": test_user.id,
        "room_code": test_room.code,
        "amount_seconds": 300,
        "service_type": "stt",
        "provider_used": "speechmatics",
        "quota_source": "own"
    }

    response = client.post(
        "/api/quota/deduct",
        json=request_data,
        headers={"X-Internal-API-Key": INTERNAL_API_KEY}
    )

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert data["quota_exhausted"] == False
    assert data["transaction_id"] > 0
    assert data["remaining_seconds"] == 7200 - 300  # 2 hours - 5 min

    # Verify transaction created
    result = await test_db_session.execute(
        select(QuotaTransaction).where(QuotaTransaction.id == data["transaction_id"])
    )
    transaction = result.scalar_one()
    assert transaction.user_id == test_user.id
    assert transaction.amount_seconds == -300  # Negative for deduction
    assert transaction.provider_used == "speechmatics"

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quota_deduct_exhausted(test_db_session, test_user, test_room):
    """Test POST /api/quota/deduct when quota exhausted"""
    # Setup: Free tier with quota fully used
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    )
    free_tier = tier_result.scalar_one()

    billing_start = datetime.utcnow()
    subscription = UserSubscription(
        user_id=test_user.id,
        plan="free",
        status="active",
        tier_id=free_tier.id,
        billing_period_start=billing_start,
        billing_period_end=billing_start + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Exhaust quota (612 seconds)
    free_tier_seconds = int(float(free_tier.monthly_quota_hours) * 3600)
    transaction = QuotaTransaction(
        user_id=test_user.id,
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-free_tier_seconds,
        quota_type="monthly",
        provider_used="apple_stt",
        service_type="stt"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()

    # Test: Try to deduct more via HTTP
    client = get_sync_test_client()

    request_data = {
        "user_id": test_user.id,
        "room_code": test_room.code,
        "amount_seconds": 60,
        "service_type": "mt",
        "provider_used": "deepl",
        "quota_source": "own"
    }

    response = client.post(
        "/api/quota/deduct",
        json=request_data,
        headers={"X-Internal-API-Key": INTERNAL_API_KEY}
    )

    # Assert: Quota exhausted
    assert response.status_code == 200
    data = response.json()
    assert data["quota_exhausted"] == True
    assert data["remaining_seconds"] == 0
    assert data["transaction_id"] == 0  # No transaction created

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quota_deduct_invalid_api_key(test_db_session, test_user, test_room):
    """Test POST /api/quota/deduct with invalid API key (CRIT-2)"""
    # Setup: Plus tier with quota
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Test: Deduct without API key
    client = get_sync_test_client()

    request_data = {
        "user_id": test_user.id,
        "room_code": test_room.code,
        "amount_seconds": 300,
        "service_type": "stt",
        "provider_used": "speechmatics",
        "quota_source": "own"
    }

    # No header
    response = client.post("/api/quota/deduct", json=request_data)
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key"

    # Wrong key
    response = client.post(
        "/api/quota/deduct",
        json=request_data,
        headers={"X-Internal-API-Key": "wrong-key"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid API key"

    # Cleanup
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_quota_function_calculation(test_db_session, test_user):
    """Test get_user_quota_available database function"""
    # Setup: Plus tier with bonus credits and some usage
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    billing_start = datetime.utcnow()
    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=billing_start,
        billing_period_end=billing_start + timedelta(days=30),
        bonus_credits_seconds=3600,  # 1 hour bonus
        grace_quota_seconds=1800  # 30 min grace
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Create usage transaction (deduct 2000 seconds)
    transaction = QuotaTransaction(
        user_id=test_user.id,
        transaction_type="deduct",
        amount_seconds=-2000,
        quota_type="monthly",
        service_type="stt",
        provider_used="speechmatics"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()

    # Test: Call database function
    result = await test_db_session.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": test_user.id}
    )
    available = result.scalar()

    # Expected: (2hr * 3600) + 3600 (bonus) + 1800 (grace) - 2000 (used) = 10600
    monthly_quota = int(plus_tier.monthly_quota_hours * 3600)  # 7200
    expected_available = monthly_quota + 3600 + 1800 - 2000

    assert available == expected_available


# ========================================
# Fixtures
# ========================================

@pytest_asyncio.fixture
async def test_user(test_db_session):
    """Create test user"""
    user = User(
        email="test@example.com",
        display_name="Test User",
        preferred_lang="en"
    )
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_room(test_db_session, test_user):
    """Create test room"""
    room = Room(
        code="TEST123",
        owner_id=test_user.id,
        recording=False
    )
    test_db_session.add(room)
    await test_db_session.commit()
    await test_db_session.refresh(room)
    return room
