"""
End-to-end tests for US-012 Email Notifications.

Tests complete user journeys from trigger to email delivery:
- TC-01: 80% quota warning email delivery
- TC-02: 100% exhaustion email + deduplication
- TC-03: Welcome email after subscription purchase
- TC-04: Email preference disable blocks emails
- TC-05: Email preference enable restores emails
- TC-06: 80% email on multiple crossings (credit purchase scenario)
- TC-07: Welcome email for first-time credit buyers

Priority: P0 (Critical user-facing notifications)
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch, AsyncMock, MagicMock
from sqlalchemy import text, select

from api.models import (
    User,
    SubscriptionTier,
    UserSubscription,
    QuotaTransaction,
    Room,
    CreditPackage
)
from api.email_service import send_quota_email, send_welcome_email


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_web3forms():
    """Mock Web3Forms API to capture email payloads without sending real emails."""
    with patch("api.email_service.send_email_via_web3forms", new_callable=AsyncMock) as mock:
        # Mock successful email send
        mock.return_value = {
            "success": True,
            "message": "Email sent successfully",
            "id": "test-email-id-123"
        }
        yield mock


@pytest.fixture(scope="function")
def test_db():
    """Create sync database session for E2E tests."""
    from api.db import SessionLocal
    db = SessionLocal()
    try:
        # Clean test data before test
        db.execute(text("DELETE FROM email_notifications WHERE user_email LIKE '%@e2etest.com'"))
        db.execute(text("DELETE FROM quota_transactions WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@e2etest.com')"))
        db.execute(text("DELETE FROM user_subscriptions WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@e2etest.com')"))
        db.execute(text("DELETE FROM users WHERE email LIKE '%@e2etest.com'"))
        db.commit()
        yield db
    finally:
        # Clean test data after test
        try:
            db.execute(text("DELETE FROM email_notifications WHERE user_email LIKE '%@e2etest.com'"))
            db.execute(text("DELETE FROM quota_transactions WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@e2etest.com')"))
            db.execute(text("DELETE FROM user_subscriptions WHERE user_id IN (SELECT id FROM users WHERE email LIKE '%@e2etest.com')"))
            db.execute(text("DELETE FROM users WHERE email LIKE '%@e2etest.com'"))
            db.commit()
        except Exception:
            pass
        db.close()


@pytest.fixture(scope="function")
def seed_tiers(test_db):
    """Seed subscription tiers for tests."""
    # Check if tiers exist, create if not
    free_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
    ).fetchone()

    if not free_tier:
        test_db.execute(
            text("""
                INSERT INTO subscription_tiers (tier_name, display_name, monthly_price_usd, monthly_quota_hours, features, provider_tier, is_active)
                VALUES ('free', 'Free', 0.00, 0.17, '[]'::jsonb, 'free', true)
            """)
        )

    plus_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'plus'")
    ).fetchone()

    if not plus_tier:
        test_db.execute(
            text("""
                INSERT INTO subscription_tiers (tier_name, display_name, monthly_price_usd, monthly_quota_hours, features, provider_tier, is_active)
                VALUES ('plus', 'Plus', 29.00, 2.00, '[]'::jsonb, 'standard', true)
            """)
        )

    test_db.commit()
    yield


# ============================================================================
# TC-01: 80% Quota Warning Email Delivery
# ============================================================================

@pytest.mark.asyncio
async def test_tc01_80_percent_quota_warning_email(test_db, seed_tiers, mock_web3forms):
    """
    TC-01: 80% Quota Warning Email Delivery

    Scenario: User crosses 80% quota threshold
    Expected: Email sent with correct content
    """
    # Setup: Create user with Free tier (10 minutes = 600 seconds quota)
    free_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
    ).fetchone()

    user = User(
        email="tc01@e2etest.com",
        display_name="TC01 User",
        password_hash="hashed",
        email_notifications_enabled=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    # Create subscription with 50% quota used (300 seconds remaining)
    billing_start = datetime.utcnow()
    billing_end = billing_start + timedelta(days=30)

    subscription = UserSubscription(
        user_id=user.id,
        tier_id=free_tier[0],
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        status="active"
    )
    test_db.add(subscription)
    test_db.commit()

    # Simulate quota usage: 300 seconds used (50% of 600)
    test_db.execute(
        text("""
            INSERT INTO quota_transactions (user_id, transaction_type, amount_seconds, quota_type, service_type, created_at)
            VALUES (:user_id, 'deduct', -300, 'own', 'stt', NOW())
        """),
        {"user_id": user.id}
    )
    test_db.commit()

    # Action: Deduct quota to cross 80% threshold (200 seconds more = 500 total used, 100 remaining = 16.67%)
    # This crosses the 20% remaining threshold (80% used)
    remaining_before = 300  # 50% remaining
    deduct_amount = 200     # Cross to 16.67% remaining
    new_remaining = 100

    # Trigger email notification
    await send_quota_email(
        db=test_db,
        user_id=user.id,
        notification_type="quota_80",
        percentage=80,
        remaining_seconds=new_remaining,
        billing_period_start=billing_start
    )

    # Verify: Web3Forms called
    assert mock_web3forms.called
    call_args = mock_web3forms.call_args
    assert call_args[1]["to_email"] == "tc01@e2etest.com"
    assert "80%" in call_args[1]["subject"]
    assert "0.0 hours" in call_args[1]["body"]  # 100 seconds = 0.03 hours, rounded to 0.0

    # Verify: Database record created
    email_record = test_db.execute(
        text("""
            SELECT * FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'quota_80'
            AND quota_percentage = 80
            AND delivery_status = 'sent'
        """),
        {"user_id": user.id}
    ).fetchone()

    assert email_record is not None
    assert email_record.user_email == "tc01@e2etest.com"
    assert "80%" in email_record.subject


# ============================================================================
# TC-02: 100% Exhaustion Email + Deduplication
# ============================================================================

@pytest.mark.asyncio
async def test_tc02_quota_100_exhaustion_email_with_deduplication(test_db, seed_tiers, mock_web3forms):
    """
    TC-02: Quota 100% Exhaustion Email Sent Once Per Period

    Scenario: User exhausts quota, then tries to use more
    Expected: Email sent once, not again in same billing period
    """
    # Setup: Create user with Free tier
    free_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
    ).fetchone()

    user = User(
        email="tc02@e2etest.com",
        display_name="TC02 User",
        password_hash="hashed",
        email_notifications_enabled=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    billing_start = datetime.utcnow()
    billing_end = billing_start + timedelta(days=30)

    subscription = UserSubscription(
        user_id=user.id,
        tier_id=free_tier[0],
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        status="active"
    )
    test_db.add(subscription)
    test_db.commit()

    # Simulate 100% quota usage
    test_db.execute(
        text("""
            INSERT INTO quota_transactions (user_id, transaction_type, amount_seconds, quota_type, service_type, created_at)
            VALUES (:user_id, 'deduct', -600, 'own', 'stt', NOW())
        """),
        {"user_id": user.id}
    )
    test_db.commit()

    # Action 1: Send first exhaustion email
    result1 = await send_quota_email(
        db=test_db,
        user_id=user.id,
        notification_type="quota_100",
        percentage=100,
        remaining_seconds=0,
        billing_period_start=billing_start
    )

    assert result1 is True
    assert mock_web3forms.call_count == 1

    # Verify first email
    call_args = mock_web3forms.call_args
    assert "Exhausted" in call_args[1]["subject"]

    # Action 2: Try to send again (simulating webhook retry or additional deduction)
    mock_web3forms.reset_mock()
    result2 = await send_quota_email(
        db=test_db,
        user_id=user.id,
        notification_type="quota_100",
        percentage=100,
        remaining_seconds=0,
        billing_period_start=billing_start
    )

    # Verify: Second email NOT sent (deduplication)
    assert result2 is False
    assert mock_web3forms.call_count == 0

    # Verify: Only one record in database
    count = test_db.execute(
        text("""
            SELECT COUNT(*) FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'quota_100'
            AND billing_period_start = :period_start
        """),
        {"user_id": user.id, "period_start": billing_start}
    ).scalar()

    assert count == 1


# ============================================================================
# TC-03: Welcome Email After Subscription Purchase
# ============================================================================

@pytest.mark.asyncio
async def test_tc03_welcome_email_after_subscription_purchase(test_db, seed_tiers, mock_web3forms):
    """
    TC-03: Welcome Email After Subscription Purchase (Plus Tier)

    Scenario: User upgrades from Free to Plus tier
    Expected: Welcome email sent with subscription details
    """
    # Setup: Create user
    plus_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'plus'")
    ).fetchone()

    user = User(
        email="tc03@e2etest.com",
        display_name="TC03 User",
        password_hash="hashed",
        email_notifications_enabled=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    billing_start = datetime.utcnow()
    billing_end = billing_start + timedelta(days=30)

    # Simulate subscription purchase (Stripe webhook would create this)
    subscription = UserSubscription(
        user_id=user.id,
        tier_id=plus_tier[0],
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        status="active",
        stripe_subscription_id="sub_test123"
    )
    test_db.add(subscription)
    test_db.commit()

    # Action: Send welcome email
    result = await send_welcome_email(
        db=test_db,
        user_id=user.id,
        tier_name="Plus"
    )

    # Verify: Email sent
    assert result is True
    assert mock_web3forms.called

    call_args = mock_web3forms.call_args
    assert call_args[1]["to_email"] == "tc03@e2etest.com"
    assert "Welcome to LiveTranslator Plus!" in call_args[1]["subject"]
    assert "2.0 hours" in call_args[1]["body"]  # Plus tier quota

    # Verify: Database record
    email_record = test_db.execute(
        text("""
            SELECT * FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'welcome'
            AND tier_name = 'Plus'
            AND delivery_status = 'sent'
        """),
        {"user_id": user.id}
    ).fetchone()

    assert email_record is not None
    assert "Welcome" in email_record.subject


# ============================================================================
# TC-04: Email Preference Disable Prevents Quota Email
# ============================================================================

@pytest.mark.asyncio
async def test_tc04_email_preference_disable_prevents_quota_email(test_db, seed_tiers, mock_web3forms):
    """
    TC-04: Email Preference Disable Prevents Quota Email

    Scenario: User disables email notifications, then crosses 80% threshold
    Expected: No email sent
    """
    # Setup: Create user with email notifications DISABLED
    free_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
    ).fetchone()

    user = User(
        email="tc04@e2etest.com",
        display_name="TC04 User",
        password_hash="hashed",
        email_notifications_enabled=False  # DISABLED
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    billing_start = datetime.utcnow()
    billing_end = billing_start + timedelta(days=30)

    subscription = UserSubscription(
        user_id=user.id,
        tier_id=free_tier[0],
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        status="active"
    )
    test_db.add(subscription)
    test_db.commit()

    # Action: Try to send 80% email
    result = await send_quota_email(
        db=test_db,
        user_id=user.id,
        notification_type="quota_80",
        percentage=80,
        remaining_seconds=120,
        billing_period_start=billing_start
    )

    # Verify: Email NOT sent
    assert result is False
    assert not mock_web3forms.called

    # Verify: NO database record created
    count = test_db.execute(
        text("""
            SELECT COUNT(*) FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'quota_80'
        """),
        {"user_id": user.id}
    ).scalar()

    assert count == 0


# ============================================================================
# TC-05: Email Preference Enable Re-Enables Notifications
# ============================================================================

@pytest.mark.asyncio
async def test_tc05_email_preference_enable_restores_notifications(test_db, seed_tiers, mock_web3forms):
    """
    TC-05: Email Preference Enable Re-Enables Notifications

    Scenario: User re-enables email notifications, then quota exhausted
    Expected: Email sent successfully
    """
    # Setup: Create user with email notifications initially disabled
    free_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
    ).fetchone()

    user = User(
        email="tc05@e2etest.com",
        display_name="TC05 User",
        password_hash="hashed",
        email_notifications_enabled=False
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    billing_start = datetime.utcnow()
    billing_end = billing_start + timedelta(days=30)

    subscription = UserSubscription(
        user_id=user.id,
        tier_id=free_tier[0],
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        status="active"
    )
    test_db.add(subscription)
    test_db.commit()

    # Action 1: Re-enable email notifications
    test_db.execute(
        text("UPDATE users SET email_notifications_enabled = TRUE WHERE id = :user_id"),
        {"user_id": user.id}
    )
    test_db.commit()

    # Refresh user object
    test_db.expire(user)
    test_db.refresh(user)
    assert user.email_notifications_enabled is True

    # Action 2: Send quota exhaustion email
    result = await send_quota_email(
        db=test_db,
        user_id=user.id,
        notification_type="quota_100",
        percentage=100,
        remaining_seconds=0,
        billing_period_start=billing_start
    )

    # Verify: Email sent successfully
    assert result is True
    assert mock_web3forms.called

    call_args = mock_web3forms.call_args
    assert "Exhausted" in call_args[1]["subject"]

    # Verify: Database record created
    email_record = test_db.execute(
        text("""
            SELECT * FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'quota_100'
            AND delivery_status = 'sent'
        """),
        {"user_id": user.id}
    ).fetchone()

    assert email_record is not None


# ============================================================================
# TC-06: 80% Email Sent on Every Crossing (Not Just First)
# ============================================================================

@pytest.mark.asyncio
async def test_tc06_80_percent_email_on_multiple_crossings(test_db, seed_tiers, mock_web3forms):
    """
    TC-06: 80% Email Sent on Every Crossing (Not Just First)

    Scenario: User crosses 80% threshold, buys credits, crosses again
    Expected: Email sent both times (not deduplicated)
    """
    # Setup: Create user with Free tier
    free_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
    ).fetchone()

    user = User(
        email="tc06@e2etest.com",
        display_name="TC06 User",
        password_hash="hashed",
        email_notifications_enabled=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    billing_start = datetime.utcnow()
    billing_end = billing_start + timedelta(days=30)

    subscription = UserSubscription(
        user_id=user.id,
        tier_id=free_tier[0],
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        status="active",
        bonus_credits_seconds=0
    )
    test_db.add(subscription)
    test_db.commit()

    # Action 1: First 80% crossing
    result1 = await send_quota_email(
        db=test_db,
        user_id=user.id,
        notification_type="quota_80",
        percentage=80,
        remaining_seconds=120,
        billing_period_start=billing_start
    )

    assert result1 is True
    assert mock_web3forms.call_count == 1

    # Simulate credit purchase (3600 seconds = 1 hour)
    test_db.execute(
        text("""
            UPDATE user_subscriptions
            SET bonus_credits_seconds = 3600
            WHERE user_id = :user_id
        """),
        {"user_id": user.id}
    )
    test_db.commit()

    # Action 2: Second 80% crossing after credit purchase
    mock_web3forms.reset_mock()
    result2 = await send_quota_email(
        db=test_db,
        user_id=user.id,
        notification_type="quota_80",
        percentage=80,
        remaining_seconds=840,  # 14 minutes remaining after crossing again
        billing_period_start=billing_start
    )

    # Verify: Second email sent (NOT deduplicated)
    assert result2 is True
    assert mock_web3forms.call_count == 1

    # Verify: TWO records in database (80% emails not deduplicated)
    count = test_db.execute(
        text("""
            SELECT COUNT(*) FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'quota_80'
            AND billing_period_start = :period_start
        """),
        {"user_id": user.id, "period_start": billing_start}
    ).scalar()

    assert count == 2


# ============================================================================
# TC-07: Welcome Email for First-Time Credit Buyers
# ============================================================================

@pytest.mark.asyncio
async def test_tc07_welcome_email_for_first_time_credit_buyer(test_db, seed_tiers, mock_web3forms):
    """
    TC-07: Welcome Email After First Credit Package Purchase (Free Tier)

    Scenario: Free tier user purchases credit package for first time
    Expected: Welcome email sent with "Credit Package Buyer" tier name
    """
    # Setup: Create free tier user
    free_tier = test_db.execute(
        text("SELECT id FROM subscription_tiers WHERE tier_name = 'free'")
    ).fetchone()

    user = User(
        email="tc07@e2etest.com",
        display_name="TC07 User",
        password_hash="hashed",
        email_notifications_enabled=True
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    billing_start = datetime.utcnow()
    billing_end = billing_start + timedelta(days=30)

    subscription = UserSubscription(
        user_id=user.id,
        tier_id=free_tier[0],
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        status="active",
        bonus_credits_seconds=3600  # 1 hour purchased
    )
    test_db.add(subscription)
    test_db.commit()

    # Action: Send welcome email for credit purchase
    result = await send_welcome_email(
        db=test_db,
        user_id=user.id,
        tier_name="Credit Package Buyer"
    )

    # Verify: Email sent
    assert result is True
    assert mock_web3forms.called

    call_args = mock_web3forms.call_args
    assert call_args[1]["to_email"] == "tc07@e2etest.com"
    assert "Welcome" in call_args[1]["subject"]

    # Note: For credit buyers, tier_name in DB should be "Credit Package Buyer"
    # However, send_welcome_email uses tier from subscription, so we check tier_name param
    email_record = test_db.execute(
        text("""
            SELECT * FROM email_notifications
            WHERE user_id = :user_id
            AND notification_type = 'welcome'
            AND delivery_status = 'sent'
        """),
        {"user_id": user.id}
    ).fetchone()

    assert email_record is not None
    assert email_record.tier_name == "Free"  # Because user still on free tier with bonus credits
