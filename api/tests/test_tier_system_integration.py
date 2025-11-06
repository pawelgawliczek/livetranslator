"""
Integration tests for Tier System core functionality.

Tests:
- Tier assignment and quota initialization
- Quota deduction and tracking
- Admin quota fallback mechanism
- Database function get_user_quota_available
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, text

from api.models import (
    User,
    Room,
    RoomParticipant,
    SubscriptionTier,
    UserSubscription,
    QuotaTransaction,
    CreditPackage,
    PaymentTransaction
)


@pytest.mark.asyncio
async def test_tier_seed_data_exists(test_db_session):
    """Test that migration 016 seeded subscription tiers correctly"""
    # Query all tiers
    result = await test_db_session.execute(
        select(SubscriptionTier).order_by(SubscriptionTier.id)
    )
    tiers = result.scalars().all()

    # Assert: 3 tiers exist
    assert len(tiers) >= 3

    # Find each tier
    tier_dict = {tier.tier_name: tier for tier in tiers}

    # Free tier
    assert "free" in tier_dict
    free_tier = tier_dict["free"]
    assert free_tier.monthly_price_usd == 0
    assert float(free_tier.monthly_quota_hours) == float(Decimal("0.17"))  # 10 minutes (0.167 rounded by NUMERIC(6,2))
    assert free_tier.provider_tier == "free"
    assert free_tier.is_active == True

    # Plus tier
    assert "plus" in tier_dict
    plus_tier = tier_dict["plus"]
    assert plus_tier.monthly_price_usd == 29
    assert float(plus_tier.monthly_quota_hours) == float(Decimal("2.00"))  # 2 hours
    assert plus_tier.provider_tier == "standard"

    # Pro tier
    assert "pro" in tier_dict
    pro_tier = tier_dict["pro"]
    assert pro_tier.monthly_price_usd == 199
    assert float(pro_tier.monthly_quota_hours) == float(Decimal("10.00"))  # 10 hours
    assert pro_tier.provider_tier == "premium"


@pytest.mark.asyncio
async def test_credit_packages_seed_data(test_db_session):
    """Test that credit packages were seeded correctly"""
    result = await test_db_session.execute(
        select(CreditPackage).order_by(CreditPackage.sort_order)
    )
    packages = result.scalars().all()

    # Assert: 4 packages exist
    assert len(packages) >= 4

    # Check first package (1hr)
    pkg_1hr = next(p for p in packages if p.package_name == "1hr")
    assert pkg_1hr.hours == 1
    assert pkg_1hr.price_usd == 5
    assert pkg_1hr.discount_percent == 0

    # Check best value package (8hr)
    pkg_8hr = next(p for p in packages if p.package_name == "8hr")
    assert pkg_8hr.hours == 8
    assert pkg_8hr.price_usd == 35
    assert pkg_8hr.discount_percent == Decimal("12.50")


@pytest.mark.asyncio
async def test_user_subscription_with_tier(test_db_session, test_user):
    """Test creating user subscription linked to tier"""
    # Get Plus tier
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    # Create subscription
    subscription = UserSubscription(
        user_id=test_user.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30),
        bonus_credits_seconds=1800,  # 30 min bonus
        grace_quota_seconds=0,
        auto_renew=True
    )
    test_db_session.add(subscription)
    await test_db_session.commit()
    await test_db_session.refresh(subscription)

    # Assert: Subscription linked to tier
    assert subscription.tier_id == plus_tier.id
    assert subscription.tier.tier_name == "plus"
    assert subscription.bonus_credits_seconds == 1800


@pytest.mark.asyncio
async def test_quota_transaction_creation(test_db_session, test_user, test_room):
    """Test creating quota transactions for tracking"""
    # Setup subscription
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
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Create quota transaction (deduct)
    transaction = QuotaTransaction(
        user_id=test_user.id,
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-300,  # Negative for deduction
        quota_type="monthly",
        provider_used="speechmatics",
        service_type="stt",
        description="STT usage via Speechmatics"
    )
    test_db_session.add(transaction)
    await test_db_session.commit()
    await test_db_session.refresh(transaction)

    # Assert: Transaction created successfully
    assert transaction.id > 0
    assert transaction.user_id == test_user.id
    assert transaction.amount_seconds == -300
    assert transaction.quota_type == "monthly"

    # Query transactions for user
    result = await test_db_session.execute(
        select(QuotaTransaction)
        .where(QuotaTransaction.user_id == test_user.id)
        .order_by(QuotaTransaction.created_at.desc())
    )
    transactions = result.scalars().all()
    assert len(transactions) == 1


@pytest.mark.asyncio
async def test_get_user_quota_available_function(test_db_session, test_user):
    """Test database function for quota calculation"""
    # Setup: Plus tier with bonus and usage
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
        grace_quota_seconds=0
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Create usage (deduct 1800 seconds)
    transaction1 = QuotaTransaction(
        user_id=test_user.id,
        transaction_type="deduct",
        amount_seconds=-1800,
        quota_type="monthly",
        service_type="stt",
        provider_used="speechmatics"
    )
    test_db_session.add(transaction1)
    await test_db_session.commit()

    # Test: Call function
    result = await test_db_session.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": test_user.id}
    )
    available = result.scalar()

    # Expected: (2hr * 3600) + 3600 (bonus) - 1800 (used) = 9000
    expected = (2 * 3600) + 3600 - 1800
    assert available == expected


@pytest.mark.asyncio
async def test_quota_with_grace_period(test_db_session, test_user):
    """Test grace quota after payment failure"""
    # Setup: Free tier with grace quota granted
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
        billing_period_end=billing_start + timedelta(days=30),
        grace_quota_seconds=600  # 10 min grace quota (same as free tier)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    # Test: Available quota includes grace
    result = await test_db_session.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": test_user.id}
    )
    available = result.scalar()

    # Expected: monthly quota + grace
    monthly_seconds = int(float(free_tier.monthly_quota_hours) * 3600)
    grace_seconds = 600
    expected = monthly_seconds + grace_seconds
    assert available == expected


@pytest.mark.asyncio
async def test_room_participant_quota_tracking(test_db_session, test_user, test_room):
    """Test quota tracking per participant"""
    # Setup: Participant in room
    participant = RoomParticipant(
        room_id=test_room.id,
        user_id=test_user.id,
        display_name="Test User",
        spoken_language="en",
        is_active=True,
        quota_used_seconds=0,
        is_using_admin_quota=False,
        quota_source="own"
    )
    test_db_session.add(participant)
    await test_db_session.commit()

    # Simulate quota usage
    participant.quota_used_seconds += 300  # 5 minutes
    await test_db_session.commit()

    # Assert
    await test_db_session.refresh(participant)
    assert participant.quota_used_seconds == 300
    assert participant.is_using_admin_quota == False
    assert participant.quota_source == "own"


@pytest.mark.asyncio
async def test_admin_fallback_quota_tracking(test_db_session, test_room):
    """Test admin quota fallback when participant exhausts quota"""
    # Setup: Admin with Plus tier
    admin = User(
        email="admin@example.com",
        display_name="Admin",
        preferred_lang="en"
    )
    test_db_session.add(admin)
    await test_db_session.flush()

    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "plus")
    )
    plus_tier = tier_result.scalar_one()

    admin_subscription = UserSubscription(
        user_id=admin.id,
        plan="plus",
        status="active",
        tier_id=plus_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(admin_subscription)

    # Update room owner
    test_room.owner_id = admin.id

    # Guest with exhausted free tier
    guest = User(
        email="guest@example.com",
        display_name="Guest",
        preferred_lang="en"
    )
    test_db_session.add(guest)
    await test_db_session.flush()

    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "free")
    )
    free_tier = tier_result.scalar_one()

    guest_subscription = UserSubscription(
        user_id=guest.id,
        plan="free",
        status="active",
        tier_id=free_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(guest_subscription)

    # Exhaust guest quota (free tier is 0.17h = 612 seconds)
    free_tier_seconds = int(float(free_tier.monthly_quota_hours) * 3600)
    guest_transaction = QuotaTransaction(
        user_id=guest.id,
        transaction_type="deduct",
        amount_seconds=-free_tier_seconds,  # Exhaust all quota
        quota_type="monthly",
        service_type="stt",
        provider_used="apple_stt"
    )
    test_db_session.add(guest_transaction)

    # Guest participant using admin quota
    guest_participant = RoomParticipant(
        room_id=test_room.id,
        user_id=guest.id,
        display_name="Guest",
        spoken_language="en",
        is_active=True,
        quota_used_seconds=0,
        is_using_admin_quota=True,  # Fallback to admin
        quota_source="admin"
    )
    test_db_session.add(guest_participant)
    await test_db_session.commit()

    # Create admin fallback quota transaction
    admin_fallback_transaction = QuotaTransaction(
        user_id=admin.id,  # Admin's quota is used
        room_id=test_room.id,
        room_code=test_room.code,
        transaction_type="deduct",
        amount_seconds=-180,  # 3 minutes used from admin quota
        quota_type="admin_fallback",
        service_type="mt",
        provider_used="deepl",
        description="Guest using admin quota"
    )
    test_db_session.add(admin_fallback_transaction)
    await test_db_session.commit()

    # Assert: Admin's available quota decreased
    result = await test_db_session.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": admin.id}
    )
    admin_available = result.scalar()
    expected_admin_quota = (2 * 3600) - 180  # 2 hours - 3 min
    assert admin_available == expected_admin_quota

    # Assert: Guest quota is 0
    result = await test_db_session.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": guest.id}
    )
    guest_available = result.scalar()
    assert guest_available == 0


@pytest.mark.asyncio
async def test_payment_transaction_stripe(test_db_session, test_user):
    """Test creating Stripe payment transaction"""
    transaction = PaymentTransaction(
        user_id=test_user.id,
        platform="stripe",
        transaction_type="subscription",
        amount_usd=Decimal("29.00"),
        currency="USD",
        stripe_payment_intent_id="pi_test123",
        stripe_subscription_id="sub_test456",
        status="succeeded",
        completed_at=datetime.utcnow()
    )
    test_db_session.add(transaction)
    await test_db_session.commit()
    await test_db_session.refresh(transaction)

    # Assert
    assert transaction.id > 0
    assert transaction.platform == "stripe"
    assert transaction.amount_usd == Decimal("29.00")
    assert transaction.status == "succeeded"


@pytest.mark.asyncio
async def test_payment_transaction_apple(test_db_session, test_user):
    """Test creating Apple IAP payment transaction"""
    transaction = PaymentTransaction(
        user_id=test_user.id,
        platform="apple",
        transaction_type="subscription",
        amount_usd=Decimal("29.00"),
        currency="USD",
        apple_transaction_id="1000000123456789",
        apple_original_transaction_id="1000000123456789",
        apple_product_id="com.livetranslator.plus.monthly",
        status="succeeded",
        completed_at=datetime.utcnow()
    )
    test_db_session.add(transaction)
    await test_db_session.commit()
    await test_db_session.refresh(transaction)

    # Assert
    assert transaction.id > 0
    assert transaction.platform == "apple"
    assert transaction.apple_transaction_id == "1000000123456789"
    assert transaction.status == "succeeded"


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
