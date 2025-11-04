"""
Payment integration for Stripe (Web) and Apple IAP (iOS).

Security features:
- Stripe webhook signature verification (prevent spoofing)
- Apple receipt duplicate transaction check (prevent fraud)
- Apple bundle_id validation (prevent replay attacks)
- Idempotent webhook processing (Redis deduplication)
"""
import os
import httpx
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..db import SessionLocal
from ..models import User, UserSubscription, SubscriptionTier, PaymentTransaction, CreditPackage, QuotaTransaction
from ..settings import settings

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Environment variables
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
APPLE_SHARED_SECRET = os.getenv("APPLE_SHARED_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", f"https://{settings.LT_DOMAIN}")
EXPECTED_BUNDLE_ID = os.getenv("APPLE_BUNDLE_ID", "com.livetranslator.ios")

# Import stripe only if configured
try:
    import stripe
    stripe.api_key = STRIPE_SECRET_KEY
except ImportError:
    stripe = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# Request/Response Models
# ============================================================================

class StripeCheckoutRequest(BaseModel):
    product_type: str  # 'subscription' or 'credits'
    tier_id: Optional[int] = None  # For subscriptions (Plus/Pro)
    package_id: Optional[int] = None  # For credit packages


class AppleReceiptRequest(BaseModel):
    receipt_data: str
    transaction_id: str
    original_transaction_id: str
    product_id: str


# ============================================================================
# Stripe Integration
# ============================================================================

@router.post("/stripe/create-checkout")
async def create_stripe_checkout(
    request: StripeCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe Checkout session for subscription or credit purchase.

    Returns:
    - checkout_url: URL to redirect user to Stripe payment page
    - session_id: Stripe session ID for tracking
    """
    if not stripe or not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    # 1. Get Stripe price ID from database
    if request.product_type == 'subscription':
        if not request.tier_id:
            raise HTTPException(400, "tier_id required for subscription")

        tier = db.scalar(select(SubscriptionTier).where(SubscriptionTier.id == request.tier_id))
        if not tier:
            raise HTTPException(404, "Tier not found")

        if not tier.stripe_price_id:
            raise HTTPException(400, f"Tier {tier.tier_name} does not support Stripe payments")

        price_id = tier.stripe_price_id
        mode = 'subscription'

    elif request.product_type == 'credits':
        if not request.package_id:
            raise HTTPException(400, "package_id required for credit purchase")

        package = db.scalar(select(CreditPackage).where(CreditPackage.id == request.package_id))
        if not package:
            raise HTTPException(404, "Credit package not found")

        if not package.stripe_price_id:
            raise HTTPException(400, f"Package {package.package_name} does not support Stripe payments")

        price_id = package.stripe_price_id
        mode = 'payment'
    else:
        raise HTTPException(400, "product_type must be 'subscription' or 'credits'")

    # 2. Create Stripe Checkout session
    try:
        session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            mode=mode,
            line_items=[{
                'price': price_id,
                'quantity': 1
            }],
            success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/billing/cancel",
            metadata={
                'user_id': str(current_user.id),
                'product_type': request.product_type,
                'tier_id': str(request.tier_id) if request.tier_id else '',
                'package_id': str(request.package_id) if request.package_id else ''
            }
        )

        return {
            "checkout_url": session.url,
            "session_id": session.id
        }
    except stripe.error.StripeError as e:
        raise HTTPException(502, f"Stripe error: {str(e)}")


@router.post("/stripe/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook handler (PUBLIC endpoint with signature verification).

    Events handled:
    - checkout.session.completed: Payment successful
    - customer.subscription.updated: Subscription changed
    - customer.subscription.deleted: Subscription canceled
    - invoice.payment_failed: Payment failed
    """
    if not stripe or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(503, "Stripe not configured")

    # Get raw body and signature
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        raise HTTPException(400, "Missing Stripe-Signature header")

    # 1. Verify webhook signature (SECURITY: Prevent spoofing)
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(400, "Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    # 2. Idempotency check (prevent duplicate processing)
    from redis.asyncio import Redis
    redis = Redis.from_url(str(settings.LT_REDIS_URL))
    event_id = event['id']

    if await redis.get(f"stripe:event:{event_id}"):
        print(f"[Stripe Webhook] Event {event_id} already processed, skipping")
        return {"status": "duplicate"}

    # Mark as processed (TTL 7 days)
    await redis.setex(f"stripe:event:{event_id}", 7 * 86400, "1")

    # 3. Handle event types
    event_type = event['type']
    event_data = event['data']['object']

    if event_type == 'checkout.session.completed':
        await handle_checkout_completed(event_data, db)
    elif event_type == 'customer.subscription.updated':
        await handle_subscription_updated(event_data, db)
    elif event_type == 'invoice.payment_failed':
        await handle_payment_failed(event_data, db)
    elif event_type == 'customer.subscription.deleted':
        await handle_subscription_deleted(event_data, db)

    return {"status": "success"}


async def handle_checkout_completed(session: dict, db: Session):
    """Process successful Stripe payment"""
    user_id = int(session['metadata']['user_id'])
    product_type = session['metadata']['product_type']

    user = db.get(User, user_id)
    if not user:
        print(f"[Stripe] User {user_id} not found")
        return

    if product_type == 'subscription':
        tier_id = int(session['metadata']['tier_id'])

        # Get or create user subscription
        subscription = db.scalar(
            select(UserSubscription).where(UserSubscription.user_id == user_id)
        )

        if not subscription:
            subscription = UserSubscription(
                user_id=user_id,
                tier_id=tier_id,
                billing_period_start=datetime.utcnow(),
                billing_period_end=datetime.utcnow() + timedelta(days=30),
                status='active'
            )
            db.add(subscription)
        else:
            subscription.tier_id = tier_id
            subscription.stripe_subscription_id = session.get('subscription')
            subscription.stripe_customer_id = session.get('customer')
            subscription.billing_period_start = datetime.utcnow()
            subscription.billing_period_end = datetime.utcnow() + timedelta(days=30)
            subscription.status = 'active'

        db.commit()

    elif product_type == 'credits':
        package_id = int(session['metadata']['package_id'])
        package = db.get(CreditPackage, package_id)

        if package:
            seconds = int(float(package.hours) * 3600)

            # Add bonus credits
            subscription = db.scalar(
                select(UserSubscription).where(UserSubscription.user_id == user_id)
            )

            if subscription:
                subscription.bonus_credits_seconds += seconds
                db.commit()

                # Record quota transaction
                quota_tx = QuotaTransaction(
                    user_id=user_id,
                    transaction_type='purchase',
                    amount_seconds=seconds,
                    quota_type='bonus',
                    description=f"Purchased {package.hours} hours credit package"
                )
                db.add(quota_tx)
                db.commit()

    # Record payment transaction
    payment_tx = PaymentTransaction(
        user_id=user_id,
        platform='stripe',
        transaction_type=product_type,
        amount_usd=Decimal(session['amount_total']) / 100,
        currency='USD',
        stripe_payment_intent_id=session.get('payment_intent'),
        status='completed',
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db.add(payment_tx)
    db.commit()

    print(f"[Stripe] Checkout completed for user {user_id}, type={product_type}")


async def handle_subscription_updated(subscription_data: dict, db: Session):
    """Handle subscription renewal/update"""
    stripe_subscription_id = subscription_data['id']

    subscription = db.scalar(
        select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_subscription_id
        )
    )

    if subscription:
        # Update billing period
        current_period_end = datetime.fromtimestamp(subscription_data['current_period_end'])
        subscription.billing_period_end = current_period_end
        subscription.status = 'active'
        db.commit()
        print(f"[Stripe] Subscription {stripe_subscription_id} updated")


async def handle_payment_failed(invoice_data: dict, db: Session):
    """Handle failed payment"""
    customer_id = invoice_data['customer']

    subscription = db.scalar(
        select(UserSubscription).where(UserSubscription.stripe_customer_id == customer_id)
    )

    if subscription:
        subscription.status = 'past_due'
        db.commit()
        print(f"[Stripe] Payment failed for user {subscription.user_id}")


async def handle_subscription_deleted(subscription_data: dict, db: Session):
    """Handle subscription cancellation"""
    stripe_subscription_id = subscription_data['id']

    subscription = db.scalar(
        select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_subscription_id
        )
    )

    if subscription:
        subscription.status = 'canceled'
        subscription.auto_renew = False
        db.commit()
        print(f"[Stripe] Subscription {stripe_subscription_id} canceled")


# ============================================================================
# Credit Packages (User Endpoint)
# ============================================================================

@router.get("/credit-packages")
async def get_credit_packages(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get active credit packages (public user view).

    Returns only is_active=true packages.
    Does not expose Stripe/Apple IDs (security).
    """
    packages = db.scalars(
        select(CreditPackage)
        .where(CreditPackage.is_active == True)
        .order_by(CreditPackage.sort_order, CreditPackage.id)
    ).all()

    return {
        "packages": [
            {
                "id": pkg.id,
                "display_name": pkg.display_name,
                "hours": float(pkg.hours),
                "price_usd": float(pkg.price_usd),
                "discount_percent": float(pkg.discount_percent),
                "sort_order": pkg.sort_order
            }
            for pkg in packages
        ]
    }


# ============================================================================
# Apple IAP Integration
# ============================================================================

APPLE_PRODUCTION_URL = "https://buy.itunes.apple.com/verifyReceipt"
APPLE_SANDBOX_URL = "https://sandbox.itunes.apple.com/verifyReceipt"


class AppleReceiptError(Exception):
    pass


async def verify_apple_receipt_with_apple(receipt_data: str) -> dict:
    """
    Verify receipt with Apple's verifyReceipt API.

    Returns verified transaction data.
    """
    if not APPLE_SHARED_SECRET:
        raise AppleReceiptError("Apple shared secret not configured")

    async with httpx.AsyncClient(timeout=10.0) as client:
        payload = {
            "receipt-data": receipt_data,
            "password": APPLE_SHARED_SECRET,
            "exclude-old-transactions": True
        }

        # Try production first
        response = await client.post(APPLE_PRODUCTION_URL, json=payload)
        data = response.json()

        # If sandbox receipt sent to production, retry with sandbox
        if data.get("status") == 21007:
            response = await client.post(APPLE_SANDBOX_URL, json=payload)
            data = response.json()

    # Check status code
    if data.get("status") != 0:
        status_messages = {
            21000: "App Store could not read receipt",
            21002: "Receipt data malformed",
            21003: "Receipt authentication failed",
            21004: "Shared secret mismatch",
            21005: "Receipt server unavailable",
            21006: "Receipt valid but subscription expired",
            21007: "Sandbox receipt sent to production",
            21008: "Production receipt sent to sandbox"
        }
        error_msg = status_messages.get(data["status"], f"Unknown status: {data['status']}")
        raise AppleReceiptError(f"Apple verification failed: {error_msg}")

    return data


@router.post("/apple/verify")
async def verify_apple_receipt(
    request: AppleReceiptRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify Apple In-App Purchase receipt.

    Security checks:
    1. Check for duplicate transaction_id (fraud prevention)
    2. Validate bundle_id (prevent receipt spoofing)
    3. Verify product_id matches our products
    """

    # 1. CHECK DUPLICATE TRANSACTION (SECURITY: Prevent fraud)
    existing = db.scalar(
        select(PaymentTransaction).where(
            PaymentTransaction.apple_transaction_id == request.transaction_id
        )
    )
    if existing:
        raise HTTPException(409, f"Transaction {request.transaction_id} already processed")

    # 2. VERIFY WITH APPLE
    try:
        apple_response = await verify_apple_receipt_with_apple(request.receipt_data)
    except AppleReceiptError as e:
        raise HTTPException(422, str(e))

    # 3. VERIFY BUNDLE_ID (SECURITY: Prevent replay attacks)
    receipt_bundle_id = apple_response.get("receipt", {}).get("bundle_id")
    if receipt_bundle_id != EXPECTED_BUNDLE_ID:
        raise HTTPException(403, f"Bundle ID mismatch: expected {EXPECTED_BUNDLE_ID}, got {receipt_bundle_id}")

    # 4. EXTRACT TRANSACTION INFO
    latest_info = apple_response.get("latest_receipt_info", [])
    if not latest_info:
        # Try in_app for non-subscription purchases
        in_app = apple_response.get("receipt", {}).get("in_app", [])
        if not in_app:
            raise HTTPException(422, "No transaction info in receipt")
        latest_info = in_app

    transaction = latest_info[0]

    # Validate product_id
    if transaction["product_id"] != request.product_id:
        raise HTTPException(400, "Product ID mismatch")

    # 5. UPDATE SUBSCRIPTION OR CREDITS
    product_id = request.product_id

    if 'subscription' in product_id or 'plus' in product_id or 'pro' in product_id:
        # Handle subscription
        if 'plus' in product_id:
            tier_name = 'plus'
        elif 'pro' in product_id:
            tier_name = 'pro'
        else:
            raise HTTPException(400, f"Unknown subscription product: {product_id}")

        tier = db.scalar(
            select(SubscriptionTier).where(SubscriptionTier.tier_name == tier_name)
        )

        if not tier:
            raise HTTPException(404, f"Tier {tier_name} not found")

        # Get or create subscription
        subscription = db.scalar(
            select(UserSubscription).where(UserSubscription.user_id == current_user.id)
        )

        if not subscription:
            subscription = UserSubscription(
                user_id=current_user.id,
                tier_id=tier.id,
                billing_period_start=datetime.utcnow(),
                billing_period_end=datetime.utcnow() + timedelta(days=30),
                status='active'
            )
            db.add(subscription)
        else:
            subscription.tier_id = tier.id
            subscription.apple_transaction_id = request.transaction_id
            subscription.apple_original_transaction_id = request.original_transaction_id
            subscription.billing_period_start = datetime.utcnow()
            subscription.billing_period_end = datetime.utcnow() + timedelta(days=30)
            subscription.status = 'active'

        db.commit()

        # Record payment
        payment_tx = PaymentTransaction(
            user_id=current_user.id,
            platform='apple',
            transaction_type='subscription',
            amount_usd=Decimal('29.00') if tier_name == 'plus' else Decimal('199.00'),
            currency='USD',
            apple_transaction_id=request.transaction_id,
            apple_original_transaction_id=request.original_transaction_id,
            apple_product_id=request.product_id,
            apple_receipt_data=request.receipt_data[:500],  # Store truncated for debugging
            status='completed',
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.add(payment_tx)
        db.commit()

        return {
            "verified": True,
            "tier_updated": True,
            "tier": tier_name,
            "message": f"Subscription to {tier.display_name} activated"
        }

    elif 'credits' in product_id:
        # Handle credit package
        # Extract hours from product_id (e.g., "com.livetranslator.credits.4hr" -> 4)
        try:
            hours_str = product_id.split('.')[-1].replace('hr', '')
            hours = int(hours_str)
        except (ValueError, IndexError):
            raise HTTPException(400, f"Cannot parse hours from product_id: {product_id}")

        seconds = hours * 3600

        # Get or create subscription
        subscription = db.scalar(
            select(UserSubscription).where(UserSubscription.user_id == current_user.id)
        )

        if not subscription:
            # Create subscription record with free tier
            free_tier = db.scalar(
                select(SubscriptionTier).where(SubscriptionTier.tier_name == 'free')
            )
            subscription = UserSubscription(
                user_id=current_user.id,
                tier_id=free_tier.id if free_tier else None,
                billing_period_start=datetime.utcnow(),
                billing_period_end=datetime.utcnow() + timedelta(days=30),
                status='active'
            )
            db.add(subscription)

        subscription.bonus_credits_seconds += seconds
        db.commit()

        # Record quota transaction
        quota_tx = QuotaTransaction(
            user_id=current_user.id,
            transaction_type='purchase',
            amount_seconds=seconds,
            quota_type='bonus',
            description=f"Purchased {hours} hours via Apple IAP"
        )
        db.add(quota_tx)

        # Record payment
        # Map hours to price
        price_map = {1: 5, 4: 19, 8: 35, 20: 80}
        amount_usd = Decimal(price_map.get(hours, hours * 5))

        payment_tx = PaymentTransaction(
            user_id=current_user.id,
            platform='apple',
            transaction_type='credit_purchase',
            amount_usd=amount_usd,
            currency='USD',
            apple_transaction_id=request.transaction_id,
            apple_original_transaction_id=request.original_transaction_id,
            apple_product_id=request.product_id,
            apple_receipt_data=request.receipt_data[:500],
            status='completed',
            created_at=datetime.utcnow(),
            completed_at=datetime.utcnow()
        )
        db.add(payment_tx)
        db.commit()

        return {
            "verified": True,
            "credits_granted": hours,
            "message": f"Added {hours} hours to your account"
        }

    else:
        raise HTTPException(400, f"Unknown product type: {product_id}")


@router.post("/apple/webhook")
async def apple_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Apple Server-to-Server notification handler (PUBLIC endpoint).

    Notification types:
    - DID_RENEW: Subscription renewed
    - DID_FAIL_TO_RENEW: Payment failed
    - DID_CHANGE_RENEWAL_STATUS: User turned off auto-renew
    - REFUND: User requested refund
    """
    payload = await request.json()

    # Validate shared secret
    if payload.get("password") != APPLE_SHARED_SECRET:
        raise HTTPException(403, "Invalid shared secret")

    notification_type = payload.get("notification_type")
    unified_receipt = payload.get("unified_receipt", {})
    latest_info = unified_receipt.get("latest_receipt_info", [])

    if not latest_info:
        return {"status": "no_transaction_info"}

    transaction = latest_info[0]
    original_transaction_id = transaction["original_transaction_id"]

    # Find subscription by original_transaction_id
    subscription = db.scalar(
        select(UserSubscription).where(
            UserSubscription.apple_original_transaction_id == original_transaction_id
        )
    )

    if not subscription:
        print(f"[Apple Webhook] Subscription not found for original_transaction_id={original_transaction_id}")
        return {"status": "subscription_not_found"}

    # Handle notification types
    if notification_type == 'DID_RENEW':
        # Extend billing period
        expires_date_ms = int(transaction.get("expires_date_ms", 0))
        if expires_date_ms:
            subscription.billing_period_end = datetime.fromtimestamp(expires_date_ms / 1000, tz=timezone.utc)
            subscription.status = 'active'
            db.commit()
            print(f"[Apple] Subscription renewed for user {subscription.user_id}")

    elif notification_type == 'DID_FAIL_TO_RENEW':
        # Start grace period
        subscription.status = 'past_due'
        subscription.grace_quota_seconds = subscription.bonus_credits_seconds
        db.commit()
        print(f"[Apple] Payment failed for user {subscription.user_id}")

    elif notification_type == 'REFUND':
        # Revoke access immediately
        free_tier = db.scalar(select(SubscriptionTier).where(SubscriptionTier.tier_name == 'free'))
        subscription.status = 'canceled'
        subscription.tier_id = free_tier.id if free_tier else None
        db.commit()
        print(f"[Apple] Refund processed for user {subscription.user_id}")

    elif notification_type == 'DID_CHANGE_RENEWAL_STATUS':
        auto_renew_status = transaction.get("auto_renew_status", "0")
        subscription.auto_renew = (auto_renew_status == "1")
        db.commit()
        print(f"[Apple] Auto-renew changed to {subscription.auto_renew} for user {subscription.user_id}")

    return {"status": "success"}


# ============================================================================
# Payment History
# ============================================================================

@router.get("/history")
async def get_payment_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's payment history"""
    transactions = db.scalars(
        select(PaymentTransaction)
        .where(PaymentTransaction.user_id == current_user.id)
        .order_by(PaymentTransaction.created_at.desc())
    ).all()

    return {
        "payments": [
            {
                "id": tx.id,
                "platform": tx.platform,
                "transaction_type": tx.transaction_type,
                "amount_usd": float(tx.amount_usd),
                "currency": tx.currency,
                "status": tx.status,
                "stripe_invoice_id": tx.stripe_invoice_id,
                "apple_product_id": tx.apple_product_id,
                "created_at": tx.created_at.isoformat(),
                "completed_at": tx.completed_at.isoformat() if tx.completed_at else None
            }
            for tx in transactions
        ],
        "total_spent_usd": float(sum(tx.amount_usd for tx in transactions if tx.status == 'completed'))
    }
