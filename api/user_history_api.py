from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, text
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from .db import SessionLocal
from .models import User, Room, RoomCost
from .auth_deps import get_current_user

router = APIRouter(prefix="/api/user/history", tags=["user-history"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class RoomHistoryOut(BaseModel):
    room_code: str
    created_at: datetime
    recording: bool
    is_public: bool
    requires_login: bool
    max_participants: int
    stt_minutes: float
    stt_cost_usd: float
    mt_cost_usd: float
    total_cost_usd: float
    participant_count: int

class UserHistoryOut(BaseModel):
    total_rooms: int
    total_stt_minutes: float
    total_cost_usd: float
    rooms: List[RoomHistoryOut]

@router.get("", response_model=UserHistoryOut)
def get_user_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    only_recorded: bool = Query(default=True),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's room history
    - Only returns rooms owned by the user
    - Only returns persisted rooms if only_recorded=True
    - Includes cost information per room
    """
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    # Build query
    query = select(Room).where(Room.owner_id == user_obj.id)

    if only_recorded:
        query = query.where(Room.recording == True)

    query = query.order_by(Room.created_at.desc())

    # Get total count
    total_query = query.with_only_columns(Room.id)
    total_rooms = len(db.scalars(total_query).all())

    # Apply pagination
    query = query.limit(limit).offset(offset)
    rooms = db.scalars(query).all()

    # Get cost and participant info for each room
    room_history_list = []
    total_stt_minutes = Decimal(0)
    total_cost = Decimal(0)

    for room in rooms:
        # Get costs for this room
        costs = db.scalars(
            select(RoomCost).where(RoomCost.room_id == room.code)
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

        # Get participant count
        participant_result = db.execute(
            text("""
                SELECT COUNT(DISTINCT user_id) as count
                FROM room_participants
                WHERE room_id = :room_id AND user_id IS NOT NULL
            """),
            {"room_id": room.id}
        )
        participant_count = participant_result.scalar() or 0

        room_total_cost = stt_cost + mt_cost
        total_stt_minutes += stt_minutes
        total_cost += room_total_cost

        room_history_list.append(RoomHistoryOut(
            room_code=room.code,
            created_at=room.created_at,
            recording=room.recording,
            is_public=room.is_public,
            requires_login=room.requires_login,
            max_participants=room.max_participants,
            stt_minutes=float(stt_minutes),
            stt_cost_usd=float(stt_cost),
            mt_cost_usd=float(mt_cost),
            total_cost_usd=float(room_total_cost),
            participant_count=participant_count
        ))

    return UserHistoryOut(
        total_rooms=total_rooms,
        total_stt_minutes=float(total_stt_minutes),
        total_cost_usd=float(total_cost),
        rooms=room_history_list
    )

@router.get("/stats")
def get_user_stats(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user statistics (total rooms, total minutes, etc.)"""
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    # Get all rooms by user
    rooms = db.scalars(
        select(Room).where(Room.owner_id == user_obj.id)
    ).all()

    total_rooms = len(rooms)
    total_recorded_rooms = sum(1 for r in rooms if r.recording)

    # Get all costs
    room_codes = [room.code for room in rooms]

    total_stt_minutes = Decimal(0)
    total_stt_cost = Decimal(0)
    total_mt_cost = Decimal(0)

    for room_code in room_codes:
        costs = db.scalars(
            select(RoomCost).where(RoomCost.room_id == room_code)
        ).all()

        for cost in costs:
            if cost.pipeline == "stt_final":
                if cost.units:
                    total_stt_minutes += Decimal(cost.units) / Decimal(60)
                total_stt_cost += cost.amount_usd
            elif cost.pipeline == "mt":
                total_mt_cost += cost.amount_usd

    return {
        "total_rooms": total_rooms,
        "total_recorded_rooms": total_recorded_rooms,
        "total_stt_minutes": float(total_stt_minutes),
        "total_stt_cost_usd": float(total_stt_cost),
        "total_mt_cost_usd": float(total_mt_cost),
        "total_cost_usd": float(total_stt_cost + total_mt_cost),
        "member_since": user_obj.created_at
    }
