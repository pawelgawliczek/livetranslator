"""
Payment integration for Stripe (Web) and Apple IAP (iOS).

Security features:
- Stripe webhook signature verification (prevent spoofing)
- Apple receipt duplicate transaction check (prevent fraud)
- Apple bundle_id validation (prevent replay attacks)
- Idempotent webhook processing (Redis deduplication)
- Rate limiting (MED-1)
"""
import os
import httpx
import structlog
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address
import asyncio

from ..auth import get_current_user
from ..db import SessionLocal
from ..models import User, UserSubscription, SubscriptionTier, PaymentTransaction, CreditPackage, QuotaTransaction
from ..settings import (
    settings,
    STRIPE_SECRET_KEY,
    STRIPE_WEBHOOK_SECRET,
    APPLE_SHARED_SECRET
)
from ..email_service import send_welcome_email_task

router = APIRouter(prefix="/api/payments", tags=["payments"])

# MED-1: Rate limiter
limiter = Limiter(key_func=get_remote_address)

# MED-2: Structured logging
log = structlog.get_logger("payments")

# Environment variables
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
@limiter.limit("10/minute")  # MED-1: Rate limit to prevent abuse
async def create_stripe_checkout(
    request: Request,
    checkout_request: StripeCheckoutRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe Checkout session for subscription or credit purchase.

    Returns:
    - checkout_url: URL to redirect user to Stripe payment page
    - session_id: Stripe session ID for tracking
    """
    # CSRF protection: Require custom header (prevents simple form POST attacks)
    if not request.headers.get("X-Requested-With"):
        log.warning("csrf_missing_header", user_id=current_user.id)
        raise HTTPException(403, "Missing required header for CSRF protection")
    if not stripe or not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    # 1. Get Stripe price ID from database
    if checkout_request.product_type == 'subscription':
        if not checkout_request.tier_id:
            raise HTTPException(400, "tier_id required for subscription")

        tier = db.scalar(select(SubscriptionTier).where(SubscriptionTier.id == checkout_request.tier_id))
        if not tier:
            raise HTTPException(404, "Tier not found")

        if not tier.stripe_price_id:
            raise HTTPException(400, f"Tier {tier.tier_name} does not support Stripe payments")

        # Check if user has existing subscription
        current_sub = db.scalar(
            select(UserSubscription)
            .where(UserSubscription.user_id == current_user.id)
        )

        # Validate downgrade rules
        if current_sub and current_sub.tier_id:
            current_tier = db.get(SubscriptionTier, current_sub.tier_id)
            if current_tier:
                # Prevent downgrade if current tier is more expensive
                if current_tier.monthly_price_usd > tier.monthly_price_usd:
                    raise HTTPException(
                        400,
                        detail={
                            "error": "downgrade_not_allowed",
                            "message": "Downgrades are not available via self-service. Please contact support.",
                            "current_tier": current_tier.tier_name,
                            "requested_tier": tier.tier_name
                        }
                    )

        price_id = tier.stripe_price_id
        mode = 'subscription'

    elif checkout_request.product_type == 'credits':
        if not checkout_request.package_id:
            raise HTTPException(400, "package_id required for credit purchase")

        package = db.scalar(select(CreditPackage).where(CreditPackage.id == checkout_request.package_id))
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
        log.info("creating_stripe_session", price_id=price_id, mode=mode, user_id=current_user.id)
        session = stripe.checkout.Session.create(
            customer_email=current_user.email,
            mode=mode,
            payment_method_types=['card'],  # Enable card payments
            line_items=[{
                'price': price_id,
                'quantity': 1
            }],
            success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{FRONTEND_URL}/billing/cancel",
            metadata={
                'user_id': str(current_user.id),
                'product_type': checkout_request.product_type,
                'tier_id': str(checkout_request.tier_id) if checkout_request.tier_id else '',
                'package_id': str(checkout_request.package_id) if checkout_request.package_id else ''
            }
        )

        log.info("stripe_session_created", session_id=session.id)
        return {
            "checkout_url": session.url,
            "session_id": session.id
        }
    except stripe.error.StripeError as e:
        log.error("stripe_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(502, f"Stripe error: {str(e)}")
    except Exception as e:
        log.error("checkout_unexpected_error", error=str(e), error_type=type(e).__name__)
        import traceback
        log.error("checkout_traceback", traceback=traceback.format_exc())
        raise HTTPException(500, f"Failed to create checkout: {str(e)}")


@router.post("/stripe/create-portal-session")
@limiter.limit("10/minute")
async def create_customer_portal_session(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create Stripe Customer Portal session for subscription management.

    Users can:
    - Cancel subscription
    - Update payment method
    - View billing history
    - Download invoices

    Returns redirect URL to Stripe Customer Portal.
    """
    # CSRF protection: Require custom header
    if not request.headers.get("X-Requested-With"):
        log.warning("csrf_missing_header", user_id=current_user.id)
        raise HTTPException(403, "Missing required header for CSRF protection")

    if not stripe or not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    # Get user's subscription
    subscription = db.scalar(
        select(UserSubscription).where(UserSubscription.user_id == current_user.id)
    )

    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(404, "No Stripe subscription found")

    try:
        log.info("creating_portal_session",
                 customer_id=subscription.stripe_customer_id,
                 user_id=current_user.id)

        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{FRONTEND_URL}/subscription"
        )

        log.info("portal_session_created", session_id=session.id)
        return {
            "portal_url": session.url
        }
    except stripe.error.StripeError as e:
        log.error("stripe_portal_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(502, f"Stripe error: {str(e)}")
    except Exception as e:
        log.error("portal_unexpected_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(500, f"Failed to create portal session: {str(e)}")


@router.post("/stripe/webhook")
@limiter.limit("60/minute")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Stripe webhook handler with retry logic (US-011).

    Flow:
    1. Verify signature
    2. Store in database (for retry)
    3. Check idempotency
    4. Process event
    5. Mark completed or schedule retry

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

    event_id = event['id']
    event_type = event['type']
    event_data = event['data']['object']

    # 2. Store webhook in database for retry logic (US-011)
    from sqlalchemy import text
    import json as jsonlib
    webhook_row = None
    webhook_id = None
    try:
        # Check if already stored
        webhook_row = db.execute(
            text("SELECT id, status FROM webhook_events WHERE event_id = :event_id"),
            {"event_id": event_id}
        ).fetchone()

        if not webhook_row:
            # Store new webhook
            result = db.execute(
                text("""
                    INSERT INTO webhook_events
                    (event_id, event_type, payload, status, created_at)
                    VALUES (:event_id, :event_type, :payload, 'processing', NOW())
                    RETURNING id
                """),
                {
                    "event_id": event_id,
                    "event_type": event_type,
                    "payload": jsonlib.dumps(event)  # Store full event for replay
                }
            )
            db.commit()
            webhook_id = result.fetchone()[0]
            log.info("webhook_stored", event_id=event_id, webhook_id=webhook_id)
        else:
            webhook_id = webhook_row[0]
            if webhook_row[1] == 'completed':
                log.info("webhook_already_processed", event_id=event_id)
                return {"status": "duplicate"}
    except Exception as e:
        log.error("webhook_storage_error", event_id=event_id, error=str(e))
        # Continue processing even if storage fails (don't block webhook)

    # 3. Redis idempotency check (7-day TTL, belt-and-suspenders with DB)
    from redis.asyncio import Redis
    redis = Redis.from_url(str(settings.LT_REDIS_URL))

    if await redis.get(f"stripe:event:{event_id}"):
        log.info("stripe_webhook_duplicate_redis", event_id=event_id)
        return {"status": "duplicate"}

    # Mark as processed in Redis (TTL 7 days)
    await redis.setex(f"stripe:event:{event_id}", 7 * 86400, "1")

    # 4. Process event
    try:
        if event_type == 'checkout.session.completed':
            await handle_checkout_completed(event_data, db)
        elif event_type == 'customer.subscription.updated':
            await handle_subscription_updated(event_data, db)
        elif event_type == 'invoice.payment_failed':
            await handle_payment_failed(event_data, db)
        elif event_type == 'customer.subscription.deleted':
            await handle_subscription_deleted(event_data, db)

        # 5. Mark webhook as completed
        if webhook_id:
            db.execute(
                text("""
                    UPDATE webhook_events
                    SET status = 'completed', completed_at = NOW()
                    WHERE id = :id
                """),
                {"id": webhook_id}
            )
            db.commit()

        return {"status": "success"}

    except Exception as e:
        db.rollback()
        log.error("webhook_handler_failed", event_type=event_type, event_id=event_id, error=str(e))

        # Schedule retry (US-011)
        if webhook_id:
            from datetime import datetime, timedelta
            next_retry = datetime.utcnow() + timedelta(minutes=1)  # First retry in 1 minute
            db.execute(
                text("""
                    UPDATE webhook_events
                    SET status = 'failed',
                        retry_count = retry_count + 1,
                        next_retry_at = :next_retry,
                        last_retry_at = NOW(),
                        error_message = :error
                    WHERE id = :id
                """),
                {
                    "id": webhook_id,
                    "next_retry": next_retry,
                    "error": str(e)[:500]  # Truncate error
                }
            )
            db.commit()
            log.info("webhook_retry_scheduled", event_id=event_id, next_retry=next_retry.isoformat())

        # Return 200 to prevent Stripe retry (we handle retries ourselves)
        return {"status": "retry_scheduled"}


async def handle_checkout_completed(session: dict, db: Session):
    """Process successful Stripe payment"""
    try:
        user_id = int(session['metadata']['user_id'])
        product_type = session['metadata']['product_type']
    except (ValueError, KeyError, TypeError) as e:
        log.error("invalid_checkout_metadata", error=str(e), metadata=session.get('metadata'))
        raise HTTPException(422, f"Invalid metadata format: {str(e)}")

    user = db.get(User, user_id)
    if not user:
        log.warning("stripe_user_not_found", user_id=user_id)
        return

    if product_type == 'subscription':
        try:
            tier_id = int(session['metadata']['tier_id'])
        except (ValueError, KeyError, TypeError) as e:
            log.error("invalid_tier_id", error=str(e), metadata=session.get('metadata'))
            raise HTTPException(422, f"Invalid tier_id: {str(e)}")

        # Validate tier exists and matches expected price
        tier = db.get(SubscriptionTier, tier_id)
        if not tier:
            log.error("invalid_tier", tier_id=tier_id, session_id=session.get('id'))
            raise HTTPException(422, f"Tier {tier_id} does not exist")

        # Validate price_id matches tier (prevent price manipulation)
        price_id = session.get('line_items', {}).get('data', [{}])[0].get('price', {}).get('id')
        if price_id and tier.stripe_price_id and price_id != tier.stripe_price_id:
            log.error("price_mismatch", tier_id=tier_id, expected=tier.stripe_price_id, actual=price_id)
            raise HTTPException(422, "Price mismatch - possible tampering detected")

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

        # === US-012: Send welcome email ===
        # P0-1 FIX: Use wrapper that creates own DB session
        tier = db.get(SubscriptionTier, tier_id)
        if tier:
            asyncio.create_task(
                send_welcome_email_task(
                    user_id=user_id,
                    tier_name=tier.display_name
                )
            )
        # === END US-012 ===

    elif product_type == 'credits':
        try:
            package_id = int(session['metadata']['package_id'])
        except (ValueError, KeyError, TypeError) as e:
            log.error("invalid_package_id", error=str(e), metadata=session.get('metadata'))
            raise HTTPException(422, f"Invalid package_id: {str(e)}")

        package = db.get(CreditPackage, package_id)
        if not package:
            log.error("invalid_package", package_id=package_id, session_id=session.get('id'))
            raise HTTPException(422, f"Package {package_id} does not exist")

        # Validate price_id matches package (prevent price manipulation)
        price_id = session.get('line_items', {}).get('data', [{}])[0].get('price', {}).get('id')
        if price_id and package.stripe_price_id and price_id != package.stripe_price_id:
            log.error("price_mismatch", package_id=package_id, expected=package.stripe_price_id, actual=price_id)
            raise HTTPException(422, "Price mismatch - possible tampering detected")

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

                # === US-012: Send welcome email for first-time credit buyers (still on free tier) ===
                # P0-1 FIX: Use wrapper that creates own DB session
                if subscription and subscription.tier_id:
                    tier = db.get(SubscriptionTier, subscription.tier_id)
                    if tier and tier.tier_name == 'free':
                        # First-time credit purchase, send welcome
                        asyncio.create_task(
                            send_welcome_email_task(
                                user_id=user_id,
                                tier_name="Credit Package Buyer"
                            )
                        )
                # === END US-012 ===

    # Record payment transaction
    payment_tx = PaymentTransaction(
        user_id=user_id,
        platform='stripe',
        transaction_type=product_type,
        amount_usd=Decimal(session['amount_total']) / 100,
        currency='USD',
        stripe_payment_intent_id=session.get('payment_intent'),
        stripe_invoice_id=session.get('invoice'),
        status='completed',
        created_at=datetime.utcnow(),
        completed_at=datetime.utcnow()
    )
    db.add(payment_tx)
    db.commit()

    log.info("stripe_checkout_completed", user_id=user_id, product_type=product_type, amount_usd=float(session['amount_total']) / 100)


async def handle_subscription_updated(subscription_data: dict, db: Session):
    """Handle subscription renewal/update/plan change"""
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
        subscription.status = subscription_data.get('status', 'active')

        # Handle plan changes (when user upgrades/downgrades via Customer Portal)
        if 'items' in subscription_data and subscription_data['items']['data']:
            stripe_price_id = subscription_data['items']['data'][0]['price']['id']

            # Find the tier matching this price ID
            new_tier = db.scalar(
                select(SubscriptionTier).where(SubscriptionTier.stripe_price_id == stripe_price_id)
            )

            if new_tier and new_tier.id != subscription.tier_id:
                old_tier_id = subscription.tier_id
                subscription.tier_id = new_tier.id
                log.info("stripe_plan_changed",
                        subscription_id=stripe_subscription_id,
                        user_id=subscription.user_id,
                        old_tier_id=old_tier_id,
                        new_tier_id=new_tier.id,
                        new_tier_name=new_tier.tier_name)

        db.commit()
        log.info("stripe_subscription_updated", subscription_id=stripe_subscription_id, user_id=subscription.user_id)


async def handle_payment_failed(invoice_data: dict, db: Session):
    """
    Handle failed payment (US-007).

    Sets subscription status to 'past_due' and grants a 3-day grace period.
    If grace period expires without payment, subscription will be downgraded to Free tier.
    """
    customer_id = invoice_data['customer']

    subscription = db.scalar(
        select(UserSubscription).where(UserSubscription.stripe_customer_id == customer_id)
    )

    if subscription:
        # Set status to past_due
        subscription.status = 'past_due'

        # Grant 3-day grace period
        grace_period_end = datetime.utcnow() + timedelta(days=3)
        subscription.grace_period_end = grace_period_end

        db.commit()

        log.warning(
            "stripe_payment_failed",
            user_id=subscription.user_id,
            customer_id=customer_id,
            grace_period_end=grace_period_end.isoformat()
        )

        # TODO: Send email notification to user about payment failure
        # await send_payment_failed_email(subscription.user_id, grace_period_end)


async def handle_subscription_deleted(subscription_data: dict, db: Session):
    """
    Handle subscription cancellation or deletion after grace period (US-007).

    This webhook is triggered when:
    1. User cancels subscription via Customer Portal
    2. Grace period expires after failed payment (automatic downgrade)
    """
    stripe_subscription_id = subscription_data['id']

    subscription = db.scalar(
        select(UserSubscription).where(
            UserSubscription.stripe_subscription_id == stripe_subscription_id
        )
    )

    if subscription:
        # Get Free tier ID
        free_tier = db.scalar(
            select(SubscriptionTier).where(SubscriptionTier.tier_name == 'free')
        )

        # Downgrade to Free tier
        subscription.tier_id = free_tier.id if free_tier else 1  # Default to tier ID 1 (Free)
        subscription.status = 'active'  # Free tier is always active
        subscription.auto_renew = False
        subscription.stripe_subscription_id = None
        subscription.billing_period_end = None
        subscription.grace_period_end = None  # Clear grace period

        db.commit()

        log.info(
            "stripe_subscription_deleted",
            subscription_id=stripe_subscription_id,
            user_id=subscription.user_id,
            downgraded_to="free"
        )


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
@limiter.limit("5/minute")  # MED-1: Rate limit Apple IAP verification
async def verify_apple_receipt(
    request_obj: Request,
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
        log.warning("apple_webhook_subscription_not_found", original_transaction_id=original_transaction_id)
        return {"status": "subscription_not_found"}

    # Handle notification types
    if notification_type == 'DID_RENEW':
        # Extend billing period
        expires_date_ms = int(transaction.get("expires_date_ms", 0))
        if expires_date_ms:
            subscription.billing_period_end = datetime.fromtimestamp(expires_date_ms / 1000, tz=timezone.utc)
            subscription.status = 'active'
            db.commit()
            log.info("apple_subscription_renewed", user_id=subscription.user_id)

    elif notification_type == 'DID_FAIL_TO_RENEW':
        # Start grace period
        subscription.status = 'past_due'
        subscription.grace_quota_seconds = subscription.bonus_credits_seconds
        db.commit()
        log.warning("apple_payment_failed", user_id=subscription.user_id)

    elif notification_type == 'REFUND':
        # Revoke access immediately
        free_tier = db.scalar(select(SubscriptionTier).where(SubscriptionTier.tier_name == 'free'))
        subscription.status = 'canceled'
        subscription.tier_id = free_tier.id if free_tier else None
        db.commit()
        log.warning("apple_refund_processed", user_id=subscription.user_id)

    elif notification_type == 'DID_CHANGE_RENEWAL_STATUS':
        auto_renew_status = transaction.get("auto_renew_status", "0")
        subscription.auto_renew = (auto_renew_status == "1")
        db.commit()
        log.info("apple_auto_renew_changed", user_id=subscription.user_id, auto_renew=subscription.auto_renew)

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


# ============================================================
# US-009: Invoice Download
# ============================================================
@router.get("/stripe/invoice/{invoice_id}/pdf")
@limiter.limit("10/minute")
async def download_invoice_pdf(
    request: Request,
    invoice_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Download invoice PDF from Stripe (US-009).

    Security:
    - Verify invoice belongs to current user
    - Rate limited to prevent abuse
    - Proxy through backend to hide Stripe API key

    Returns:
        StreamingResponse: PDF file stream
    """
    if not stripe or not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured")

    # Validate invoice_id format (Stripe invoices start with 'in_')
    if not invoice_id.startswith('in_'):
        raise HTTPException(400, "Invalid invoice ID format")

    # Verify invoice belongs to this user
    payment = db.scalar(
        select(PaymentTransaction)
        .where(
            PaymentTransaction.user_id == current_user.id,
            PaymentTransaction.stripe_invoice_id == invoice_id
        )
    )

    if not payment:
        raise HTTPException(404, "Invoice not found or access denied")

    try:
        # Fetch invoice from Stripe
        invoice = stripe.Invoice.retrieve(invoice_id)

        # Get PDF URL
        pdf_url = invoice.invoice_pdf

        if not pdf_url:
            raise HTTPException(404, "Invoice PDF not available")

        # Stream PDF through our backend (don't expose Stripe URL)
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(pdf_url)
            response.raise_for_status()

            from starlette.responses import StreamingResponse
            return StreamingResponse(
                iter([response.content]),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename=invoice_{invoice_id}.pdf"
                }
            )

    except stripe.error.StripeError as e:
        log.error("stripe_invoice_error", invoice_id=invoice_id, error=str(e))
        raise HTTPException(502, f"Stripe error: {str(e)}")
    except Exception as e:
        log.error("invoice_download_error", invoice_id=invoice_id, error=str(e))
        raise HTTPException(500, f"Failed to download invoice: {str(e)}")
