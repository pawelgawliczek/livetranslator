"""
Integration tests for US-012: Credit Package Management
Tests admin endpoints for managing credit packages and purchase history.
"""
import pytest
from fastapi.testclient import TestClient
from decimal import Decimal
from datetime import datetime, timedelta
import json


def test_get_credit_packages_admin(client: TestClient, admin_token: str, db_session):
    """Test GET /api/admin/credit-packages - Admin view with purchase counts"""
    # Create test packages
    from api.models import CreditPackage

    pkg1 = CreditPackage(
        package_name="test_1hr",
        display_name="1 Hour Test",
        hours=Decimal("1.0"),
        price_usd=Decimal("10.00"),
        discount_percent=Decimal("0"),
        is_active=True,
        sort_order=1
    )
    pkg2 = CreditPackage(
        package_name="test_4hr",
        display_name="4 Hours Test",
        hours=Decimal("4.0"),
        price_usd=Decimal("35.00"),
        discount_percent=Decimal("12.5"),
        is_active=False,
        sort_order=2
    )

    db_session.add(pkg1)
    db_session.add(pkg2)
    db_session.commit()

    # Test endpoint
    response = client.get(
        "/api/admin/credit-packages",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "packages" in data
    assert len(data["packages"]) >= 2

    # Verify package data structure
    pkg_data = next((p for p in data["packages"] if p["package_name"] == "test_1hr"), None)
    assert pkg_data is not None
    assert pkg_data["display_name"] == "1 Hour Test"
    assert pkg_data["hours"] == 1.0
    assert pkg_data["price_usd"] == 10.0
    assert pkg_data["discount_percent"] == 0.0
    assert pkg_data["is_active"] is True
    assert "total_purchases" in pkg_data

    # Cleanup
    db_session.delete(pkg1)
    db_session.delete(pkg2)
    db_session.commit()


def test_get_credit_packages_requires_admin(client: TestClient, user_token: str):
    """Test that regular users cannot access admin credit packages endpoint"""
    response = client.get(
        "/api/admin/credit-packages",
        headers={"Authorization": f"Bearer {user_token}"}
    )

    assert response.status_code == 403


def test_update_credit_package(client: TestClient, admin_token: str, db_session):
    """Test PUT /api/admin/credit-packages/{id} - Update package details"""
    from api.models import CreditPackage

    # Create test package
    pkg = CreditPackage(
        package_name="test_update",
        display_name="Update Test",
        hours=Decimal("1.0"),
        price_usd=Decimal("10.00"),
        discount_percent=Decimal("0"),
        is_active=True,
        sort_order=99
    )
    db_session.add(pkg)
    db_session.commit()
    db_session.refresh(pkg)

    # Update package
    response = client.put(
        f"/api/admin/credit-packages/{pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "hours": 2.0,
            "price_usd": 18.00,
            "discount_percent": 10.0,
            "is_active": False
        }
    )

    assert response.status_code == 200
    data = response.json()
    assert data["package"]["hours"] == 2.0
    assert data["package"]["price_usd"] == 18.0
    assert data["package"]["discount_percent"] == 10.0
    assert data["package"]["is_active"] is False

    # Verify database was updated
    db_session.refresh(pkg)
    assert pkg.hours == Decimal("2.0")
    assert pkg.price_usd == Decimal("18.00")
    assert pkg.discount_percent == Decimal("10.0")
    assert pkg.is_active is False

    # Cleanup
    db_session.delete(pkg)
    db_session.commit()


def test_update_credit_package_validation(client: TestClient, admin_token: str, db_session):
    """Test validation on package updates"""
    from api.models import CreditPackage

    pkg = CreditPackage(
        package_name="test_validation",
        display_name="Validation Test",
        hours=Decimal("1.0"),
        price_usd=Decimal("10.00"),
        discount_percent=Decimal("0"),
        is_active=True,
        sort_order=99
    )
    db_session.add(pkg)
    db_session.commit()
    db_session.refresh(pkg)

    # Test negative hours
    response = client.put(
        f"/api/admin/credit-packages/{pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"hours": -1.0}
    )
    assert response.status_code == 400
    assert "must be positive" in response.json()["detail"].lower()

    # Test negative price
    response = client.put(
        f"/api/admin/credit-packages/{pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"price_usd": -10.0}
    )
    assert response.status_code == 400
    assert "cannot be negative" in response.json()["detail"].lower()

    # Test invalid discount
    response = client.put(
        f"/api/admin/credit-packages/{pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"discount_percent": 150.0}
    )
    assert response.status_code == 400
    assert "between 0 and 100" in response.json()["detail"].lower()

    # Test non-existent package
    response = client.put(
        f"/api/admin/credit-packages/999999",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"hours": 2.0}
    )
    assert response.status_code == 404

    # Cleanup
    db_session.delete(pkg)
    db_session.commit()


def test_get_credit_purchases(client: TestClient, admin_token: str, db_session, test_user):
    """Test GET /api/admin/credit-purchases - Purchase history with filters"""
    from api.models import PaymentTransaction, CreditPackage

    # Create test package
    pkg = CreditPackage(
        package_name="test_purchase",
        display_name="Purchase Test",
        hours=Decimal("1.0"),
        price_usd=Decimal("10.00"),
        discount_percent=Decimal("0"),
        is_active=True,
        sort_order=99
    )
    db_session.add(pkg)
    db_session.commit()
    db_session.refresh(pkg)

    # Create test transactions
    tx1 = PaymentTransaction(
        user_id=test_user.id,
        platform="stripe",
        transaction_type="credit_purchase",
        amount_usd=Decimal("10.00"),
        stripe_payment_intent_id="pi_test_123",
        status="completed",
        transaction_metadata={"package_id": pkg.id},
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )

    tx2 = PaymentTransaction(
        user_id=test_user.id,
        platform="apple",
        transaction_type="credit_purchase",
        amount_usd=Decimal("10.00"),
        apple_transaction_id="1000000123456789",
        status="completed",
        transaction_metadata={"package_id": pkg.id},
        created_at=datetime.utcnow() - timedelta(days=1),
        completed_at=datetime.utcnow() - timedelta(days=1)
    )

    db_session.add(tx1)
    db_session.add(tx2)
    db_session.commit()

    # Test basic query
    response = client.get(
        "/api/admin/credit-purchases",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "purchases" in data
    assert "total" in data
    assert len(data["purchases"]) >= 2

    # Test filter by user email
    response = client.get(
        f"/api/admin/credit-purchases?user_email={test_user.email}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert all(p["user_email"] == test_user.email for p in data["purchases"])

    # Test filter by package
    response = client.get(
        f"/api/admin/credit-purchases?package_id={pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["purchases"]) >= 2

    # Test filter by platform
    response = client.get(
        "/api/admin/credit-purchases?platform=stripe",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    stripe_purchases = [p for p in data["purchases"] if p["transaction_id"] == "pi_test_123"]
    assert len(stripe_purchases) >= 1

    # Test filter by status
    response = client.get(
        "/api/admin/credit-purchases?status=completed",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert all(p["status"] == "completed" for p in data["purchases"])

    # Test pagination
    response = client.get(
        "/api/admin/credit-purchases?limit=1&offset=0",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data["purchases"]) == 1
    assert data["limit"] == 1
    assert data["offset"] == 0

    # Cleanup
    db_session.delete(tx1)
    db_session.delete(tx2)
    db_session.delete(pkg)
    db_session.commit()


def test_export_credit_purchases_csv(client: TestClient, admin_token: str, db_session, test_user):
    """Test GET /api/admin/credit-purchases/export - CSV export"""
    from api.models import PaymentTransaction, CreditPackage

    # Create test package
    pkg = CreditPackage(
        package_name="test_export",
        display_name="Export Test",
        hours=Decimal("1.0"),
        price_usd=Decimal("10.00"),
        discount_percent=Decimal("0"),
        is_active=True,
        sort_order=99
    )
    db_session.add(pkg)
    db_session.commit()
    db_session.refresh(pkg)

    # Create test transaction
    tx = PaymentTransaction(
        user_id=test_user.id,
        platform="stripe",
        transaction_type="credit_purchase",
        amount_usd=Decimal("10.00"),
        stripe_payment_intent_id="pi_export_test",
        status="completed",
        transaction_metadata={"package_id": pkg.id},
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db_session.add(tx)
    db_session.commit()

    # Test CSV export
    response = client.get(
        "/api/admin/credit-purchases/export",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]

    # Verify CSV content
    csv_content = response.text
    assert "Transaction ID" in csv_content
    assert "User Email" in csv_content
    assert "Package" in csv_content
    assert test_user.email in csv_content

    # Test export with filters
    response = client.get(
        f"/api/admin/credit-purchases/export?user_email={test_user.email}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200
    csv_content = response.text
    assert test_user.email in csv_content

    # Cleanup
    db_session.delete(tx)
    db_session.delete(pkg)
    db_session.commit()


def test_credit_package_audit_logging(client: TestClient, admin_token: str, db_session, admin_user):
    """Test that package updates are logged in admin_audit_log"""
    from api.models import CreditPackage
    from sqlalchemy import text

    # Create test package
    pkg = CreditPackage(
        package_name="test_audit",
        display_name="Audit Test",
        hours=Decimal("1.0"),
        price_usd=Decimal("10.00"),
        discount_percent=Decimal("0"),
        is_active=True,
        sort_order=99
    )
    db_session.add(pkg)
    db_session.commit()
    db_session.refresh(pkg)

    # Update package
    response = client.put(
        f"/api/admin/credit-packages/{pkg.id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"hours": 2.0}
    )

    assert response.status_code == 200

    # Check audit log
    result = db_session.execute(
        text("""
            SELECT action, details FROM admin_audit_log
            WHERE admin_id = :admin_id
            AND action = 'update_credit_package'
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"admin_id": admin_user.id}
    ).fetchone()

    assert result is not None
    assert result[0] == "update_credit_package"
    details = json.loads(result[1])
    assert details["package_id"] == pkg.id
    assert "updates" in details
    assert details["updates"]["hours"] == 2.0

    # Cleanup
    db_session.delete(pkg)
    db_session.commit()


def test_export_audit_logging(client: TestClient, admin_token: str, db_session, admin_user):
    """Test that CSV exports are logged in admin_audit_log"""
    from sqlalchemy import text

    # Export CSV
    response = client.get(
        "/api/admin/credit-purchases/export",
        headers={"Authorization": f"Bearer {admin_token}"}
    )

    assert response.status_code == 200

    # Check audit log
    result = db_session.execute(
        text("""
            SELECT action, details FROM admin_audit_log
            WHERE admin_id = :admin_id
            AND action = 'export_credit_purchases'
            ORDER BY created_at DESC
            LIMIT 1
        """),
        {"admin_id": admin_user.id}
    ).fetchone()

    assert result is not None
    assert result[0] == "export_credit_purchases"
    details = json.loads(result[1])
    assert "row_count" in details
    assert "filters" in details
