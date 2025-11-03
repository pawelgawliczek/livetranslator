"""
Integration tests for Quota API endpoints.

Tests:
- GET /api/quota/status - Real-time quota status
- POST /api/quota/deduct - Quota deduction (internal API)
"""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, text

from api.models import (
    User,
    SubscriptionTier,
    UserSubscription,
    QuotaTransaction,
    Room
)


@pytest.mark.asyncio
async def test_quota_status_free_tier(test_db_session, test_user):
    """Test GET /api/quota/status for free tier user"""
    # Setup: Create free tier subscription
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

    # Calculate expected quota
    monthly_quota_seconds = int(free_tier.monthly_quota_hours * 3600)  # 600 seconds (10 min)

    # Test: Get quota status
    from api.routers.quota import get_quota_status

    response = await get_quota_status(
        current_user_id=test_user.id,
        db=test_db_session
    )

    # Assert
    assert response.tier == "free"
    assert response.quota_seconds_total == monthly_quota_seconds
    assert response.quota_seconds_used == 0
    assert response.quota_seconds_remaining == monthly_quota_seconds
    assert response.grace_quota_seconds == 0
    assert len(response.alerts) == 0


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
    monthly_quota_seconds = int(plus_tier.monthly_quota_hours * 3600)  # 7200 seconds (2 hr)
    total_quota = monthly_quota_seconds + 1800  # Plus bonus
    used_seconds = 3600
    remaining_seconds = total_quota - used_seconds

    # Test: Get quota status
    from api.routers.quota import get_quota_status

    response = await get_quota_status(
        current_user_id=test_user.id,
        db=test_db_session
    )

    # Assert
    assert response.tier == "plus"
    assert response.quota_seconds_total == total_quota
    assert response.quota_seconds_used == used_seconds
    assert response.quota_seconds_remaining == remaining_seconds
    assert response.grace_quota_seconds == 0


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

    # Deduct 480 seconds (80% of 600)
    transaction = QuotaTransaction(
        user_id=test_user.id,
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-480,
        quota_type="monthly",
        provider_used="apple_stt",
        service_type="stt"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()

    # Test
    from api.routers.quota import get_quota_status

    response = await get_quota_status(
        current_user_id=test_user.id,
        db=test_db_session
    )

    # Assert: Warning alert triggered
    assert len(response.alerts) > 0
    assert response.alerts[0]["type"] == "warning"
    assert response.alerts[0]["threshold"] == "80_percent"


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

    # Test: Deduct 300 seconds (5 minutes)
    from api.routers.quota import deduct_quota, QuotaDeductRequest

    request = QuotaDeductRequest(
        user_id=test_user.id,
        room_code=test_room.code,
        amount_seconds=300,
        service_type="stt",
        provider_used="speechmatics",
        quota_source="own"
    )

    response = await deduct_quota(
        request=request,
        db=test_db_session,
        x_internal_api_key="internal"
    )

    # Assert
    assert response.quota_exhausted == False
    assert response.transaction_id > 0
    assert response.remaining_seconds == 7200 - 300  # 2 hours - 5 min

    # Verify transaction created
    result = await test_db_session.execute(
        select(QuotaTransaction).where(QuotaTransaction.id == response.transaction_id)
    )
    transaction = result.scalar_one()
    assert transaction.user_id == test_user.id
    assert transaction.amount_seconds == -300  # Negative for deduction
    assert transaction.provider_used == "speechmatics"


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

    # Exhaust quota (600 seconds)
    transaction = QuotaTransaction(
        user_id=test_user.id,
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-600,
        quota_type="monthly",
        provider_used="apple_stt",
        service_type="stt"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()

    # Test: Try to deduct more
    from api.routers.quota import deduct_quota, QuotaDeductRequest

    request = QuotaDeductRequest(
        user_id=test_user.id,
        room_code=test_room.code,
        amount_seconds=60,
        service_type="mt",
        provider_used="deepl",
        quota_source="own"
    )

    response = await deduct_quota(
        request=request,
        db=test_db_session,
        x_internal_api_key="internal"
    )

    # Assert: Quota exhausted
    assert response.quota_exhausted == True
    assert response.remaining_seconds == 0
    assert response.transaction_id == 0  # No transaction created


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

@pytest.fixture
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


@pytest.fixture
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
