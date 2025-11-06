from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from .db import SessionLocal
from .models import User, UserSubscription, UserUsage, RoomCost, Room, SubscriptionTier
from .auth_deps import get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class RoomUsageOut(BaseModel):
    room_code: str
    stt_minutes: float
    stt_cost_usd: float
    mt_cost_usd: float
    total_cost_usd: float
    created_at: datetime

class BillingPeriodUsageOut(BaseModel):
    billing_period_start: datetime
    billing_period_end: datetime
    total_stt_minutes: float
    total_stt_cost_usd: float
    total_mt_cost_usd: float
    total_cost_usd: float
    quota_minutes: Optional[int]
    quota_remaining_minutes: Optional[float]
    rooms: List[RoomUsageOut]

@router.get("/usage", response_model=BillingPeriodUsageOut)
def get_current_usage(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current billing period usage"""
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    # Get subscription
    subscription = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_obj.id))
    if not subscription:
        raise HTTPException(404, "Subscription not found")

    billing_start = subscription.billing_period_start
    billing_end = subscription.billing_period_end

    # Get all rooms owned by user in current billing period
    rooms = db.scalars(
        select(Room).where(
            and_(
                Room.owner_id == user_obj.id,
                Room.created_at >= billing_start,
                Room.created_at < billing_end
            )
        )
    ).all()

    room_codes = [room.code for room in rooms]

    # Aggregate costs by room
    room_usage_list = []
    total_stt_minutes = Decimal(0)
    total_stt_cost = Decimal(0)
    total_mt_cost = Decimal(0)

    for room_code in room_codes:
        # Get costs for this room
        costs = db.scalars(
            select(RoomCost).where(
                and_(
                    RoomCost.room_id == room_code,
                    RoomCost.ts >= billing_start,
                    RoomCost.ts < billing_end
                )
            )
        ).all()

        stt_minutes = Decimal(0)
        stt_cost = Decimal(0)
        mt_cost = Decimal(0)

        for cost in costs:
            if cost.pipeline == "stt_final":
                # Convert units (seconds) to minutes
                if cost.units:
                    stt_minutes += Decimal(cost.units) / Decimal(60)
                stt_cost += cost.amount_usd
            elif cost.pipeline == "mt":
                mt_cost += cost.amount_usd

        if stt_minutes > 0 or stt_cost > 0 or mt_cost > 0:
            room_usage_list.append(RoomUsageOut(
                room_code=room_code,
                stt_minutes=float(stt_minutes),
                stt_cost_usd=float(stt_cost),
                mt_cost_usd=float(mt_cost),
                total_cost_usd=float(stt_cost + mt_cost),
                created_at=costs[0].ts if costs else datetime.utcnow()
            ))

            total_stt_minutes += stt_minutes
            total_stt_cost += stt_cost
            total_mt_cost += mt_cost

    # Calculate remaining quota - use tier quota if available
    quota_minutes = subscription.monthly_quota_minutes
    if subscription.tier_id:
        tier = db.get(SubscriptionTier, subscription.tier_id)
        if tier and tier.monthly_quota_hours:
            quota_minutes = int(tier.monthly_quota_hours * 60)

    quota_remaining = None
    if quota_minutes is not None:
        quota_remaining = quota_minutes - float(total_stt_minutes)

    return BillingPeriodUsageOut(
        billing_period_start=billing_start,
        billing_period_end=billing_end,
        total_stt_minutes=float(total_stt_minutes),
        total_stt_cost_usd=float(total_stt_cost),
        total_mt_cost_usd=float(total_mt_cost),
        total_cost_usd=float(total_stt_cost + total_mt_cost),
        quota_minutes=quota_minutes,
        quota_remaining_minutes=quota_remaining,
        rooms=room_usage_list
    )

@router.get("/usage/room/{room_code}", response_model=RoomUsageOut)
def get_room_usage(
    room_code: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get usage for a specific room"""
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    # Check if user owns this room
    room = db.scalar(select(Room).where(Room.code == room_code))
    if not room or room.owner_id != user_obj.id:
        raise HTTPException(404, "Room not found or not owned by user")

    # Get costs for this room
    costs = db.scalars(
        select(RoomCost).where(RoomCost.room_id == room_code)
    ).all()

    stt_minutes = Decimal(0)
    stt_cost = Decimal(0)
    mt_cost = Decimal(0)

    for cost in costs:
        if cost.pipeline == "stt_final":
            # Convert units (seconds) to minutes
            if cost.units:
                stt_minutes += Decimal(cost.units) / Decimal(60)
            stt_cost += cost.amount_usd
        elif cost.pipeline == "mt":
            mt_cost += cost.amount_usd

    return RoomUsageOut(
        room_code=room_code,
        stt_minutes=float(stt_minutes),
        stt_cost_usd=float(stt_cost),
        mt_cost_usd=float(mt_cost),
        total_cost_usd=float(stt_cost + mt_cost),
        created_at=costs[0].ts if costs else datetime.utcnow()
    )

@router.get("/quota")
def get_quota_status(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get quota status (remaining minutes, etc.)"""
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    subscription = db.scalar(select(UserSubscription).where(UserSubscription.user_id == user_obj.id))
    if not subscription:
        raise HTTPException(404, "Subscription not found")

    # Get quota from tier (new schema) or subscription (legacy)
    quota_minutes = subscription.monthly_quota_minutes  # Legacy default
    plan_name = subscription.plan
    is_unlimited = False

    if subscription.tier_id:
        tier = db.get(SubscriptionTier, subscription.tier_id)
        if tier:
            plan_name = tier.tier_name
            if tier.monthly_quota_hours:
                quota_minutes = int(tier.monthly_quota_hours * 60)
            else:
                is_unlimited = True
                quota_minutes = None

    # Get current usage
    usage = get_current_usage(user=user, db=db)

    return {
        "plan": plan_name,
        "quota_minutes": quota_minutes,
        "used_minutes": usage.total_stt_minutes,
        "remaining_minutes": usage.quota_remaining_minutes if quota_minutes else None,
        "is_unlimited": is_unlimited,
        "billing_period_start": subscription.billing_period_start,
        "billing_period_end": subscription.billing_period_end
    }
