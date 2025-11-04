"""Admin Subscriptions API - Phase 3C US-011
Endpoints for managing subscription tiers and user subscriptions.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, or_, case
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal
from datetime import datetime, timedelta
from decimal import Decimal

from ..auth import require_admin, get_db
from ..models import User, SubscriptionTier, UserSubscription, AdminAuditLog, QuotaTransaction

router = APIRouter(prefix="/api/admin/subscriptions", tags=["admin-subscriptions"])


# ============================================================================
# Pydantic Models
# ============================================================================

class TierUpdate(BaseModel):
    """Request body for updating a subscription tier"""
    display_name: Optional[str] = Field(None, max_length=50)
    monthly_price_usd: Optional[Decimal] = Field(None, ge=0, le=999.99)
    monthly_quota_hours: Optional[Decimal] = Field(None, gt=0)
    features: Optional[List[str]] = None
    provider_tier: Optional[Literal['free', 'standard', 'premium']] = None
    stripe_price_id: Optional[str] = Field(None, max_length=100)
    apple_product_id: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None

    @validator('features')
    def validate_features(cls, v):
        if v is not None and not isinstance(v, list):
            raise ValueError('features must be a JSON array')
        return v


class ChangeTierRequest(BaseModel):
    """Request body for changing a user's subscription tier"""
    new_tier_id: int
    effective_date: Literal['immediate', 'next_renewal']
    reason: str = Field(..., min_length=20, max_length=500)


class CancelRequest(BaseModel):
    """Request body for cancelling a subscription"""
    effective_date: Literal['immediate', 'period_end']
    reason: str = Field(..., min_length=20, max_length=500)


class ReactivateRequest(BaseModel):
    """Request body for reactivating a subscription"""
    tier_id: int
    reason: str = Field(..., min_length=20, max_length=500)


# ============================================================================
# Helper Functions
# ============================================================================

def create_audit_log(
    db: Session,
    admin: User,
    action: str,
    target_user_id: Optional[int] = None,
    details: dict = None,
    ip_address: Optional[str] = None
):
    """Create an audit log entry"""
    log = AdminAuditLog(
        admin_id=admin.id,
        action=action,
        target_user_id=target_user_id,
        details=details or {},
        ip_address=ip_address
    )
    db.add(log)


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/tiers")
def get_subscription_tiers(
    include_inactive: bool = False,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all subscription tiers with active user counts.

    Query params:
    - include_inactive: Include inactive tiers (default: false)
    """
    # Build query with active user count
    query = select(
        SubscriptionTier,
        func.count(UserSubscription.user_id).filter(
            UserSubscription.status == 'active'
        ).label('active_users')
    ).outerjoin(
        UserSubscription, SubscriptionTier.id == UserSubscription.tier_id
    ).group_by(SubscriptionTier.id)

    # Filter by active status
    if not include_inactive:
        query = query.where(SubscriptionTier.is_active == True)

    query = query.order_by(SubscriptionTier.id)

    results = db.execute(query).all()

    tiers = []
    for tier, active_users in results:
        tiers.append({
            "id": tier.id,
            "tier_name": tier.tier_name,
            "display_name": tier.display_name,
            "monthly_price_usd": str(tier.monthly_price_usd),
            "monthly_quota_hours": str(tier.monthly_quota_hours) if tier.monthly_quota_hours else None,
            "features": tier.features if isinstance(tier.features, list) else [],
            "provider_tier": tier.provider_tier,
            "stripe_price_id": tier.stripe_price_id,
            "apple_product_id": tier.apple_product_id,
            "is_active": tier.is_active,
            "active_users": active_users or 0,
            "created_at": tier.created_at.isoformat(),
            "updated_at": tier.updated_at.isoformat()
        })

    return {"tiers": tiers, "total": len(tiers)}


@router.put("/tiers/{tier_id}")
def update_subscription_tier(
    tier_id: int,
    update: TierUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update subscription tier details (pricing, quotas, features).

    Business rules:
    - Cannot deactivate tier with active subscriptions
    - Cannot modify tier_name (system identifier)
    - Price/quota changes apply to new billing periods only
    """
    tier = db.get(SubscriptionTier, tier_id)
    if not tier:
        raise HTTPException(404, "Tier not found")

    # Validation: Cannot deactivate tier with active subscriptions
    if update.is_active is not None and not update.is_active and tier.is_active:
        active_count = db.scalar(
            select(func.count(UserSubscription.id))
            .where(
                UserSubscription.tier_id == tier_id,
                UserSubscription.status == 'active'
            )
        )
        if active_count and active_count > 0:
            raise HTTPException(
                403,
                f"Cannot deactivate tier with {active_count} active subscriptions"
            )

    # Track changes for audit log
    changes = {}

    # Update fields
    for field, value in update.model_dump(exclude_unset=True).items():
        if value is not None:
            old_value = getattr(tier, field)
            if old_value != value:
                changes[field] = {"old": str(old_value), "new": str(value)}
                setattr(tier, field, value)

    tier.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tier)

    # Audit log
    create_audit_log(
        db,
        admin,
        action="update_subscription_tier",
        details={
            "tier_id": tier_id,
            "tier_name": tier.tier_name,
            "changes": changes
        },
        ip_address=request.client.host if request.client else None
    )
    db.commit()

    # Get active user count for response
    active_users = db.scalar(
        select(func.count(UserSubscription.id))
        .where(
            UserSubscription.tier_id == tier_id,
            UserSubscription.status == 'active'
        )
    ) or 0

    return {
        "id": tier.id,
        "tier_name": tier.tier_name,
        "display_name": tier.display_name,
        "monthly_price_usd": str(tier.monthly_price_usd),
        "monthly_quota_hours": str(tier.monthly_quota_hours) if tier.monthly_quota_hours else None,
        "features": tier.features if isinstance(tier.features, list) else [],
        "provider_tier": tier.provider_tier,
        "stripe_price_id": tier.stripe_price_id,
        "apple_product_id": tier.apple_product_id,
        "is_active": tier.is_active,
        "active_users": active_users,
        "created_at": tier.created_at.isoformat(),
        "updated_at": tier.updated_at.isoformat()
    }


@router.get("/users")
def get_user_subscriptions(
    tier: Optional[str] = None,
    status: Optional[str] = None,
    platform: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List user subscriptions with filters and pagination.

    Query params:
    - tier: Filter by tier name (free, plus, pro)
    - status: Filter by status (active, cancelled, expired, past_due)
    - platform: Filter by platform (stripe, apple)
    - start_date: Billing period start >= date (ISO format)
    - end_date: Billing period start <= date (ISO format)
    - search: Search by user email (ILIKE pattern)
    - limit: Page size (default 50, max 100)
    - offset: Page offset (default 0)
    """
    # Limit validation
    if limit > 100:
        limit = 100

    # Build base query with joins
    query = select(
        UserSubscription,
        User.email.label('user_email'),
        SubscriptionTier.tier_name,
        SubscriptionTier.display_name.label('tier_display_name'),
        SubscriptionTier.monthly_quota_hours,
        case(
            (UserSubscription.stripe_customer_id.isnot(None), 'stripe'),
            (UserSubscription.apple_customer_id.isnot(None), 'apple'),
            else_=None
        ).label('platform')
    ).join(
        User, UserSubscription.user_id == User.id
    ).join(
        SubscriptionTier, UserSubscription.tier_id == SubscriptionTier.id
    )

    # Apply filters
    filters = []

    if tier:
        filters.append(SubscriptionTier.tier_name == tier)

    if status:
        filters.append(UserSubscription.status == status)

    if platform == 'stripe':
        filters.append(UserSubscription.stripe_customer_id.isnot(None))
    elif platform == 'apple':
        filters.append(UserSubscription.apple_customer_id.isnot(None))

    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            filters.append(UserSubscription.billing_period_start >= start_dt)
        except ValueError:
            raise HTTPException(400, "Invalid start_date format")

    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            filters.append(UserSubscription.billing_period_start <= end_dt)
        except ValueError:
            raise HTTPException(400, "Invalid end_date format")

    if search:
        filters.append(User.email.ilike(f'%{search}%'))

    if filters:
        query = query.where(and_(*filters))

    # Count total
    count_query = select(func.count()).select_from(
        query.subquery()
    )
    total = db.scalar(count_query) or 0

    # Apply ordering and pagination
    query = query.order_by(UserSubscription.created_at.desc())
    query = query.limit(limit).offset(offset)

    results = db.execute(query).all()

    # Calculate quota used for each subscription
    subscriptions = []
    for row in results:
        sub = row.UserSubscription
        user_email = row.user_email
        tier_name = row.tier_name
        tier_display_name = row.tier_display_name
        monthly_quota_hours = row.monthly_quota_hours
        platform_value = row.platform

        # Calculate quota used from quota_transactions
        quota_used_seconds = db.scalar(
            select(func.coalesce(func.sum(-QuotaTransaction.amount_seconds), 0))
            .where(
                QuotaTransaction.user_id == sub.user_id,
                QuotaTransaction.transaction_type == 'deduct',
                QuotaTransaction.created_at >= sub.billing_period_start,
                QuotaTransaction.created_at < sub.billing_period_end
            )
        ) or 0

        quota_used_hours = Decimal(quota_used_seconds) / Decimal(3600)
        bonus_credits_hours = Decimal(sub.bonus_credits_seconds) / Decimal(3600)

        subscriptions.append({
            "id": sub.id,
            "user_id": sub.user_id,
            "user_email": user_email,
            "tier_id": sub.tier_id,
            "tier_name": tier_name,
            "tier_display_name": tier_display_name,
            "status": sub.status,
            "platform": platform_value,
            "billing_period_start": sub.billing_period_start.isoformat(),
            "billing_period_end": sub.billing_period_end.isoformat(),
            "monthly_quota_hours": str(monthly_quota_hours) if monthly_quota_hours else None,
            "quota_used_seconds": int(quota_used_seconds),
            "quota_used_hours": str(quota_used_hours.quantize(Decimal('0.01'))),
            "bonus_credits_hours": str(bonus_credits_hours.quantize(Decimal('0.01'))),
            "auto_renew": sub.auto_renew,
            "stripe_customer_id": sub.stripe_customer_id,
            "stripe_subscription_id": sub.stripe_subscription_id,
            "apple_customer_id": sub.apple_customer_id,
            "created_at": sub.created_at.isoformat(),
            "updated_at": sub.updated_at.isoformat()
        })

    return {
        "subscriptions": subscriptions,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.post("/{subscription_id}/change-tier")
def change_subscription_tier(
    subscription_id: int,
    req: ChangeTierRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Change a user's subscription tier manually.

    Side effects:
    - Updates user_subscriptions.tier_id
    - If immediate: Resets billing_period_start/end, creates quota reset transaction
    - Creates admin_audit_log entry
    - (TODO: Sends email notification to user)
    """
    subscription = db.get(UserSubscription, subscription_id)
    if not subscription:
        raise HTTPException(404, "Subscription not found")

    new_tier = db.get(SubscriptionTier, req.new_tier_id)
    if not new_tier or not new_tier.is_active:
        raise HTTPException(400, "Invalid tier")

    if subscription.tier_id == req.new_tier_id:
        raise HTTPException(400, "Already on this tier")

    old_tier = subscription.tier

    if req.effective_date == 'immediate':
        # Immediate tier change
        subscription.tier_id = req.new_tier_id
        subscription.updated_at = datetime.utcnow()

        # Reset quota counters (new billing period starts now)
        subscription.billing_period_start = datetime.utcnow()
        subscription.billing_period_end = datetime.utcnow() + timedelta(days=30)

        db.commit()

        # Record quota reset transaction
        quota_tx = QuotaTransaction(
            user_id=subscription.user_id,
            transaction_type='reset',
            amount_seconds=0,
            quota_type='monthly',
            description=f"Tier changed from {old_tier.tier_name} to {new_tier.tier_name} by admin"
        )
        db.add(quota_tx)

        effective_timestamp = datetime.utcnow()
    else:
        # Schedule tier change for next renewal (store in future implementation)
        # For now, just update the tier and timestamp
        subscription.tier_id = req.new_tier_id
        subscription.updated_at = datetime.utcnow()
        db.commit()

        effective_timestamp = subscription.billing_period_end

    # Audit log
    create_audit_log(
        db,
        admin,
        action="change_subscription_tier",
        target_user_id=subscription.user_id,
        details={
            "subscription_id": subscription_id,
            "old_tier": old_tier.tier_name,
            "new_tier": new_tier.tier_name,
            "effective_date": req.effective_date,
            "reason": req.reason
        },
        ip_address=request.client.host if request.client else None
    )
    db.commit()

    # TODO: Send email notification to user
    # await send_tier_change_email(subscription.user, old_tier, new_tier)

    return {
        "subscription_id": subscription_id,
        "old_tier": old_tier.tier_name,
        "new_tier": new_tier.tier_name,
        "effective_date": effective_timestamp.isoformat(),
        "message": "Subscription tier updated successfully"
    }


@router.post("/{subscription_id}/cancel")
def cancel_subscription(
    subscription_id: int,
    req: CancelRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Cancel a user subscription.

    Side effects:
    - Sets status to 'cancelled', auto_renew to false
    - If immediate: Downgrades to free tier, updates billing_period_end
    - Creates admin_audit_log entry
    """
    subscription = db.get(UserSubscription, subscription_id)
    if not subscription:
        raise HTTPException(404, "Subscription not found")

    if subscription.status == 'cancelled':
        raise HTTPException(400, "Subscription already cancelled")

    if req.effective_date == 'immediate':
        # Downgrade to free tier immediately
        free_tier = db.scalar(
            select(SubscriptionTier).where(SubscriptionTier.tier_name == 'free')
        )
        if free_tier:
            subscription.tier_id = free_tier.id
        subscription.status = 'cancelled'
        subscription.auto_renew = False
        subscription.billing_period_end = datetime.utcnow()
        cancel_timestamp = datetime.utcnow()
    else:
        # Cancel at period end (user retains access until then)
        subscription.status = 'cancelled'
        subscription.auto_renew = False
        cancel_timestamp = subscription.billing_period_end

    subscription.updated_at = datetime.utcnow()
    db.commit()

    # Audit log
    create_audit_log(
        db,
        admin,
        action="cancel_subscription",
        target_user_id=subscription.user_id,
        details={
            "subscription_id": subscription_id,
            "effective_date": req.effective_date,
            "reason": req.reason,
            "cancelled_at": cancel_timestamp.isoformat()
        },
        ip_address=request.client.host if request.client else None
    )
    db.commit()

    return {
        "subscription_id": subscription_id,
        "status": "cancelled",
        "billing_period_end": subscription.billing_period_end.isoformat(),
        "message": f"Subscription will cancel at {cancel_timestamp.strftime('%Y-%m-%d')}"
    }


@router.post("/{subscription_id}/reactivate")
def reactivate_subscription(
    subscription_id: int,
    req: ReactivateRequest,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Reactivate a cancelled/expired subscription.

    Side effects:
    - Sets status to 'active', auto_renew to true
    - Creates new 30-day billing period
    - Resets quota counters
    - Creates admin_audit_log entry
    """
    subscription = db.get(UserSubscription, subscription_id)
    if not subscription:
        raise HTTPException(404, "Subscription not found")

    if subscription.status not in ['cancelled', 'expired']:
        raise HTTPException(400, "Can only reactivate cancelled/expired subscriptions")

    tier = db.get(SubscriptionTier, req.tier_id)
    if not tier or not tier.is_active:
        raise HTTPException(400, "Invalid tier")

    # Reactivate subscription
    subscription.tier_id = req.tier_id
    subscription.status = 'active'
    subscription.auto_renew = True
    subscription.billing_period_start = datetime.utcnow()
    subscription.billing_period_end = datetime.utcnow() + timedelta(days=30)
    subscription.updated_at = datetime.utcnow()
    db.commit()

    # Reset quota
    quota_tx = QuotaTransaction(
        user_id=subscription.user_id,
        transaction_type='reset',
        amount_seconds=0,
        quota_type='monthly',
        description=f"Subscription reactivated to {tier.tier_name} by admin"
    )
    db.add(quota_tx)

    # Audit log
    create_audit_log(
        db,
        admin,
        action="reactivate_subscription",
        target_user_id=subscription.user_id,
        details={
            "subscription_id": subscription_id,
            "tier": tier.tier_name,
            "reason": req.reason
        },
        ip_address=request.client.host if request.client else None
    )
    db.commit()

    return {
        "subscription_id": subscription_id,
        "status": "active",
        "tier": tier.tier_name,
        "billing_period_start": subscription.billing_period_start.isoformat(),
        "billing_period_end": subscription.billing_period_end.isoformat(),
        "message": "Subscription reactivated successfully"
    }


@router.get("/analytics")
def get_subscription_analytics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get subscription analytics summary (MRR, churn, tier distribution).

    Query params:
    - start_date: Analysis start date (ISO format, default: 30 days ago)
    - end_date: Analysis end date (ISO format, default: today)
    """
    # Parse dates
    if not end_date:
        end_dt = datetime.utcnow()
    else:
        try:
            end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(400, "Invalid end_date format")

    if not start_date:
        start_dt = end_dt - timedelta(days=30)
    else:
        try:
            start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(400, "Invalid start_date format")

    # Summary statistics
    total_active = db.scalar(
        select(func.count(UserSubscription.id))
        .where(UserSubscription.status == 'active')
    ) or 0

    total_cancelled = db.scalar(
        select(func.count(UserSubscription.id))
        .where(UserSubscription.status == 'cancelled')
    ) or 0

    total_expired = db.scalar(
        select(func.count(UserSubscription.id))
        .where(UserSubscription.status == 'expired')
    ) or 0

    # MRR calculation (sum of monthly prices for active subscriptions)
    mrr_usd = db.scalar(
        select(func.coalesce(func.sum(SubscriptionTier.monthly_price_usd), 0))
        .select_from(UserSubscription)
        .join(SubscriptionTier, UserSubscription.tier_id == SubscriptionTier.id)
        .where(UserSubscription.status == 'active')
    ) or Decimal('0')

    # Tier distribution
    tier_dist_query = select(
        SubscriptionTier.tier_name,
        func.count(UserSubscription.id).label('count')
    ).join(
        UserSubscription, SubscriptionTier.id == UserSubscription.tier_id
    ).where(
        UserSubscription.status == 'active'
    ).group_by(
        SubscriptionTier.tier_name
    )

    tier_dist_results = db.execute(tier_dist_query).all()
    tier_distribution = {}
    for tier_name, count in tier_dist_results:
        percentage = (count / total_active * 100) if total_active > 0 else 0
        tier_distribution[tier_name] = {
            "count": count,
            "percentage": round(percentage, 1)
        }

    # Churn rate calculation
    # Active at start of period
    active_at_start = db.scalar(
        select(func.count(UserSubscription.id))
        .where(
            UserSubscription.status == 'active',
            UserSubscription.billing_period_start < start_dt
        )
    ) or 0

    # Cancelled in period
    cancelled_in_period = db.scalar(
        select(func.count(UserSubscription.id))
        .where(
            UserSubscription.status == 'cancelled',
            UserSubscription.updated_at >= start_dt,
            UserSubscription.updated_at <= end_dt
        )
    ) or 0

    churn_rate = (cancelled_in_period / active_at_start * 100) if active_at_start > 0 else 0

    # MRR history (last 12 months)
    # Simplified - just get current MRR by tier
    mrr_history_query = select(
        SubscriptionTier.tier_name,
        func.sum(SubscriptionTier.monthly_price_usd).label('revenue')
    ).join(
        UserSubscription, SubscriptionTier.id == UserSubscription.tier_id
    ).where(
        UserSubscription.status == 'active'
    ).group_by(
        SubscriptionTier.tier_name
    )

    mrr_by_tier = {}
    for tier_name, revenue in db.execute(mrr_history_query).all():
        mrr_by_tier[tier_name] = float(revenue or 0)

    # Simple MRR history (current month only for MVP)
    current_month = datetime.utcnow().strftime('%Y-%m')
    mrr_history = [{
        "month": current_month,
        "free": mrr_by_tier.get('free', 0),
        "plus": mrr_by_tier.get('plus', 0),
        "pro": mrr_by_tier.get('pro', 0),
        "total": float(mrr_usd)
    }]

    # New/cancelled subscriptions in period
    new_subscriptions = db.scalar(
        select(func.count(UserSubscription.id))
        .where(
            UserSubscription.created_at >= start_dt,
            UserSubscription.created_at <= end_dt
        )
    ) or 0

    return {
        "summary": {
            "total_active": total_active,
            "total_cancelled": total_cancelled,
            "total_expired": total_expired,
            "mrr_usd": float(mrr_usd),
            "churn_rate": round(churn_rate, 1),
            "tier_distribution": tier_distribution
        },
        "mrr_history": mrr_history,
        "new_subscriptions": new_subscriptions,
        "cancelled_subscriptions": cancelled_in_period,
        "upgrades": 0,  # TODO: Track tier changes
        "downgrades": 0  # TODO: Track tier changes
    }
