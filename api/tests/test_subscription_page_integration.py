"""
Integration tests for US-002: User Subscription Page
Tests the backend APIs that power the subscription page
"""
import pytest
from fastapi.testclient import TestClient


@pytest.mark.integration
def test_get_subscription_endpoint(client: TestClient, test_user_token: str):
    """Test GET /api/subscription returns current user subscription"""
    response = client.get(
        "/api/subscription",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "tier_id" in data
    assert "tier_name" in data
    assert "monthly_quota_seconds" in data
    assert "status" in data

    # New user should be on Free tier
    assert data["tier_id"] == 1
    assert data["tier_name"] == "Free"
    assert data["monthly_quota_seconds"] == 600  # 10 minutes


@pytest.mark.integration
def test_get_quota_status_endpoint(client: TestClient, test_user_token: str):
    """Test GET /api/quota/status returns current quota"""
    response = client.get(
        "/api/quota/status",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "quota_used_seconds" in data
    assert "quota_available_seconds" in data
    assert "bonus_credits_seconds" in data
    assert "billing_period_end" in data

    # New user should have zero usage
    assert data["quota_used_seconds"] == 0
    assert data["quota_available_seconds"] == 600  # Free tier: 10 minutes
    assert data["bonus_credits_seconds"] == 0


@pytest.mark.integration
def test_get_credit_packages_endpoint(client: TestClient, test_user_token: str):
    """Test GET /api/payments/credit-packages returns available packages"""
    response = client.get(
        "/api/payments/credit-packages",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )

    assert response.status_code == 200
    data = response.json()

    # Should return packages list
    assert "packages" in data
    packages = data["packages"]

    # Should have 4 packages (from migration 016)
    assert len(packages) >= 4

    # Verify first package structure
    package = packages[0]
    assert "id" in package
    assert "credit_hours" in package
    assert "price_usd" in package
    assert "discount_pct" in package

    # Verify pricing (1hr package should be $5)
    one_hour_pkg = next(p for p in packages if p["credit_hours"] == 1)
    assert one_hour_pkg["price_usd"] == 5.0


@pytest.mark.integration
def test_create_checkout_session_subscription(client: TestClient, test_user_token: str):
    """Test POST /api/payments/stripe/create-checkout for subscription"""
    response = client.post(
        "/api/payments/stripe/create-checkout",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "product_type": "subscription",
            "tier_id": 2  # Plus tier
        }
    )

    # Should succeed (or fail with Stripe key not configured in test env)
    # In test mode, we may not have STRIPE_SECRET_KEY
    if response.status_code == 200:
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data
        assert data["checkout_url"].startswith("https://")
    elif response.status_code == 503:
        # Stripe not configured in test environment - acceptable
        assert "Stripe" in response.json()["detail"]
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")


@pytest.mark.integration
def test_create_checkout_session_credits(client: TestClient, test_user_token: str):
    """Test POST /api/payments/stripe/create-checkout for credits"""
    response = client.post(
        "/api/payments/stripe/create-checkout",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "product_type": "credits",
            "tier_id": 1  # 1hr package
        }
    )

    # Same logic as subscription test
    if response.status_code == 200:
        data = response.json()
        assert "checkout_url" in data
        assert "session_id" in data
    elif response.status_code == 503:
        # Stripe not configured - acceptable
        assert "Stripe" in response.json()["detail"]
    else:
        pytest.fail(f"Unexpected status code: {response.status_code}")


@pytest.mark.integration
def test_create_checkout_invalid_tier(client: TestClient, test_user_token: str):
    """Test create checkout with invalid tier ID"""
    response = client.post(
        "/api/payments/stripe/create-checkout",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "product_type": "subscription",
            "tier_id": 999  # Invalid tier
        }
    )

    # Should return 404 or 400
    assert response.status_code in [400, 404]


@pytest.mark.integration
def test_create_checkout_invalid_product_type(client: TestClient, test_user_token: str):
    """Test create checkout with invalid product type"""
    response = client.post(
        "/api/payments/stripe/create-checkout",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={
            "product_type": "invalid",
            "tier_id": 2
        }
    )

    # Should return 422 (validation error)
    assert response.status_code == 422


@pytest.mark.integration
def test_endpoints_require_authentication(client: TestClient):
    """Test that all endpoints require valid auth token"""
    endpoints = [
        ("GET", "/api/subscription"),
        ("GET", "/api/quota/status"),
        ("GET", "/api/payments/credit-packages"),
        ("POST", "/api/payments/stripe/create-checkout"),
    ]

    for method, path in endpoints:
        if method == "GET":
            response = client.get(path)
        else:
            response = client.post(path, json={})

        # Should return 401 Unauthorized
        assert response.status_code == 401


@pytest.mark.integration
def test_quota_calculation_accuracy(client: TestClient, test_user_token: str, db_session):
    """Test that quota calculations are accurate"""
    # Get initial quota
    response = client.get(
        "/api/quota/status",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert response.status_code == 200
    initial_quota = response.json()

    # Simulate usage by updating quota_used in database
    from api.models import UserSubscription
    user_id = 1  # Assuming test user has ID 1

    subscription = db_session.query(UserSubscription).filter_by(user_id=user_id).first()
    if subscription:
        subscription.quota_used_seconds = 300  # Use 5 minutes
        db_session.commit()

        # Verify updated quota
        response = client.get(
            "/api/quota/status",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 200
        updated_quota = response.json()

        assert updated_quota["quota_used_seconds"] == 300
        assert updated_quota["quota_available_seconds"] == initial_quota["quota_available_seconds"]


@pytest.mark.integration
def test_subscription_page_full_flow(client: TestClient, test_user_token: str):
    """
    Test complete user flow:
    1. View subscription page (fetch all data)
    2. Verify Free tier
    3. Attempt upgrade to Plus (will fail without Stripe in test)
    """
    # Step 1: Fetch subscription
    sub_response = client.get(
        "/api/subscription",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert sub_response.status_code == 200
    assert sub_response.json()["tier_name"] == "Free"

    # Step 2: Fetch quota status
    quota_response = client.get(
        "/api/quota/status",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert quota_response.status_code == 200

    # Step 3: Fetch credit packages
    packages_response = client.get(
        "/api/payments/credit-packages",
        headers={"Authorization": f"Bearer {test_user_token}"}
    )
    assert packages_response.status_code == 200
    assert len(packages_response.json()["packages"]) >= 4

    # Step 4: Attempt to create checkout (will fail in test without Stripe)
    checkout_response = client.post(
        "/api/payments/stripe/create-checkout",
        headers={"Authorization": f"Bearer {test_user_token}"},
        json={"product_type": "subscription", "tier_id": 2}
    )
    # Accept either success (if Stripe configured) or 503 (if not)
    assert checkout_response.status_code in [200, 503]
