"""Integration tests for Admin API endpoints (Phase 3)"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import text
from api.main import app
from api.db import SessionLocal
from api.models import User, SubscriptionTier
from api.jwt_tools import JWT_SECRET, ALGO
from jose import jwt
import json


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
    # Check if admin exists
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
    # Ensure subscription tiers exist
    free_tier = db.query(SubscriptionTier).filter(SubscriptionTier.tier_name == "free").first()
    if not free_tier:
        free_tier = SubscriptionTier(
            tier_name="free",
            display_name="Free",
            monthly_price_usd=0,
            monthly_quota_hours=0.167,
            features=["10 minutes per month"],
            provider_tier="free"
        )
        db.add(free_tier)
        db.commit()

    # Add some test payment transactions
    db.execute(text("""
        INSERT INTO payment_transactions (
            user_id, platform, transaction_type, amount_usd, status, created_at
        ) VALUES
        (1, 'stripe', 'subscription', 29.00, 'succeeded', NOW() - INTERVAL '1 day'),
        (1, 'apple', 'subscription', 29.00, 'succeeded', NOW() - INTERVAL '2 days')
        ON CONFLICT DO NOTHING
    """))

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
    # Cleanup if needed


# Test 1: Non-admin user should get 403
def test_financial_summary_non_admin(client, user_token):
    """Non-admin user should not access financial summary"""
    response = client.get(
        "/api/admin/financial/summary",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403


# Test 2: Admin user should get 200 with data
def test_financial_summary_admin(client, admin_token, setup_test_data):
    """Admin user should access financial summary"""
    response = client.get(
        "/api/admin/financial/summary",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "period" in data
    assert "total_revenue_usd" in data
    assert "total_cost_usd" in data
    assert "gross_profit_usd" in data
    assert "gross_margin_pct" in data


# Test 3: Date range filtering works
def test_financial_summary_date_filter(client, admin_token, setup_test_data):
    """Financial summary should filter by date range"""
    start_date = (datetime.utcnow() - timedelta(days=7)).isoformat()
    end_date = datetime.utcnow().isoformat()

    response = client.get(
        f"/api/admin/financial/summary?start_date={start_date}&end_date={end_date}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "period" in data


# Test 4: Tier analysis endpoint
def test_tier_analysis(client, admin_token, setup_test_data):
    """Tier analysis should return tier metrics"""
    response = client.get(
        "/api/admin/financial/tier-analysis",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "tiers" in data
    assert isinstance(data["tiers"], list)


# Test 5: User acquisition endpoint
def test_user_acquisition(client, admin_token, setup_test_data):
    """User acquisition should return signup metrics"""
    response = client.get(
        "/api/admin/users/acquisition",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data
    assert "total_new_users" in data
    assert "total_activated" in data


# Test 6: User engagement endpoint
def test_user_engagement(client, admin_token, setup_test_data):
    """User engagement should return DAU/WAU/MAU"""
    response = client.get(
        "/api/admin/users/engagement",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "metrics" in data


# Test 7: User retention endpoint
def test_user_retention(client, admin_token, setup_test_data):
    """User retention should return cohort analysis"""
    response = client.get(
        "/api/admin/users/retention",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "cohorts" in data


# Test 8: System performance endpoint
def test_system_performance(client, admin_token, setup_test_data):
    """System performance should return provider costs (latency removed)"""
    response = client.get(
        "/api/admin/system/performance",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "providers" in data
    assert "message" in data
    assert "Latency metrics not available" in data["message"]


# Test 9: Quota utilization endpoint
def test_quota_utilization(client, admin_token, setup_test_data):
    """Quota utilization should return tier usage"""
    response = client.get(
        "/api/admin/system/quota-utilization",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "utilization" in data


# Test 10: Grant credits endpoint
def test_grant_credits(client, admin_token, regular_user, db, setup_test_data):
    """Admin should be able to grant credits to users"""
    # First ensure user has a subscription
    db.execute(text("""
        INSERT INTO user_subscriptions (
            user_id, tier_id, status, billing_period_start, billing_period_end
        )
        SELECT
            :user_id,
            (SELECT id FROM subscription_tiers WHERE tier_name = 'free' LIMIT 1),
            'active',
            NOW(),
            NOW() + INTERVAL '30 days'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_subscriptions WHERE user_id = :user_id
        )
    """), {"user_id": regular_user.id})
    db.commit()

    response = client.post(
        f"/api/admin/users/{regular_user.id}/grant-credits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "bonus_hours": 5.0,
            "reason": "Test credit grant"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "bonus_hours_granted" in data
    assert data["bonus_hours_granted"] == 5.0
    assert "new_total_bonus_hours" in data


# Test 11: Grant credits to non-existent user
def test_grant_credits_not_found(client, admin_token):
    """Grant credits should fail for non-existent user"""
    response = client.post(
        "/api/admin/users/99999/grant-credits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "bonus_hours": 5.0,
            "reason": "Test"
        }
    )
    assert response.status_code == 404


# Test 12: Active rooms endpoint
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


# Test 13: Granularity parameter works
def test_financial_summary_granularity(client, admin_token, setup_test_data):
    """Financial summary should respect granularity parameter"""
    response = client.get(
        "/api/admin/financial/summary?granularity=week",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200


# Test 14: Empty results handled gracefully
def test_financial_summary_empty_range(client, admin_token):
    """Financial summary should handle empty date ranges"""
    start_date = (datetime.utcnow() + timedelta(days=365)).isoformat()
    end_date = (datetime.utcnow() + timedelta(days=366)).isoformat()

    response = client.get(
        f"/api/admin/financial/summary?start_date={start_date}&end_date={end_date}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_revenue_usd"] == 0.0


# Test 15: Unauthenticated request should fail
def test_financial_summary_no_auth(client):
    """Financial summary should require authentication"""
    response = client.get("/api/admin/financial/summary")
    assert response.status_code == 401


# Test 16: Grant credits updates subscription correctly
def test_grant_credits_updates_subscription(client, admin_token, regular_user, db, setup_test_data):
    """Grant credits should update user subscription correctly"""
    # Ensure subscription exists
    db.execute(text("""
        INSERT INTO user_subscriptions (
            user_id, tier_id, status, billing_period_start, billing_period_end,
            bonus_credits_seconds
        )
        SELECT
            :user_id,
            (SELECT id FROM subscription_tiers WHERE tier_name = 'free' LIMIT 1),
            'active',
            NOW(),
            NOW() + INTERVAL '30 days',
            0
        WHERE NOT EXISTS (
            SELECT 1 FROM user_subscriptions WHERE user_id = :user_id
        )
    """), {"user_id": regular_user.id})
    db.commit()

    # Get initial bonus credits
    initial = db.execute(text("""
        SELECT bonus_credits_seconds FROM user_subscriptions WHERE user_id = :user_id
    """), {"user_id": regular_user.id}).scalar()

    # Grant 2 hours
    response = client.post(
        f"/api/admin/users/{regular_user.id}/grant-credits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "bonus_hours": 2.0,
            "reason": "Test increment"
        }
    )
    assert response.status_code == 200

    # Verify credits increased by 7200 seconds (2 hours)
    final = db.execute(text("""
        SELECT bonus_credits_seconds FROM user_subscriptions WHERE user_id = :user_id
    """), {"user_id": regular_user.id}).scalar()

    assert final == initial + 7200


# Test 17: Audit log created for grant credits
def test_grant_credits_audit_log(client, admin_token, regular_user, admin_user, db, setup_test_data):
    """Grant credits should create audit log entry"""
    # Ensure subscription exists
    db.execute(text("""
        INSERT INTO user_subscriptions (
            user_id, tier_id, status, billing_period_start, billing_period_end
        )
        SELECT
            :user_id,
            (SELECT id FROM subscription_tiers WHERE tier_name = 'free' LIMIT 1),
            'active',
            NOW(),
            NOW() + INTERVAL '30 days'
        WHERE NOT EXISTS (
            SELECT 1 FROM user_subscriptions WHERE user_id = :user_id
        )
    """), {"user_id": regular_user.id})
    db.commit()

    response = client.post(
        f"/api/admin/users/{regular_user.id}/grant-credits",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "bonus_hours": 1.0,
            "reason": "Audit test"
        }
    )
    assert response.status_code == 200

    # Check audit log
    audit_entry = db.execute(text("""
        SELECT admin_id, action, target_user_id, details
        FROM admin_audit_log
        WHERE admin_id = :admin_id
          AND target_user_id = :target_user_id
          AND action = 'grant_credits'
        ORDER BY created_at DESC
        LIMIT 1
    """), {"admin_id": admin_user.id, "target_user_id": regular_user.id}).fetchone()

    assert audit_entry is not None
    assert audit_entry[0] == admin_user.id
    assert audit_entry[2] == regular_user.id
    details = json.loads(audit_entry[3])
    assert details["bonus_hours"] == 1.0
    assert details["reason"] == "Audit test"
