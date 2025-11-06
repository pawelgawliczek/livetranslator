"""
Integration tests for payment endpoints (Stripe + Apple IAP).

Tests security features:
- Stripe webhook signature verification
- Apple duplicate transaction prevention
- Apple bundle_id validation
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from decimal import Decimal
import time

# Import real stripe for exception classes
try:
    import stripe as real_stripe
except ImportError:
    real_stripe = None


class TestStripeIntegration:
    """Test Stripe payment integration"""

    def test_create_checkout_subscription_requires_auth(self, test_client):
        """Test that Stripe checkout requires authentication"""
        response = test_client.post(
            "/api/payments/stripe/create-checkout",
            json={"product_type": "subscription", "tier_id": 2}
        )
        assert response.status_code == 401

    def test_create_checkout_subscription_missing_tier_id(self, test_client, test_user_token):
        """Test validation: subscription requires tier_id"""
        response = test_client.post(
            "/api/payments/stripe/create-checkout",
            json={"product_type": "subscription"},
            headers={"Authorization": f"Bearer {test_user_token}", "X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 400
        assert "tier_id required" in response.json()["detail"]

    def test_create_checkout_credits_missing_package_id(self, test_client, test_user_token):
        """Test validation: credit purchase requires package_id"""
        response = test_client.post(
            "/api/payments/stripe/create-checkout",
            json={"product_type": "credits"},
            headers={"Authorization": f"Bearer {test_user_token}", "X-Requested-With": "XMLHttpRequest"}
        )
        assert response.status_code == 400
        assert "package_id required" in response.json()["detail"]

    @patch('api.routers.payments.stripe')
    def test_stripe_webhook_missing_signature(self, mock_stripe, test_client):
        """Test webhook signature verification (security)"""
        response = test_client.post(
            "/api/payments/stripe/webhook",
            json={"type": "checkout.session.completed"}
        )
        assert response.status_code == 400
        assert "Missing Stripe-Signature" in response.json()["detail"]

    @patch('api.routers.payments.stripe')
    def test_stripe_webhook_invalid_signature(self, mock_stripe):
        """Test webhook rejects invalid signature (security)"""
        # Use real Stripe exception class for proper exception handling
        if not real_stripe:
            pytest.skip("Stripe not available")

        mock_stripe.error.SignatureVerificationError = real_stripe.error.SignatureVerificationError
        mock_stripe.Webhook.construct_event.side_effect = real_stripe.error.SignatureVerificationError(
            "Invalid signature", "sig_header"
        )

        # Create test client AFTER patch is applied
        from fastapi.testclient import TestClient
        from api.main import app
        test_client = TestClient(app)

        response = test_client.post(
            "/api/payments/stripe/webhook",
            headers={"stripe-signature": "invalid_signature"},
            json={"type": "checkout.session.completed"}
        )
        assert response.status_code == 400
        assert "Invalid signature" in response.json()["detail"]

    @patch('api.routers.payments.stripe')
    def test_stripe_webhook_idempotency(self, mock_stripe, test_client, test_db):
        """Test webhook idempotency (prevent duplicate processing)"""
        # Mock Stripe webhook verification
        mock_event = {
            "id": "evt_test_12345",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "metadata": {"user_id": "1", "product_type": "subscription", "tier_id": "2"},
                    "subscription": "sub_123",
                    "customer": "cus_123",
                    "amount_total": 2900,
                    "payment_intent": "pi_123"
                }
            }
        }
        mock_stripe.Webhook.construct_event.return_value = mock_event

        # First webhook call should succeed
        response1 = test_client.post(
            "/api/payments/stripe/webhook",
            headers={"stripe-signature": "valid_signature"},
            json=mock_event
        )
        assert response1.status_code == 200

        # Second webhook call with same event_id should be deduplicated
        response2 = test_client.post(
            "/api/payments/stripe/webhook",
            headers={"stripe-signature": "valid_signature"},
            json=mock_event
        )
        assert response2.status_code == 200
        assert response2.json()["status"] == "duplicate"


class TestAppleIAP:
    """Test Apple In-App Purchase integration"""

    def test_verify_receipt_requires_auth(self, test_client):
        """Test that Apple receipt verification requires authentication"""
        response = test_client.post(
            "/api/payments/apple/verify",
            json={
                "receipt_data": "base64_receipt",
                "transaction_id": "1000000123456789",
                "original_transaction_id": "1000000123456789",
                "product_id": "com.livetranslator.plus.monthly"
            }
        )
        assert response.status_code == 401

    def test_duplicate_transaction_prevention(self, test_client, test_user_token, test_db):
        """Test duplicate transaction_id rejection (security: prevent fraud)"""
        from api.models import PaymentTransaction, User
        from sqlalchemy import select
        import jwt

        # Generate unique transaction ID for this test
        unique_tx_id = f"1000000{int(time.time() * 1000)}"

        # Decode token to get user_id
        decoded = jwt.decode(test_user_token, options={"verify_signature": False})
        user_id = int(decoded["sub"])

        # Create existing payment transaction
        existing_tx = PaymentTransaction(
            user_id=user_id,
            platform='apple',
            transaction_type='subscription',
            amount_usd=Decimal('29.00'),
            currency='USD',
            apple_transaction_id=unique_tx_id,
            apple_original_transaction_id=unique_tx_id,
            apple_product_id='com.livetranslator.plus.monthly',
            status='completed',
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(existing_tx)
        test_db.commit()

        # Try to submit duplicate transaction
        response = test_client.post(
            "/api/payments/apple/verify",
            json={
                "receipt_data": "base64_receipt",
                "transaction_id": unique_tx_id,
                "original_transaction_id": unique_tx_id,
                "product_id": "com.livetranslator.plus.monthly"
            },
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 409
        assert "already processed" in response.json()["detail"]

    @patch('api.billing_api.verify_apple_receipt_with_apple')
    def test_bundle_id_validation(self, mock_verify, test_client, test_user_token):
        """Test bundle_id spoofing prevention (security)"""
        # Generate unique transaction ID for this test
        unique_tx_id = f"1000000{int(time.time() * 1000) + 1}"

        # Mock Apple response with wrong bundle_id
        mock_verify.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "com.malicious.app"  # Wrong bundle_id
            },
            "latest_receipt_info": [
                {
                    "product_id": "com.livetranslator.plus.monthly",
                    "transaction_id": unique_tx_id,
                    "original_transaction_id": unique_tx_id
                }
            ]
        }

        response = test_client.post(
            "/api/payments/apple/verify",
            json={
                "receipt_data": "base64_receipt",
                "transaction_id": unique_tx_id,
                "original_transaction_id": unique_tx_id,
                "product_id": "com.livetranslator.plus.monthly"
            },
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 403
        assert "Bundle ID mismatch" in response.json()["detail"]

    @patch('api.billing_api.verify_apple_receipt_with_apple')
    def test_apple_subscription_success(self, mock_verify, test_client, test_user_token, test_db):
        """Test successful Apple subscription verification"""
        # Generate unique transaction ID for this test
        unique_tx_id = f"1000000{int(time.time() * 1000) + 2}"

        # Mock Apple response
        mock_verify.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "com.livetranslator.ios"
            },
            "latest_receipt_info": [
                {
                    "product_id": "com.livetranslator.plus.monthly",
                    "transaction_id": unique_tx_id,
                    "original_transaction_id": unique_tx_id,
                    "purchase_date_ms": str(int(datetime.utcnow().timestamp() * 1000)),
                    "expires_date_ms": str(int((datetime.utcnow() + timedelta(days=30)).timestamp() * 1000))
                }
            ]
        }

        response = test_client.post(
            "/api/payments/apple/verify",
            json={
                "receipt_data": "base64_receipt",
                "transaction_id": unique_tx_id,
                "original_transaction_id": unique_tx_id,
                "product_id": "com.livetranslator.plus.monthly"
            },
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["tier_updated"] is True
        assert data["tier"] == "plus"

    @patch('api.billing_api.verify_apple_receipt_with_apple')
    def test_apple_credits_success(self, mock_verify, test_client, test_user_token, test_db):
        """Test successful Apple credit purchase"""
        # Generate unique transaction ID for this test
        unique_tx_id = f"1000000{int(time.time() * 1000) + 3}"

        # Mock Apple response
        mock_verify.return_value = {
            "status": 0,
            "receipt": {
                "bundle_id": "com.livetranslator.ios",
                "in_app": [
                    {
                        "product_id": "com.livetranslator.credits.4hr",
                        "transaction_id": unique_tx_id,
                        "original_transaction_id": unique_tx_id
                    }
                ]
            },
            "latest_receipt_info": [
                {
                    "product_id": "com.livetranslator.credits.4hr",
                    "transaction_id": unique_tx_id,
                    "original_transaction_id": unique_tx_id
                }
            ]
        }

        response = test_client.post(
            "/api/payments/apple/verify",
            json={
                "receipt_data": "base64_receipt",
                "transaction_id": unique_tx_id,
                "original_transaction_id": unique_tx_id,
                "product_id": "com.livetranslator.credits.4hr"
            },
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["credits_granted"] == 4
        assert "4 hours" in data["message"]

    def test_apple_webhook_missing_secret(self, test_client):
        """Test Apple webhook validates shared secret (security)"""
        response = test_client.post(
            "/api/payments/apple/webhook",
            json={
                "notification_type": "DID_RENEW",
                "password": "wrong_secret",
                "unified_receipt": {}
            }
        )
        assert response.status_code == 403
        assert "Invalid shared secret" in response.json()["detail"]


class TestPaymentHistory:
    """Test payment history endpoint"""

    def test_payment_history_requires_auth(self, test_client):
        """Test payment history requires authentication"""
        response = test_client.get("/api/payments/history")
        assert response.status_code == 401

    def test_payment_history_empty(self, test_client, test_user_token):
        """Test payment history with no transactions"""
        response = test_client.get(
            "/api/payments/history",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "payments" in data
        assert isinstance(data["payments"], list)
        assert data["total_spent_usd"] == 0.0

    def test_payment_history_with_transactions(self, test_client, test_user_token, test_db):
        """Test payment history returns user's transactions"""
        from api.models import PaymentTransaction
        import jwt

        # Generate unique transaction ID for this test
        unique_tx_id = f"1000000{int(time.time() * 1000) + 4}"

        # Decode token to get user_id
        decoded = jwt.decode(test_user_token, options={"verify_signature": False})
        user_id = int(decoded["sub"])

        # Create test transactions
        tx1 = PaymentTransaction(
            user_id=user_id,
            platform='stripe',
            transaction_type='subscription',
            amount_usd=Decimal('29.00'),
            currency='USD',
            stripe_payment_intent_id=f'pi_{int(time.time())}',
            status='completed',
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        tx2 = PaymentTransaction(
            user_id=user_id,
            platform='apple',
            transaction_type='credit_purchase',
            amount_usd=Decimal('19.00'),
            currency='USD',
            apple_transaction_id=unique_tx_id,
            apple_product_id='com.livetranslator.credits.4hr',
            status='completed',
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        test_db.add(tx1)
        test_db.add(tx2)
        test_db.commit()

        response = test_client.get(
            "/api/payments/history",
            headers={"Authorization": f"Bearer {test_user_token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["payments"]) == 2
        assert data["total_spent_usd"] == 48.0
