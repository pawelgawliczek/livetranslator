"""Tests for Admin Subscriptions API - Phase 3C US-011"""
import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from decimal import Decimal

from ..main import app
from ..db import SessionLocal
from ..models import User, SubscriptionTier, UserSubscription, AdminAuditLog
from ..auth import _issue


@pytest.fixture
def db():
    """Get database session"""
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def admin_user(db):
    """Create admin user for testing"""
    user = User(
        email="admin@test.com",
        password_hash="test_hash",
        display_name="Admin User",
        preferred_lang="en",
        is_admin=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def regular_user(db):
    """Create regular user for testing"""
    user = User(
        email="user@test.com",
        password_hash="test_hash",
        display_name="Regular User",
        preferred_lang="en",
        is_admin=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    """Get JWT token for admin user"""
    token = _issue(admin_user)
    return token.access_token


@pytest.fixture
def user_token(regular_user):
    """Get JWT token for regular user"""
    token = _issue(regular_user)
    return token.access_token


@pytest.fixture
def client():
    """Get test client"""
    return TestClient(app)


@pytest.fixture
def sample_tiers(db):
    """Create sample subscription tiers"""
    tiers = [
        SubscriptionTier(
            tier_name="free",
            display_name="Free",
            monthly_price_usd=Decimal("0.00"),
            monthly_quota_hours=Decimal("0.17"),
            features=["10 minutes per month", "Basic support"],
            provider_tier="free",
            is_active=True
        ),
        SubscriptionTier(
            tier_name="plus",
            display_name="Plus",
            monthly_price_usd=Decimal("29.00"),
            monthly_quota_hours=Decimal("2.00"),
            features=["2 hours per month", "Email support"],
            provider_tier="standard",
            stripe_price_id="price_plus_monthly",
            is_active=True
        ),
        SubscriptionTier(
            tier_name="pro",
            display_name="Pro",
            monthly_price_usd=Decimal("199.00"),
            monthly_quota_hours=Decimal("10.00"),
            features=["10 hours per month", "Priority support"],
            provider_tier="premium",
            stripe_price_id="price_pro_monthly",
            is_active=True
        )
    ]
    for tier in tiers:
        db.add(tier)
    db.commit()
    for tier in tiers:
        db.refresh(tier)
    return tiers


@pytest.fixture
def sample_subscription(db, regular_user, sample_tiers):
    """Create sample user subscription"""
    subscription = UserSubscription(
        user_id=regular_user.id,
        plan="plus",
        status="active",
        tier_id=sample_tiers[1].id,  # Plus tier
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30),
        bonus_credits_seconds=0,
        auto_renew=True
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription


class TestGetSubscriptionTiers:
    """Tests for GET /api/admin/subscriptions/tiers"""

    def test_get_tiers_as_admin(self, client, admin_token, sample_tiers):
        """Admin can list subscription tiers"""
        response = client.get(
            "/api/admin/subscriptions/tiers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "tiers" in data
        assert len(data["tiers"]) == 3
        assert data["total"] == 3

        # Check tier structure
        tier = data["tiers"][0]
        assert "id" in tier
        assert "tier_name" in tier
        assert "display_name" in tier
        assert "monthly_price_usd" in tier
        assert "active_users" in tier

    def test_get_tiers_unauthorized(self, client, user_token):
        """Non-admin cannot list subscription tiers"""
        response = client.get(
            "/api/admin/subscriptions/tiers",
            headers={"Authorization": f"Bearer {user_token}"}
        )
        assert response.status_code == 403

    def test_get_tiers_include_inactive(self, client, admin_token, db, sample_tiers):
        """Test include_inactive parameter"""
        # Deactivate one tier
        tier = sample_tiers[2]
        tier.is_active = False
        db.commit()

        # Without include_inactive
        response = client.get(
            "/api/admin/subscriptions/tiers",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert len(response.json()["tiers"]) == 2

        # With include_inactive
        response = client.get(
            "/api/admin/subscriptions/tiers?include_inactive=true",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        assert len(response.json()["tiers"]) == 3


class TestUpdateSubscriptionTier:
    """Tests for PUT /api/admin/subscriptions/tiers/{tier_id}"""

    def test_update_tier_pricing(self, client, admin_token, db, sample_tiers):
        """Admin can update tier pricing"""
        tier = sample_tiers[1]  # Plus tier
        response = client.put(
            f"/api/admin/subscriptions/tiers/{tier.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "monthly_price_usd": 35.00,
                "display_name": "Plus Premium"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["monthly_price_usd"] == "35.00"
        assert data["display_name"] == "Plus Premium"

        # Verify audit log created
        audit_log = db.query(AdminAuditLog).filter(
            AdminAuditLog.action == "update_subscription_tier"
        ).first()
        assert audit_log is not None
        assert audit_log.details["tier_id"] == tier.id

    def test_update_tier_invalid_price(self, client, admin_token, sample_tiers):
        """Cannot set negative price"""
        tier = sample_tiers[1]
        response = client.put(
            f"/api/admin/subscriptions/tiers/{tier.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"monthly_price_usd": -5.00}
        )
        assert response.status_code == 422  # Validation error

    def test_cannot_deactivate_tier_with_active_users(
        self, client, admin_token, db, sample_tiers, sample_subscription
    ):
        """Cannot deactivate tier with active subscriptions"""
        tier = sample_tiers[1]  # Plus tier (has active subscription)
        response = client.put(
            f"/api/admin/subscriptions/tiers/{tier.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"is_active": False}
        )
        assert response.status_code == 403
        assert "Cannot deactivate tier" in response.json()["detail"]

    def test_update_tier_not_found(self, client, admin_token):
        """Return 404 for non-existent tier"""
        response = client.put(
            "/api/admin/subscriptions/tiers/9999",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"monthly_price_usd": 50.00}
        )
        assert response.status_code == 404


class TestGetUserSubscriptions:
    """Tests for GET /api/admin/subscriptions/users"""

    def test_get_subscriptions(self, client, admin_token, sample_subscription):
        """Admin can list user subscriptions"""
        response = client.get(
            "/api/admin/subscriptions/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "subscriptions" in data
        assert len(data["subscriptions"]) >= 1
        assert data["total"] >= 1

        # Check subscription structure
        sub = data["subscriptions"][0]
        assert "user_email" in sub
        assert "tier_name" in sub
        assert "status" in sub
        assert "platform" in sub

    def test_filter_by_tier(self, client, admin_token, sample_subscription):
        """Filter subscriptions by tier"""
        response = client.get(
            "/api/admin/subscriptions/users?tier=plus",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        for sub in data["subscriptions"]:
            assert sub["tier_name"] == "plus"

    def test_filter_by_status(self, client, admin_token, sample_subscription):
        """Filter subscriptions by status"""
        response = client.get(
            "/api/admin/subscriptions/users?status=active",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        for sub in data["subscriptions"]:
            assert sub["status"] == "active"

    def test_search_by_email(self, client, admin_token, sample_subscription, regular_user):
        """Search subscriptions by email"""
        response = client.get(
            f"/api/admin/subscriptions/users?search={regular_user.email}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["subscriptions"]) >= 1
        assert data["subscriptions"][0]["user_email"] == regular_user.email

    def test_pagination(self, client, admin_token, sample_subscription):
        """Test pagination parameters"""
        response = client.get(
            "/api/admin/subscriptions/users?limit=10&offset=0",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0


class TestChangeTier:
    """Tests for POST /api/admin/subscriptions/{subscription_id}/change-tier"""

    def test_change_tier_immediate(
        self, client, admin_token, db, sample_subscription, sample_tiers
    ):
        """Admin can change subscription tier immediately"""
        pro_tier = sample_tiers[2]  # Pro tier
        response = client.post(
            f"/api/admin/subscriptions/{sample_subscription.id}/change-tier",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "new_tier_id": pro_tier.id,
                "effective_date": "immediate",
                "reason": "User requested upgrade via support ticket"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["old_tier"] == "plus"
        assert data["new_tier"] == "pro"

        # Verify audit log created
        audit_log = db.query(AdminAuditLog).filter(
            AdminAuditLog.action == "change_subscription_tier"
        ).first()
        assert audit_log is not None

    def test_change_tier_invalid_tier(
        self, client, admin_token, sample_subscription
    ):
        """Cannot change to invalid tier"""
        response = client.post(
            f"/api/admin/subscriptions/{sample_subscription.id}/change-tier",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "new_tier_id": 9999,
                "effective_date": "immediate",
                "reason": "Testing invalid tier change"
            }
        )
        assert response.status_code == 400

    def test_change_tier_reason_required(
        self, client, admin_token, sample_subscription, sample_tiers
    ):
        """Reason field is required and validated"""
        pro_tier = sample_tiers[2]
        response = client.post(
            f"/api/admin/subscriptions/{sample_subscription.id}/change-tier",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "new_tier_id": pro_tier.id,
                "effective_date": "immediate",
                "reason": "Short"  # Too short (min 20 chars)
            }
        )
        assert response.status_code == 422  # Validation error


class TestCancelSubscription:
    """Tests for POST /api/admin/subscriptions/{subscription_id}/cancel"""

    def test_cancel_immediate(
        self, client, admin_token, db, sample_subscription
    ):
        """Admin can cancel subscription immediately"""
        response = client.post(
            f"/api/admin/subscriptions/{sample_subscription.id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "effective_date": "immediate",
                "reason": "User requested cancellation due to billing issue"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "cancelled"

        # Verify subscription updated
        db.refresh(sample_subscription)
        assert sample_subscription.status == "cancelled"
        assert sample_subscription.auto_renew == False

    def test_cancel_period_end(
        self, client, admin_token, db, sample_subscription
    ):
        """Admin can cancel subscription at period end"""
        original_end = sample_subscription.billing_period_end
        response = client.post(
            f"/api/admin/subscriptions/{sample_subscription.id}/cancel",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "effective_date": "period_end",
                "reason": "User requested cancellation at period end"
            }
        )
        assert response.status_code == 200

        # Verify billing period unchanged
        db.refresh(sample_subscription)
        assert sample_subscription.billing_period_end == original_end


class TestReactivateSubscription:
    """Tests for POST /api/admin/subscriptions/{subscription_id}/reactivate"""

    def test_reactivate_cancelled_subscription(
        self, client, admin_token, db, sample_subscription, sample_tiers
    ):
        """Admin can reactivate cancelled subscription"""
        # First cancel it
        sample_subscription.status = "cancelled"
        db.commit()

        # Then reactivate
        plus_tier = sample_tiers[1]
        response = client.post(
            f"/api/admin/subscriptions/{sample_subscription.id}/reactivate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tier_id": plus_tier.id,
                "reason": "User resolved payment issue and requested reactivation"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["tier"] == "plus"

        # Verify subscription updated
        db.refresh(sample_subscription)
        assert sample_subscription.status == "active"
        assert sample_subscription.auto_renew == True

    def test_cannot_reactivate_active_subscription(
        self, client, admin_token, sample_subscription, sample_tiers
    ):
        """Cannot reactivate already active subscription"""
        plus_tier = sample_tiers[1]
        response = client.post(
            f"/api/admin/subscriptions/{sample_subscription.id}/reactivate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tier_id": plus_tier.id,
                "reason": "Trying to reactivate active subscription"
            }
        )
        assert response.status_code == 400


class TestSubscriptionAnalytics:
    """Tests for GET /api/admin/subscriptions/analytics"""

    def test_get_analytics(self, client, admin_token, sample_subscription):
        """Admin can view subscription analytics"""
        response = client.get(
            "/api/admin/subscriptions/analytics",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "mrr_history" in data

        # Check summary structure
        summary = data["summary"]
        assert "total_active" in summary
        assert "mrr_usd" in summary
        assert "churn_rate" in summary
        assert "tier_distribution" in summary

    def test_analytics_date_range(self, client, admin_token):
        """Test analytics with date range"""
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.get(
            f"/api/admin/subscriptions/analytics?start_date={start_date}&end_date={end_date}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200
