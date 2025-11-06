"""
Quota management API router for LiveTranslator tier system.

Handles:
- GET /api/quota/status - Real-time quota status for authenticated user
- POST /api/quota/deduct - Internal API for quota deduction (called by STT/MT/TTS routers)
"""

import logging
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text
import asyncio

from ..db import SessionLocal
from ..auth import get_current_user
from ..models import User, UserSubscription, SubscriptionTier, QuotaTransaction
from ..settings import INTERNAL_API_KEY
from ..email_service import send_quota_email_task
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/quota", tags=["quota"])

# Redis client for caching (sync version)
import redis
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ========================================
# Dependencies
# ========================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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
def get_quota_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get real-time quota status for authenticated user.

    Cached in Redis for 30 seconds to optimize performance.
    Cache invalidated on quota deduction.
    """
    # Check cache first
    cache_key = f"quota:status:{current_user.id}"
    cached = redis_client.get(cache_key)

    if cached:
        logger.debug(f"Quota status cache hit for user {current_user.id}")
        data = json.loads(cached)
        # Parse datetime from ISO string
        data['quota_reset_date'] = datetime.fromisoformat(data['quota_reset_date'])
        return QuotaStatusResponse(**data)

    # Query user subscription with tier
    result = db.execute(
        text("""
            SELECT
                us.*,
                st.tier_name,
                st.monthly_quota_hours
            FROM user_subscriptions us
            JOIN subscription_tiers st ON us.tier_id = st.id
            WHERE us.user_id = :user_id
            AND us.status = 'active'
        """),
        {"user_id": current_user.id}
    ).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="No active subscription found")

    # Calculate quota
    monthly_quota_seconds = int((result.monthly_quota_hours or 0) * 3600)
    bonus_seconds = result.bonus_credits_seconds or 0
    grace_seconds = result.grace_quota_seconds or 0
    total_quota = monthly_quota_seconds + bonus_seconds + grace_seconds

    # Get used quota in current billing period using database function
    available_seconds = db.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": current_user.id}
    ).scalar() or 0

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
        "tier": result.tier_name,
        "quota_seconds_total": total_quota,
        "quota_seconds_used": used_seconds,
        "quota_seconds_remaining": remaining_seconds,
        "quota_reset_date": result.billing_period_end,
        "grace_quota_seconds": grace_seconds,
        "alerts": alerts
    }

    # Cache for 30 seconds
    cache_data = response_data.copy()
    cache_data['quota_reset_date'] = cache_data['quota_reset_date'].isoformat()
    redis_client.setex(cache_key, 30, json.dumps(cache_data))

    logger.info(f"Quota status for user {current_user.id}: {remaining_seconds}s remaining")
    return QuotaStatusResponse(**response_data)


@router.post("/deduct", response_model=QuotaDeductResponse)
def deduct_quota(
    request: QuotaDeductRequest,
    db: Session = Depends(get_db),
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
    # CRIT-2: Validate internal API key
    if x_internal_api_key != INTERNAL_API_KEY:
        logger.warning(f"Invalid internal API key attempt for user {request.user_id}")
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Get user's available quota
    available_seconds = db.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": request.user_id}
    ).scalar() or 0

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
    room_id = db.execute(
        text("SELECT id FROM rooms WHERE code = :code"),
        {"code": request.room_code}
    ).scalar()

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
    db.commit()
    db.refresh(transaction)

    # Invalidate cache
    cache_key = f"quota:status:{request.user_id}"
    redis_client.delete(cache_key)

    new_remaining = available_seconds - request.amount_seconds

    # === US-012: Email notification for quota thresholds ===
    # Calculate total quota for percentage
    result = db.execute(
        text("""
            SELECT us.billing_period_start, st.monthly_quota_hours
            FROM user_subscriptions us
            JOIN subscription_tiers st ON us.tier_id = st.id
            WHERE us.user_id = :user_id
        """),
        {"user_id": request.user_id}
    ).fetchone()

    if result:
        billing_period_start = result[0]
        monthly_quota_seconds = int((result[1] or 0) * 3600)
        bonus_seconds = db.execute(
            text("SELECT COALESCE(bonus_credits_seconds, 0) FROM user_subscriptions WHERE user_id = :user_id"),
            {"user_id": request.user_id}
        ).scalar() or 0
        total_quota = monthly_quota_seconds + bonus_seconds

        if total_quota > 0:
            old_percentage = (available_seconds / total_quota) * 100
            new_percentage = (new_remaining / total_quota) * 100

            # 80% warning: Trigger when crossing FROM >80% TO <=80% remaining
            if old_percentage > 20 and new_percentage <= 20:
                logger.info(
                    "quota_threshold_crossed_80",
                    extra={
                        "user_id": request.user_id,
                        "old_pct_remaining": old_percentage,
                        "new_pct_remaining": new_percentage
                    }
                )

                # Send email asynchronously (don't block quota deduction)
                # P0-1 FIX: Use wrapper that creates own DB session
                asyncio.create_task(
                    send_quota_email_task(
                        user_id=request.user_id,
                        notification_type="quota_80",
                        percentage=80,  # 80% used = 20% remaining
                        remaining_seconds=new_remaining,
                        billing_period_start=billing_period_start
                    )
                )

            # 100% exhaustion: Send once per billing period
            elif new_remaining <= 0:
                logger.info(
                    "quota_exhausted",
                    extra={
                        "user_id": request.user_id,
                        "billing_period_start": billing_period_start
                    }
                )

                # Send email asynchronously
                # P0-1 FIX: Use wrapper that creates own DB session
                asyncio.create_task(
                    send_quota_email_task(
                        user_id=request.user_id,
                        notification_type="quota_100",
                        percentage=100,
                        remaining_seconds=0,
                        billing_period_start=billing_period_start
                    )
                )
    # === END US-012 ===

    logger.info(
        f"Quota deducted: user={request.user_id}, amount={request.amount_seconds}s, "
        f"remaining={new_remaining}s, provider={request.provider_used}"
    )

    return QuotaDeductResponse(
        transaction_id=transaction.id,
        remaining_seconds=new_remaining,
        quota_exhausted=False
    )
