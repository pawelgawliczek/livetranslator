"""
Email notification service using Web3Forms API.

Handles:
- Quota warning emails (80%)
- Quota exhaustion emails (100%)
- Welcome emails (new subscriptions)
- Payment failure emails (future)
"""
import os
import logging
import httpx
import json
from datetime import datetime
from typing import Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import text, select
from .models import User, UserSubscription, SubscriptionTier

logger = logging.getLogger(__name__)


# ========================================
# Async Task Wrappers (P0-1 Fix)
# ========================================

async def send_quota_email_task(
    user_id: int,
    notification_type: str,
    percentage: int,
    remaining_seconds: int,
    billing_period_start: datetime
):
    """
    Wrapper that creates own DB session for async task.

    CRITICAL: Async tasks cannot use parent session (closes before task completes).
    """
    from .db import SessionLocal
    db = SessionLocal()
    try:
        await send_quota_email(db, user_id, notification_type, percentage, remaining_seconds, billing_period_start)
    finally:
        db.close()


async def send_welcome_email_task(user_id: int, tier_name: str):
    """
    Wrapper that creates own DB session for async task.

    CRITICAL: Async tasks cannot use parent session (closes before task completes).
    """
    from .db import SessionLocal
    db = SessionLocal()
    try:
        await send_welcome_email(db, user_id, tier_name)
    finally:
        db.close()


# Web3Forms configuration
WEB3FORMS_API_URL = "https://api.web3forms.com/submit"
WEB3FORMS_ACCESS_KEY = os.getenv("WEB3FORMS_ACCESS_KEY", "1d5e5f8c-7b5b-44c8-99a4-68d20e3d5c92")
WEB3FORMS_FROM_NAME = "LiveTranslator"
WEB3FORMS_TIMEOUT = 10.0  # seconds

NotificationType = Literal["quota_80", "quota_100", "welcome", "payment_failed"]


async def send_email_via_web3forms(
    to_email: str,
    subject: str,
    body: str,
    user_name: Optional[str] = None
) -> dict:
    """
    Send email via Web3Forms API.

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Plain text email body
        user_name: Optional user display name

    Returns:
        dict: Web3Forms API response

    Raises:
        httpx.HTTPError: If API request fails
    """
    payload = {
        "access_key": WEB3FORMS_ACCESS_KEY,
        "from_name": WEB3FORMS_FROM_NAME,
        "subject": subject,
        "email": to_email,
        "message": body
    }

    # Add user name if provided
    if user_name:
        payload["name"] = user_name

    try:
        async with httpx.AsyncClient(timeout=WEB3FORMS_TIMEOUT) as client:
            response = await client.post(WEB3FORMS_API_URL, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("success"):
                logger.info(
                    "email_sent",
                    extra={
                        "to": to_email,
                        "subject": subject,
                        "response": result
                    }
                )
            else:
                logger.error(
                    "email_send_failed",
                    extra={
                        "to": to_email,
                        "subject": subject,
                        "response": result
                    }
                )

            return result

    except httpx.HTTPError as e:
        logger.error(
            "email_http_error",
            extra={
                "to": to_email,
                "subject": subject,
                "error": str(e)
            }
        )
        raise


def get_email_template(
    notification_type: NotificationType,
    user_name: str,
    **context
) -> tuple[str, str]:
    """
    Generate email subject and body based on notification type.

    Args:
        notification_type: Type of notification
        user_name: User's display name
        **context: Template context variables

    Returns:
        tuple[str, str]: (subject, body)
    """
    if notification_type == "quota_80":
        percentage = context.get("percentage", 80)
        remaining_hours = context.get("remaining_hours", 0)
        reset_date = context.get("reset_date", "N/A")

        subject = f"Quota Alert: You've used {percentage}% of your LiveTranslator quota"
        body = f"""Hi {user_name},

This is a friendly reminder that you've used {percentage}% of your monthly quota on LiveTranslator.

Remaining quota: {remaining_hours} hours
Quota resets on: {reset_date}

To avoid service interruption, consider:
- Upgrading to a higher tier: https://livetranslator.pawelgawliczek.cloud/subscription
- Purchasing additional credit packages: https://livetranslator.pawelgawliczek.cloud/billing

Questions? Reply to this email or visit our support page.

Best regards,
The LiveTranslator Team

---
You're receiving this email because you have an active LiveTranslator account.
To manage email preferences: https://livetranslator.pawelgawliczek.cloud/profile
"""

    elif notification_type == "quota_100":
        reset_date = context.get("reset_date", "N/A")

        subject = "Quota Exhausted: Your LiveTranslator quota has been used up"
        body = f"""Hi {user_name},

Your monthly quota on LiveTranslator has been fully used.

Quota resets on: {reset_date}

To continue using LiveTranslator immediately:
- Purchase credit packages: https://livetranslator.pawelgawliczek.cloud/billing
- Upgrade to a higher tier: https://livetranslator.pawelgawliczek.cloud/subscription

Your data and settings are safe. You can resume using the service once quota is replenished.

Questions? Reply to this email or visit our support page.

Best regards,
The LiveTranslator Team

---
You're receiving this email because you have an active LiveTranslator account.
To manage email preferences: https://livetranslator.pawelgawliczek.cloud/profile
"""

    elif notification_type == "welcome":
        tier_name = context.get("tier_name", "Unknown")
        quota_hours = context.get("quota_hours", 0)
        billing_start = context.get("billing_start", "N/A")
        billing_end = context.get("billing_end", "N/A")

        subject = f"Welcome to LiveTranslator {tier_name}!"
        body = f"""Hi {user_name},

Thank you for subscribing to LiveTranslator {tier_name}!

Your subscription details:
- Plan: {tier_name}
- Monthly quota: {quota_hours} hours
- Billing period: {billing_start} to {billing_end}

Getting started:
1. Create a room: https://livetranslator.pawelgawliczek.cloud/
2. Invite participants or share the room code
3. Start speaking - translations happen in real-time!

Features you now have access to:
- Real-time speech translation
- Multi-speaker support
- Advanced language models
- Priority processing

Need help? Check our docs or reply to this email.

Welcome aboard!
The LiveTranslator Team

---
Manage your subscription: https://livetranslator.pawelgawliczek.cloud/subscription
Support: https://livetranslator.pawelgawliczek.cloud/support
"""

    elif notification_type == "payment_failed":
        grace_period_end = context.get("grace_period_end", "N/A")

        subject = "Payment Failed: Update your payment method"
        body = f"""Hi {user_name},

We were unable to process your payment for LiveTranslator.

Grace period ends: {grace_period_end}

To avoid service interruption, please update your payment method:
https://livetranslator.pawelgawliczek.cloud/subscription

If you've already updated your payment method, please disregard this message.

Questions? Reply to this email or contact our support team.

Best regards,
The LiveTranslator Team

---
Manage your subscription: https://livetranslator.pawelgawliczek.cloud/subscription
Support: https://livetranslator.pawelgawliczek.cloud/support
"""
    else:
        raise ValueError(f"Unknown notification type: {notification_type}")

    return subject, body


async def send_quota_email(
    db: Session,
    user_id: int,
    notification_type: Literal["quota_80", "quota_100"],
    percentage: int,
    remaining_seconds: int,
    billing_period_start: datetime
) -> bool:
    """
    Send quota warning or exhaustion email.

    Args:
        db: Database session
        user_id: User ID
        notification_type: 'quota_80' or 'quota_100'
        percentage: Current usage percentage
        remaining_seconds: Remaining quota in seconds
        billing_period_start: Start of current billing period

    Returns:
        bool: True if email sent successfully
    """
    # Get user details
    user = db.get(User, user_id)
    if not user:
        logger.warning("send_quota_email_user_not_found", extra={"user_id": user_id})
        return False

    # Check user preference
    if not user.email_notifications_enabled:
        logger.info("send_quota_email_disabled", extra={"user_id": user_id})
        return False

    # Get subscription for reset date
    subscription = db.scalar(
        select(UserSubscription).where(UserSubscription.user_id == user_id)
    )

    if not subscription:
        logger.warning("send_quota_email_no_subscription", extra={"user_id": user_id})
        return False

    # Deduplication for 100% quota (once per billing period)
    if notification_type == "quota_100":
        existing = db.execute(
            text("""
                SELECT id FROM email_notifications
                WHERE user_id = :user_id
                  AND notification_type = :type
                  AND billing_period_start = :period_start
                  AND delivery_status = 'sent'
                LIMIT 1
            """),
            {
                "user_id": user_id,
                "type": notification_type,
                "period_start": billing_period_start
            }
        ).fetchone()

        if existing:
            logger.info(
                "send_quota_email_already_sent",
                extra={
                    "user_id": user_id,
                    "type": notification_type,
                    "period_start": billing_period_start
                }
            )
            return False

    # Generate email content
    remaining_hours = round(remaining_seconds / 3600, 1)
    reset_date = subscription.billing_period_end.strftime("%Y-%m-%d") if subscription.billing_period_end else "N/A"

    subject, body = get_email_template(
        notification_type,
        user_name=user.display_name or "User",
        percentage=percentage,
        remaining_hours=remaining_hours,
        reset_date=reset_date
    )

    # Send email
    try:
        response = await send_email_via_web3forms(
            to_email=user.email,
            subject=subject,
            body=body,
            user_name=user.display_name or "User"
        )

        delivery_status = "sent" if response.get("success") else "failed"

        # Record in database
        db.execute(
            text("""
                INSERT INTO email_notifications
                (user_id, notification_type, billing_period_start, sent_at,
                 delivery_status, web3forms_response, user_email, subject, quota_percentage)
                VALUES
                (:user_id, :type, :period_start, NOW(),
                 :status, CAST(:response AS jsonb), :email, :subject, :percentage)
            """),
            {
                "user_id": user_id,
                "type": notification_type,
                "period_start": billing_period_start,
                "status": delivery_status,
                "response": json.dumps(response) if response else None,
                "email": user.email,
                "subject": subject,
                "percentage": percentage
            }
        )
        db.commit()

        logger.info(
            "quota_email_sent",
            extra={
                "user_id": user_id,
                "type": notification_type,
                "percentage": percentage,
                "status": delivery_status
            }
        )

        return delivery_status == "sent"

    except Exception as e:
        logger.error(
            "send_quota_email_failed",
            extra={
                "user_id": user_id,
                "type": notification_type,
                "error": str(e)
            }
        )

        # Record failure
        try:
            db.execute(
                text("""
                    INSERT INTO email_notifications
                    (user_id, notification_type, billing_period_start, sent_at,
                     delivery_status, web3forms_response, user_email, subject, quota_percentage)
                    VALUES
                    (:user_id, :type, :period_start, NOW(),
                     'failed', CAST(:error AS text), :email, :subject, :percentage)
                """),
                {
                    "user_id": user_id,
                    "type": notification_type,
                    "period_start": billing_period_start,
                    "error": str(e)[:500],
                    "email": user.email,
                    "subject": subject,
                    "percentage": percentage
                }
            )
            db.commit()
        except Exception:
            pass  # Don't fail if logging fails

        return False


async def send_welcome_email(
    db: Session,
    user_id: int,
    tier_name: str
) -> bool:
    """
    Send welcome email after subscription purchase.

    Args:
        db: Database session
        user_id: User ID
        tier_name: Subscription tier name (Plus, Pro)

    Returns:
        bool: True if email sent successfully
    """
    # Get user details
    user = db.get(User, user_id)
    if not user:
        logger.warning("send_welcome_email_user_not_found", extra={"user_id": user_id})
        return False

    # Check user preference
    if not user.email_notifications_enabled:
        logger.info("send_welcome_email_disabled", extra={"user_id": user_id})
        return False

    # Deduplication: Check if sent in last 24 hours (prevent webhook retry duplicates)
    existing = db.execute(
        text("""
            SELECT id FROM email_notifications
            WHERE user_id = :user_id
              AND notification_type = 'welcome'
              AND sent_at > NOW() - INTERVAL '24 hours'
            LIMIT 1
        """),
        {"user_id": user_id}
    ).fetchone()

    if existing:
        logger.info("send_welcome_email_already_sent", extra={"user_id": user_id})
        return False

    # Get subscription details
    subscription = db.scalar(
        select(UserSubscription)
        .where(UserSubscription.user_id == user_id)
    )

    if not subscription or not subscription.tier_id:
        logger.warning("send_welcome_email_no_subscription", extra={"user_id": user_id})
        return False

    tier = db.get(SubscriptionTier, subscription.tier_id)
    if not tier:
        logger.warning("send_welcome_email_no_tier", extra={"user_id": user_id})
        return False

    # Generate email content
    quota_hours = float(tier.monthly_quota_hours) if tier.monthly_quota_hours else 0
    billing_start = subscription.billing_period_start.strftime("%Y-%m-%d")
    billing_end = subscription.billing_period_end.strftime("%Y-%m-%d") if subscription.billing_period_end else "N/A"

    subject, body = get_email_template(
        "welcome",
        user_name=user.display_name or "User",
        tier_name=tier.display_name,
        quota_hours=quota_hours,
        billing_start=billing_start,
        billing_end=billing_end
    )

    # Send email
    try:
        response = await send_email_via_web3forms(
            to_email=user.email,
            subject=subject,
            body=body,
            user_name=user.display_name or "User"
        )

        delivery_status = "sent" if response.get("success") else "failed"

        # Record in database
        db.execute(
            text("""
                INSERT INTO email_notifications
                (user_id, notification_type, sent_at, delivery_status,
                 web3forms_response, user_email, subject, tier_name)
                VALUES
                (:user_id, 'welcome', NOW(), :status,
                 CAST(:response AS jsonb), :email, :subject, :tier_name)
            """),
            {
                "user_id": user_id,
                "status": delivery_status,
                "response": json.dumps(response) if response else None,
                "email": user.email,
                "subject": subject,
                "tier_name": tier.display_name
            }
        )
        db.commit()

        logger.info(
            "welcome_email_sent",
            extra={
                "user_id": user_id,
                "tier_name": tier.display_name,
                "status": delivery_status
            }
        )

        return delivery_status == "sent"

    except Exception as e:
        logger.error(
            "send_welcome_email_failed",
            extra={
                "user_id": user_id,
                "tier_name": tier_name,
                "error": str(e)
            }
        )
        return False
