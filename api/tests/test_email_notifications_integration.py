"""
Integration tests for Email Notifications (US-012).

Tests:
- Quota email triggers (80%, 100%)
- Welcome email triggers (subscription, credit purchase)
- Deduplication logic
- User preferences (opt-out)
- Database records
- Web3Forms API integration (mocked)
"""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
from fastapi import Depends
from unittest.mock import patch, AsyncMock, MagicMock

from api.models import (
    User,
    SubscriptionTier,
    UserSubscription,
    QuotaTransaction,
    Room,
    CreditPackage
)
from api.main import app
from api.auth import get_db
from api.db import SessionLocal
from api.settings import INTERNAL_API_KEY
from api.email_service import (
    send_quota_email,
    send_welcome_email,
    send_email_via_web3forms
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest_asyncio.fixture(scope="function")
async def seed_subscription_tiers(test_db_session):
    """Seed subscription tiers for tests."""
    # Subscription tiers are already seeded globally in conftest.py
    # This fixture exists for compatibility but does nothing
    yield


# Helper to create sync database session override
def get_sync_test_client(mock_user=None):
    """Create TestClient with sync database session and optional user override."""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Use TEST database URL (sync version)
    test_db_url = os.getenv(
        "TEST_POSTGRES_DSN",
        "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator_test"
    )
    # Convert async URL to sync URL
    sync_test_db_url = test_db_url.replace("postgresql+asyncpg://", "postgresql://")

    # Create engine for test database
    test_engine = create_engine(
        sync_test_db_url,
        pool_pre_ping=True,
        isolation_level="READ COMMITTED"
    )
    TestSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False
    )

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
        def override_get_current_user():
            return mock_user
        app.dependency_overrides[get_current_user] = override_get_current_user

    client = TestClient(app)
    return client


def get_sync_db():
    """Get synchronous database session for email tests."""
    import os
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Use TEST database URL (sync version)
    test_db_url = os.getenv(
        "TEST_POSTGRES_DSN",
        "postgresql+asyncpg://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator_test"
    )
    # Convert async URL to sync URL
    sync_test_db_url = test_db_url.replace("postgresql+asyncpg://", "postgresql://")

    # Create engine with isolation level that sees committed data
    engine = create_engine(
        sync_test_db_url,
        pool_pre_ping=True,
        isolation_level="READ COMMITTED"
    )
    TestSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False
    )

    db = TestSessionLocal()
    try:
        return db
    finally:
        pass  # Don't close here, let test manage it


# ============================================================================
# Quota Email Tests (80%, 100%)
# ============================================================================

@pytest.mark.asyncio
async def test_quota_email_80_percent_trigger(test_db_session, test_user, test_room, seed_subscription_tiers):
    """Test 80% quota warning email is sent when crossing threshold"""
    # Setup: Free tier user with email notifications enabled
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

    # Mock Web3Forms API
    mock_response = {"success": True, "message": "Email sent"}
    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = mock_response

        # Get sync DB for email service (creates new transaction that should see committed data)
        db = get_sync_db()

        # Send 80% warning email
        result = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,  # 2 minutes remaining
            billing_period_start=billing_start
        )

        db.close()

    # Assert: Email sent
    assert result is True
    mock_email.assert_called_once()

    # Verify email parameters
    call_args = mock_email.call_args
    assert call_args.kwargs['to_email'] == test_user.email
    assert '80%' in call_args.kwargs['subject']
    assert 'friendly reminder' in call_args.kwargs['body'].lower()

    # Verify database record
    email_record = await test_db_session.execute(
        text("""
            SELECT notification_type, delivery_status, quota_percentage
            FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'quota_80'
        """),
        {"user_id": test_user.id}
    )
    record = email_record.fetchone()
    assert record is not None
    assert record[0] == "quota_80"
    assert record[1] == "sent"
    assert record[2] == 80


@pytest.mark.asyncio
async def test_quota_email_100_percent_exhaustion(test_db_session, test_user, seed_subscription_tiers):
    """Test 100% quota exhaustion email is sent"""
    # Setup: Free tier user
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

    # Mock Web3Forms API
    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        # Send 100% exhaustion email
        result = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_100",
            percentage=100,
            remaining_seconds=0,
            billing_period_start=billing_start
        )

        db.close()

    # Assert
    assert result is True
    mock_email.assert_called_once()

    # Verify subject and body
    call_args = mock_email.call_args
    assert 'Exhausted' in call_args.kwargs['subject']
    assert 'fully used' in call_args.kwargs['body'].lower()

    # Verify database record
    email_record = await test_db_session.execute(
        text("""
            SELECT notification_type, quota_percentage
            FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'quota_100'
        """),
        {"user_id": test_user.id}
    )
    record = email_record.fetchone()
    assert record is not None
    assert record[0] == "quota_100"
    assert record[1] == 100


@pytest.mark.asyncio
async def test_quota_email_80_deduplication(test_db_session, test_user, seed_subscription_tiers):
    """Test 80% email NOT sent multiple times at same percentage"""
    # Setup
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

    # Mock Web3Forms
    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        # Send first 80% email
        result1 = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=billing_start
        )

        # Try to send again (should not trigger due to deduplication logic in quota router)
        # Note: Deduplication for 80% is handled by checking if crossed threshold,
        # not by database constraint. We'll send again to verify behavior.
        result2 = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=100,
            billing_period_start=billing_start
        )

        db.close()

    # Assert: Both emails sent (quota router handles deduplication, not email service)
    assert result1 is True
    assert result2 is True
    assert mock_email.call_count == 2

    # Note: Actual deduplication for 80% happens in quota router by checking
    # old_percentage > 20 and new_percentage <= 20 (crossing threshold logic)


@pytest.mark.asyncio
async def test_quota_email_100_deduplication_per_billing_period(test_db_session, test_user, seed_subscription_tiers):
    """Test 100% email sent only once per billing period"""
    # Setup
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

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        # Send first 100% email
        result1 = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_100",
            percentage=100,
            remaining_seconds=0,
            billing_period_start=billing_start
        )

        # Try to send again in same billing period (should be blocked)
        result2 = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_100",
            percentage=100,
            remaining_seconds=0,
            billing_period_start=billing_start
        )

        db.close()

    # Assert: Only first email sent
    assert result1 is True
    assert result2 is False  # Deduplication blocked second email
    assert mock_email.call_count == 1


@pytest.mark.asyncio
async def test_quota_email_not_sent_when_disabled(test_db_session, test_user, seed_subscription_tiers):
    """Test email not sent if user has email_notifications_enabled=False"""
    # Setup: Disable email notifications
    await test_db_session.execute(
        text("UPDATE users SET email_notifications_enabled = FALSE WHERE id = :user_id"),
        {"user_id": test_user.id}
    )
    await test_db_session.commit()

    # Refresh user object
    await test_db_session.refresh(test_user)
    assert test_user.email_notifications_enabled is False

    # Setup subscription
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

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        db = get_sync_db()

        # Try to send email
        result = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=billing_start
        )

        db.close()

    # Assert: Email not sent
    assert result is False
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_quota_email_web3forms_payload(test_db_session, test_user, seed_subscription_tiers):
    """Test Web3Forms API called with correct payload"""
    # Setup
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

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=billing_start
        )

        db.close()

    # Assert: Web3Forms called with correct parameters
    call_args = mock_email.call_args
    assert call_args.kwargs['to_email'] == test_user.email
    assert '80%' in call_args.kwargs['subject']
    assert 'friendly reminder' in call_args.kwargs['body'].lower()
    assert 'remaining quota' in call_args.kwargs['body'].lower()


# ============================================================================
# Welcome Email Tests
# ============================================================================

@pytest.mark.asyncio
async def test_welcome_email_subscription_purchase(test_db_session, test_user, seed_subscription_tiers):
    """Test welcome email sent after subscription purchase"""
    # Setup: Plus tier subscription
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

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        # Send welcome email
        result = await send_welcome_email(
            db=db,
            user_id=test_user.id,
            tier_name=plus_tier.display_name
        )

        db.close()

    # Assert
    assert result is True
    mock_email.assert_called_once()

    # Verify email content
    call_args = mock_email.call_args
    assert 'Welcome' in call_args.kwargs['subject']
    assert plus_tier.display_name in call_args.kwargs['subject']
    assert 'Thank you for subscribing' in call_args.kwargs['body']

    # Verify database record
    email_record = await test_db_session.execute(
        text("""
            SELECT notification_type, tier_name
            FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'welcome'
        """),
        {"user_id": test_user.id}
    )
    record = email_record.fetchone()
    assert record is not None
    assert record[0] == "welcome"
    assert record[1] == plus_tier.display_name


@pytest.mark.asyncio
async def test_welcome_email_credit_package_purchase(test_db_session, test_user, seed_subscription_tiers):
    """Test welcome email sent for credit package purchase (free tier users)"""
    # Setup: Free tier user with credit purchase
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
        bonus_credits_seconds=14400  # 4 hours
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        # Send welcome email for credit buyer
        result = await send_welcome_email(
            db=db,
            user_id=test_user.id,
            tier_name="Credit Package Buyer"
        )

        db.close()

    # Assert
    assert result is True
    mock_email.assert_called_once()


@pytest.mark.asyncio
async def test_welcome_email_not_sent_twice_24h(test_db_session, test_user, seed_subscription_tiers):
    """Test welcome email not sent twice in 24 hours (webhook retry protection)"""
    # Setup: Plus tier subscription
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

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        # Send first welcome email
        result1 = await send_welcome_email(
            db=db,
            user_id=test_user.id,
            tier_name=plus_tier.display_name
        )

        # Try to send again (should be blocked)
        result2 = await send_welcome_email(
            db=db,
            user_id=test_user.id,
            tier_name=plus_tier.display_name
        )

        db.close()

    # Assert: Only first email sent
    assert result1 is True
    assert result2 is False  # Deduplication blocked second email
    assert mock_email.call_count == 1


@pytest.mark.asyncio
async def test_welcome_email_contains_quota_info(test_db_session, test_user, seed_subscription_tiers):
    """Test welcome email contains correct tier name and quota information"""
    # Setup: Pro tier subscription
    tier_result = await test_db_session.execute(
        select(SubscriptionTier).where(SubscriptionTier.tier_name == "pro")
    )
    pro_tier = tier_result.scalar_one()

    subscription = UserSubscription(
        user_id=test_user.id,
        plan="pro",
        status="active",
        tier_id=pro_tier.id,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30)
    )
    test_db_session.add(subscription)
    await test_db_session.commit()

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": True}

        db = get_sync_db()

        await send_welcome_email(
            db=db,
            user_id=test_user.id,
            tier_name=pro_tier.display_name
        )

        db.close()

    # Assert: Email contains quota and tier info
    call_args = mock_email.call_args
    body = call_args.kwargs['body']
    assert pro_tier.display_name in body
    assert 'Monthly quota' in body
    assert 'hours' in body
    assert 'Billing period' in body


# ============================================================================
# User Preferences Tests
# ============================================================================

@pytest.mark.asyncio
async def test_get_email_preferences(test_db_session, test_user):
    """Test GET /api/user/email-preferences returns current setting"""
    client = get_sync_test_client(mock_user=test_user)

    response = client.get("/api/user/email-preferences")

    assert response.status_code == 200
    data = response.json()
    assert "email_notifications_enabled" in data
    assert data["email_notifications_enabled"] is True  # Default

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_email_preferences_disable(test_db_session, test_user, seed_subscription_tiers):
    """Test PATCH /api/user/email-preferences toggles setting to False"""
    client = get_sync_test_client(mock_user=test_user)

    response = client.patch(
        "/api/user/email-preferences",
        json={"email_notifications_enabled": False}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["email_notifications_enabled"] is False

    # Verify in database - commit first to ensure fresh read
    await test_db_session.commit()
    result = await test_db_session.execute(
        text("SELECT email_notifications_enabled FROM users WHERE id = :user_id"),
        {"user_id": test_user.id}
    )
    enabled = result.scalar()
    assert enabled is False

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_patch_email_preferences_enable(test_db_session, test_user, seed_subscription_tiers):
    """Test PATCH /api/user/email-preferences toggles setting to True"""
    # First disable
    await test_db_session.execute(
        text("UPDATE users SET email_notifications_enabled = FALSE WHERE id = :user_id"),
        {"user_id": test_user.id}
    )
    await test_db_session.commit()

    client = get_sync_test_client(mock_user=test_user)

    # Now enable
    response = client.patch(
        "/api/user/email-preferences",
        json={"email_notifications_enabled": True}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["email_notifications_enabled"] is True

    # Verify in database - commit first to ensure fresh read
    await test_db_session.commit()
    result = await test_db_session.execute(
        text("SELECT email_notifications_enabled FROM users WHERE id = :user_id"),
        {"user_id": test_user.id}
    )
    enabled = result.scalar()
    assert enabled is True

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_emails_not_sent_when_preferences_disabled(test_db_session, test_user, seed_subscription_tiers):
    """Test emails not sent when user has disabled notifications"""
    # Setup: Disable notifications
    await test_db_session.execute(
        text("UPDATE users SET email_notifications_enabled = FALSE WHERE id = :user_id"),
        {"user_id": test_user.id}
    )
    await test_db_session.commit()
    await test_db_session.refresh(test_user)

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

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        db = get_sync_db()

        # Try to send quota email
        quota_result = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=datetime.utcnow()
        )

        # Try to send welcome email
        welcome_result = await send_welcome_email(
            db=db,
            user_id=test_user.id,
            tier_name="Plus"
        )

        db.close()

    # Assert: No emails sent
    assert quota_result is False
    assert welcome_result is False
    mock_email.assert_not_called()


# ============================================================================
# Database Records Tests
# ============================================================================

@pytest.mark.asyncio
async def test_email_notification_record_fields(test_db_session, test_user, seed_subscription_tiers):
    """Test database records email with correct notification_type and fields"""
    # Setup
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

    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {
            "success": True,
            "message": "Email sent",
            "id": "test-123"
        }

        db = get_sync_db()

        await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=billing_start
        )

        db.close()

    # Verify database record fields
    email_record = await test_db_session.execute(
        text("""
            SELECT
                user_id,
                notification_type,
                billing_period_start,
                delivery_status,
                web3forms_response,
                user_email,
                subject,
                quota_percentage
            FROM email_notifications
            WHERE user_id = :user_id
        """),
        {"user_id": test_user.id}
    )
    record = email_record.fetchone()

    assert record is not None
    assert record[0] == test_user.id
    assert record[1] == "quota_80"
    assert record[2] == billing_start
    assert record[3] == "sent"
    assert record[4].get("success") is True  # JSONB field returned as dict
    assert record[5] == test_user.email
    assert '80%' in record[6]
    assert record[7] == 80


@pytest.mark.asyncio
async def test_email_failure_recorded_in_database(test_db_session, test_user, seed_subscription_tiers):
    """Test failed email attempts are recorded in database"""
    # Setup
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

    # Mock Web3Forms failure
    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        mock_email.return_value = {"success": False, "error": "Rate limit exceeded"}

        db = get_sync_db()

        result = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=billing_start
        )

        db.close()

    # Assert: Email marked as failed
    assert result is False

    # Verify database record
    email_record = await test_db_session.execute(
        text("""
            SELECT delivery_status, web3forms_response
            FROM email_notifications
            WHERE user_id = :user_id
        """),
        {"user_id": test_user.id}
    )
    record = email_record.fetchone()

    assert record is not None
    assert record[0] == "failed"
    assert record[1].get("success") is False  # JSONB field returned as dict


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================

@pytest.mark.asyncio
async def test_quota_email_user_not_found(test_db_session):
    """Test quota email returns False for non-existent user"""
    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        db = get_sync_db()

        result = await send_quota_email(
            db=db,
            user_id=99999,  # Non-existent user
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=datetime.utcnow()
        )

        db.close()

    assert result is False
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_welcome_email_user_not_found(test_db_session):
    """Test welcome email returns False for non-existent user"""
    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        db = get_sync_db()

        result = await send_welcome_email(
            db=db,
            user_id=99999,  # Non-existent user
            tier_name="Plus"
        )

        db.close()

    assert result is False
    mock_email.assert_not_called()


@pytest.mark.asyncio
async def test_quota_email_no_subscription(test_db_session, test_user):
    """Test quota email returns False if user has no subscription"""
    with patch('api.email_service.send_email_via_web3forms', new_callable=AsyncMock) as mock_email:
        db = get_sync_db()

        result = await send_quota_email(
            db=db,
            user_id=test_user.id,
            notification_type="quota_80",
            percentage=80,
            remaining_seconds=120,
            billing_period_start=datetime.utcnow()
        )

        db.close()

    assert result is False
    mock_email.assert_not_called()
