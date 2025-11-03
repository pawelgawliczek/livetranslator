"""
Quota management API router for LiveTranslator tier system.

Handles:
- GET /api/quota/status - Real-time quota status for authenticated user
- POST /api/quota/deduct - Internal API for quota deduction (called by STT/MT/TTS routers)
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..db import SessionLocal
from ..auth import get_current_user
from ..models import User, UserSubscription, SubscriptionTier, QuotaTransaction
from ..settings import REDIS_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quota", tags=["quota"])

# Redis client for caching
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ========================================
# Pydantic Models
# ========================================

class QuotaStatusResponse(BaseModel):
    """Response model for GET /api/quota/status"""
    tier: str
    quota_seconds_total: int
    quota_seconds_used: int
    quota_seconds_remaining: int
    quota_reset_date: datetime
    grace_quota_seconds: int = 0
    alerts: list[dict] = []

class QuotaDeductRequest(BaseModel):
    """Request model for POST /api/quota/deduct"""
    user_id: int
    room_code: str
    amount_seconds: int = Field(gt=0, description="Positive seconds to deduct")
    service_type: str = Field(pattern="^(stt|mt|tts)$")
    provider_used: str
    quota_source: str = Field(default="own", pattern="^(own|admin|grace)$")

class QuotaDeductResponse(BaseModel):
    """Response model for POST /api/quota/deduct"""
    transaction_id: int
    remaining_seconds: int
    quota_exhausted: bool

# ========================================
# Endpoints
# ========================================

@router.get("/status", response_model=QuotaStatusResponse)
async def get_quota_status(
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db)
):
    """
    Get real-time quota status for authenticated user.

    Cached in Redis for 30 seconds to optimize performance.
    Cache invalidated on quota deduction.
    """
    # Check cache first
    cache_key = f"quota:status:{current_user_id}"
    cached = await redis_client.get(cache_key)

    if cached:
        logger.debug(f"Quota status cache hit for user {current_user_id}")
        import json
        data = json.loads(cached)
        # Parse datetime from ISO string
        data['quota_reset_date'] = datetime.fromisoformat(data['quota_reset_date'])
        return QuotaStatusResponse(**data)

    # Query user subscription with tier
    result = await db.execute(
        select(UserSubscription, SubscriptionTier)
        .join(SubscriptionTier, UserSubscription.tier_id == SubscriptionTier.id)
        .where(UserSubscription.user_id == current_user_id)
        .where(UserSubscription.status == 'active')
    )
    row = result.first()

    if not row:
        raise HTTPException(status_code=404, detail="No active subscription found")

    subscription, tier = row

    # Calculate quota
    monthly_quota_seconds = int((tier.monthly_quota_hours or 0) * 3600)
    bonus_seconds = subscription.bonus_credits_seconds
    grace_seconds = subscription.grace_quota_seconds
    total_quota = monthly_quota_seconds + bonus_seconds + grace_seconds

    # Get used quota in current billing period using database function
    result = await db.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": current_user_id}
    )
    available_seconds = result.scalar() or 0

    # Calculate used from available
    used_seconds = total_quota - available_seconds
    remaining_seconds = max(0, available_seconds)

    # Generate alerts
    alerts = []
    if total_quota > 0:
        usage_percent = (used_seconds / total_quota) * 100

        if usage_percent >= 95:
            alerts.append({
                "type": "critical",
                "threshold": "95_percent",
                "message": f"You've used {usage_percent:.0f}% of your quota"
            })
        elif usage_percent >= 80:
            alerts.append({
                "type": "warning",
                "threshold": "80_percent",
                "message": f"You've used {usage_percent:.0f}% of your quota"
            })

    response_data = {
        "tier": tier.tier_name,
        "quota_seconds_total": total_quota,
        "quota_seconds_used": used_seconds,
        "quota_seconds_remaining": remaining_seconds,
        "quota_reset_date": subscription.billing_period_end,
        "grace_quota_seconds": grace_seconds,
        "alerts": alerts
    }

    # Cache for 30 seconds
    import json
    cache_data = response_data.copy()
    cache_data['quota_reset_date'] = cache_data['quota_reset_date'].isoformat()
    await redis_client.setex(cache_key, 30, json.dumps(cache_data))

    logger.info(f"Quota status for user {current_user_id}: {remaining_seconds}s remaining")
    return QuotaStatusResponse(**response_data)


@router.post("/deduct", response_model=QuotaDeductResponse)
async def deduct_quota(
    request: QuotaDeductRequest,
    db: AsyncSession = Depends(get_async_db),
    x_internal_api_key: Optional[str] = Header(None)
):
    """
    Deduct quota for a user (internal API).

    Called by STT/MT/TTS routers after processing.

    Business Logic:
    1. Check user's available quota
    2. Deduct from own quota if available
    3. If exhausted, return quota_exhausted=True
    4. Create quota_transaction record
    5. Invalidate Redis cache
    """
    # TODO: Add internal API key validation in production
    # if x_internal_api_key != INTERNAL_API_KEY:
    #     raise HTTPException(status_code=403, detail="Invalid API key")

    # Get user's available quota
    result = await db.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": request.user_id}
    )
    available_seconds = result.scalar() or 0

    if available_seconds < request.amount_seconds:
        logger.warning(
            f"Quota exhausted for user {request.user_id}: "
            f"needs {request.amount_seconds}s, has {available_seconds}s"
        )
        return QuotaDeductResponse(
            transaction_id=0,
            remaining_seconds=available_seconds,
            quota_exhausted=True
        )

    # Get room_id from room_code
    result = await db.execute(
        text("SELECT id FROM rooms WHERE code = :code"),
        {"code": request.room_code}
    )
    room_id = result.scalar()

    # Create quota transaction
    transaction = QuotaTransaction(
        user_id=request.user_id,
        room_id=room_id,
        room_code=request.room_code,
        transaction_type="deduct",
        amount_seconds=-request.amount_seconds,  # Negative for deduction
        quota_type=request.quota_source,
        provider_used=request.provider_used,
        service_type=request.service_type,
        description=f"{request.service_type.upper()} usage via {request.provider_used}"
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(transaction)

    # Invalidate cache
    cache_key = f"quota:status:{request.user_id}"
    await redis_client.delete(cache_key)

    new_remaining = available_seconds - request.amount_seconds

    logger.info(
        f"Quota deducted: user={request.user_id}, amount={request.amount_seconds}s, "
        f"remaining={new_remaining}s, provider={request.provider_used}"
    )

    return QuotaDeductResponse(
        transaction_id=transaction.id,
        remaining_seconds=new_remaining,
        quota_exhausted=False
    )
