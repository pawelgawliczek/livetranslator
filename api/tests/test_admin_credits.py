"""
Tests for admin credit package management endpoints.

Test Coverage:
- TC-01: Admin views credit packages
- TC-02: Admin edits package pricing
- TC-06: Admin filters purchase history
- TC-08: Cannot deactivate package with recent purchases
- Security: Non-admin access denied
"""
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from datetime import datetime, timedelta

from ..main import app
from ..db import SessionLocal
from ..models import User, CreditPackage, PaymentTransaction, AdminAuditLog, UserSubscription
from ..auth import _issue


@pytest.fixture(scope="function")
def db():
    """Database session for tests with cleanup"""
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture
def client():
    """Get test client"""
    return TestClient(app)


@pytest.fixture
def admin_user(db):
    """Create admin user"""
    user = User(
        email="admin@test.com",
        password_hash="hashed",
        display_name="Admin",
        preferred_lang="en",
        is_admin=True
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
def regular_user(db):
    """Create regular user"""
    user = User(
        email="user@test.com",
        password_hash="hashed",
        display_name="User",
        preferred_lang="en",
        is_admin=False
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def user_token(regular_user):
    """Get JWT token for regular user"""
    token = _issue(regular_user)
    return token.access_token


def test_get_packages_admin_only(client, db, admin_token, user_token):
    """TC-01: Admin can view credit packages, regular user cannot"""
    # Admin can access
    response = client.get(
        "/api/admin/credits/packages",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "packages" in data
    assert len(data["packages"]) >= 4  # At least 4 packages from migration 016

    # Verify package structure
    if len(data["packages"]) > 0:
        pkg = data["packages"][0]
        assert "id" in pkg
        assert "package_name" in pkg
        assert "display_name" in pkg
        assert "hours" in pkg
        assert "price_usd" in pkg
        assert "discount_percent" in pkg
        assert "is_active" in pkg
        assert "sort_order" in pkg
        assert "purchase_count_30d" in pkg

    # Regular user gets 403
    response = client.get(
        "/api/admin/credits/packages",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 403


def test_update_package_pricing(client, db, admin_token):
    """TC-02: Admin edits package pricing and discount is recalculated"""
    # Get 4hr package (from migration 016)
    pkg_4hr = db.query(CreditPackage).filter_by(package_name='4hr').first()

    if not pkg_4hr:
        pytest.skip("4hr package not seeded in test database")

    original_price = float(pkg_4hr.price_usd)

    # Update price from $19 to $18
    response = client.put(
        f"/api/admin/credits/packages/{pkg_4hr.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "display_name": "4 Hours (Sale!)",
            "hours": 4.00,
            "price_usd": 18.00,
            "sort_order": 2,
            "is_active": True
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["package"]["price_usd"] == 18.00
    assert data["package"]["display_name"] == "4 Hours (Sale!)"

    # Verify discount recalculated: (5*4 - 18) / (5*4) * 100 = 10%
    assert data["package"]["discount_percent"] == 10.00

    # Verify audit log created
    assert "audit_log_id" in data
    audit = db.query(AdminAuditLog).filter_by(id=data["audit_log_id"]).first()
    assert audit is not None
    assert audit.action == "update_credit_package"
    assert audit.details["old_values"]["price_usd"] == original_price
    assert audit.details["new_values"]["price_usd"] == 18.00


def test_cannot_deactivate_with_recent_purchases(client, db, admin_token, regular_user):
    """TC-08: Admin cannot deactivate package with recent purchases"""
    # Get 4hr package
    pkg_4hr = db.query(CreditPackage).filter_by(package_name='4hr').first()

    if not pkg_4hr:
        pytest.skip("4hr package not seeded in test database")

    # Create user subscription for transaction
    subscription = UserSubscription(
        user_id=regular_user.id,
        tier_id=None,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30),
        status='active'
    )
    db.add(subscription)
    db.commit()

    # Create recent payment transaction (5 days ago)
    payment_tx = PaymentTransaction(
        user_id=regular_user.id,
        platform='stripe',
        transaction_type='credit_purchase',
        amount_usd=Decimal('19.00'),
        currency='USD',
        status='completed',
        transaction_metadata={'package_id': pkg_4hr.id},
        created_at=datetime.utcnow() - timedelta(days=5),
        completed_at=datetime.utcnow() - timedelta(days=5)
    )
    db.add(payment_tx)
    db.commit()

    # Try to deactivate package
    response = client.put(
        f"/api/admin/credits/packages/{pkg_4hr.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "display_name": "4 Hours",
            "hours": 4.00,
            "price_usd": 19.00,
            "sort_order": 2,
            "is_active": False  # Try to deactivate
        }
    )

    assert response.status_code == 400
    assert "Cannot deactivate package" in response.json()["detail"]
    assert "purchases in last 30 days" in response.json()["detail"]


def test_get_purchase_history_with_filters(client, db, admin_token, regular_user):
    """TC-06: Admin filters purchase history"""
    # Get 4hr package
    pkg_4hr = db.query(CreditPackage).filter_by(package_name='4hr').first()

    if not pkg_4hr:
        pytest.skip("4hr package not seeded in test database")

    # Create user subscription
    subscription = UserSubscription(
        user_id=regular_user.id,
        tier_id=None,
        billing_period_start=datetime.utcnow(),
        billing_period_end=datetime.utcnow() + timedelta(days=30),
        status='active'
    )
    db.add(subscription)
    db.commit()

    # Create purchase transactions
    for i in range(3):
        payment_tx = PaymentTransaction(
            user_id=regular_user.id,
            platform='stripe',
            transaction_type='credit_purchase',
            amount_usd=Decimal('19.00'),
            currency='USD',
            status='completed',
            stripe_payment_intent_id=f'pi_test_{i}',
            transaction_metadata={'package_id': pkg_4hr.id},
            created_at=datetime.utcnow() - timedelta(days=i),
            completed_at=datetime.utcnow() - timedelta(days=i)
        )
        db.add(payment_tx)

    db.commit()

    # Test: Get all purchases
    response = client.get(
        "/api/admin/credits/purchases",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "purchases" in data
    assert "total" in data
    assert data["total"] >= 3

    # Test: Filter by user email
    response = client.get(
        "/api/admin/credits/purchases?user_email=user@test",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["purchases"]) >= 3

    # All results should match filter
    for purchase in data["purchases"]:
        assert "user@test" in purchase["user_email"].lower()

    # Test: Pagination
    response = client.get(
        "/api/admin/credits/purchases?limit=2&offset=0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["purchases"]) <= 2
    assert data["limit"] == 2
    assert data["offset"] == 0


def test_include_inactive_packages(client, db, admin_token):
    """Test include_inactive parameter"""
    # Get 1hr package
    pkg_1hr = db.query(CreditPackage).filter_by(package_name='1hr').first()

    if not pkg_1hr:
        pytest.skip("1hr package not seeded in test database")

    # Deactivate 1hr package (no purchases, so allowed)
    pkg_1hr.is_active = False
    db.commit()

    # Without include_inactive: should not see 1hr
    response = client.get(
        "/api/admin/credits/packages",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    package_names = [p["package_name"] for p in data["packages"]]
    assert "1hr" not in package_names

    # With include_inactive: should see 1hr
    response = client.get(
        "/api/admin/credits/packages?include_inactive=true",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    package_names = [p["package_name"] for p in data["packages"]]
    assert "1hr" in package_names


def test_user_can_view_active_packages(client, db, user_token):
    """Test user endpoint for viewing active packages (not admin endpoint)"""
    # User can access /api/payments/credit-packages
    response = client.get(
        "/api/payments/credit-packages",
        headers={"Authorization": f"Bearer {user_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "packages" in data

    # Verify no sensitive data exposed
    if len(data["packages"]) > 0:
        pkg = data["packages"][0]
        assert "stripe_price_id" not in pkg
        assert "apple_product_id" not in pkg
        assert "purchase_count_30d" not in pkg

        # Verify required fields present
        assert "id" in pkg
        assert "display_name" in pkg
        assert "hours" in pkg
        assert "price_usd" in pkg
        assert "discount_percent" in pkg
        assert "sort_order" in pkg


def test_validation_errors(client, db, admin_token):
    """Test validation on package updates"""
    # Get first package
    pkg = db.query(CreditPackage).first()

    if not pkg:
        pytest.skip("No packages in test database")

    # Test: hours too large
    response = client.put(
        f"/api/admin/credits/packages/{pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "display_name": "Test",
            "hours": 200.00,  # Over 100 limit
            "price_usd": 50.00,
            "sort_order": 1,
            "is_active": True
        }
    )
    assert response.status_code == 422  # Validation error

    # Test: price too low
    response = client.put(
        f"/api/admin/credits/packages/{pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "display_name": "Test",
            "hours": 1.00,
            "price_usd": 0.00,  # Below 0.01 minimum
            "sort_order": 1,
            "is_active": True
        }
    )
    assert response.status_code == 422  # Validation error


def test_package_not_found(client, db, admin_token):
    """Test updating non-existent package"""
    response = client.put(
        "/api/admin/credits/packages/99999",  # Non-existent ID
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "display_name": "Test",
            "hours": 1.00,
            "price_usd": 5.00,
            "sort_order": 1,
            "is_active": True
        }
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
