from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from .db import SessionLocal
from .models import User, UserSubscription, SubscriptionTier
from .auth_deps import get_current_user

router = APIRouter(prefix="/api/subscription", tags=["subscription"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class SubscriptionOut(BaseModel):
    id: int
    plan: str
    status: str
    monthly_quota_minutes: Optional[int]
    billing_period_start: datetime
    billing_period_end: datetime
    created_at: datetime
    updated_at: datetime
    grace_period_end: Optional[datetime] = None  # US-007: Failed payment grace period

class SubscriptionPlanIn(BaseModel):
    plan: str  # free, plus, pro

# Plan configurations
PLAN_CONFIG = {
    "free": {
        "monthly_quota_minutes": 60,  # 1 hour per month
        "features": ["Basic translation", "1 hour per month"]
    },
    "plus": {
        "monthly_quota_minutes": None,  # Unlimited
        "features": ["Unlimited translation", "Priority support", "Advanced features"]
    },
    "pro": {
        "monthly_quota_minutes": None,  # Unlimited
        "features": ["Unlimited translation", "24/7 support", "Advanced features", "API access"]
    }
}

@router.get("", response_model=SubscriptionOut)
def get_subscription(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user's subscription"""
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    subscription = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_obj.id))

    if not subscription:
        # Create default free subscription
        subscription = UserSubscription(
            user_id=user_obj.id,
            plan="free",
            status="active",
            monthly_quota_minutes=60,
            billing_period_start=datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
            billing_period_end=(datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0) + relativedelta(months=1))
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

    # Get plan name from tier_id (new schema) or plan field (legacy)
    plan_name = subscription.plan  # Default to legacy field
    if subscription.tier_id:
        tier = db.get(SubscriptionTier, subscription.tier_id)
        if tier:
            plan_name = tier.tier_name

    return SubscriptionOut(
        id=subscription.id,
        plan=plan_name,
        status=subscription.status,
        monthly_quota_minutes=subscription.monthly_quota_minutes,
        billing_period_start=subscription.billing_period_start,
        billing_period_end=subscription.billing_period_end,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
        grace_period_end=subscription.grace_period_end
    )

@router.patch("", response_model=SubscriptionOut)
def update_subscription(
    plan_update: SubscriptionPlanIn,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user subscription plan"""
    if plan_update.plan not in PLAN_CONFIG:
        raise HTTPException(400, "Invalid plan")

    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    subscription = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_obj.id))

    if not subscription:
        raise HTTPException(404, "Subscription not found")

    # Update plan
    subscription.plan = plan_update.plan
    subscription.monthly_quota_minutes = PLAN_CONFIG[plan_update.plan]["monthly_quota_minutes"]
    subscription.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(subscription)

    return SubscriptionOut(
        id=subscription.id,
        plan=subscription.plan,
        status=subscription.status,
        monthly_quota_minutes=subscription.monthly_quota_minutes,
        billing_period_start=subscription.billing_period_start,
        billing_period_end=subscription.billing_period_end,
        created_at=subscription.created_at,
        updated_at=subscription.updated_at,
        grace_period_end=subscription.grace_period_end
    )

@router.get("/plans")
def get_plans():
    """Get available subscription plans"""
    return PLAN_CONFIG

@router.get("/tiers")
def get_subscription_tiers(db: Session = Depends(get_db)):
    """
    Get all active subscription tiers with pricing and features.
    Public endpoint (no auth required) for pricing page.
    """
    tiers = db.scalars(
        select(SubscriptionTier)
        .where(SubscriptionTier.is_active == True)
        .order_by(SubscriptionTier.monthly_price_usd)
    ).all()

    # Calculate quota in seconds for compatibility
    return {
        "tiers": [
            {
                "id": tier.id,
                "name": tier.tier_name,
                "display_name": tier.display_name,
                "plan": tier.tier_name.lower(),
                "price_usd": float(tier.monthly_price_usd or 0),
                "monthly_quota_seconds": int(float(tier.monthly_quota_hours or 0) * 3600) if tier.monthly_quota_hours else 0,
                "stripe_price_id": tier.stripe_price_id,
                "features": {
                    "basic_translation": True,
                    "premium_providers": tier.tier_name.lower() in ["plus", "pro"],
                    "server_tts": tier.tier_name.lower() == "pro",
                    "priority_support": tier.tier_name.lower() == "pro"
                }
            }
            for tier in tiers
        ]
    }
