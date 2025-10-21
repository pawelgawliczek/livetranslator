from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, text, union_all
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional
from .db import SessionLocal
from .models import User, Room, RoomCost, RoomArchive
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
    archived: bool = False
    archived_at: Optional[datetime] = None
    duration_minutes: Optional[float] = None
    total_messages: Optional[int] = None

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
    include_archived: bool = Query(default=True),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get user's room history including archived (deleted) rooms
    - Returns both active and archived rooms owned by the user
    - Only returns persisted rooms if only_recorded=True
    - Includes cost information per room
    - Archived rooms show pre-calculated metrics for efficiency
    """
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    room_history_list = []
    total_stt_minutes = Decimal(0)
    total_cost = Decimal(0)

    # 1. Get active rooms
    active_query = select(Room).where(Room.owner_id == user_obj.id)
    if only_recorded:
        active_query = active_query.where(Room.recording == True)
    active_rooms = db.scalars(active_query).all()

    for room in active_rooms:
        # Get costs for this room
        costs = db.scalars(
            select(RoomCost).where(RoomCost.room_id == room.code)
        ).all()

        stt_minutes = Decimal(0)
        stt_cost = Decimal(0)
        mt_cost = Decimal(0)

        for cost in costs:
            if cost.pipeline == "stt_final":
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

        # Get message count
        message_result = db.execute(
            text("SELECT COUNT(*) FROM segments WHERE room_id = :room_id AND final = true"),
            {"room_id": room.id}
        )
        message_count = message_result.scalar() or 0

        # Calculate duration
        duration = datetime.utcnow() - room.created_at
        duration_minutes = duration.total_seconds() / 60

        room_total_cost = stt_cost + mt_cost
        total_stt_minutes += stt_minutes
        total_cost += room_total_cost

        room_history_list.append({
            "room_code": room.code,
            "created_at": room.created_at,
            "recording": room.recording,
            "is_public": room.is_public,
            "requires_login": room.requires_login,
            "max_participants": room.max_participants,
            "stt_minutes": float(stt_minutes),
            "stt_cost_usd": float(stt_cost),
            "mt_cost_usd": float(mt_cost),
            "total_cost_usd": float(room_total_cost),
            "participant_count": participant_count,
            "archived": False,
            "duration_minutes": duration_minutes,
            "total_messages": message_count
        })

    # 2. Get archived rooms if requested
    if include_archived:
        archived_query = select(RoomArchive).where(RoomArchive.owner_id == user_obj.id)
        if only_recorded:
            archived_query = archived_query.where(RoomArchive.recording == True)
        archived_rooms = db.scalars(archived_query).all()

        for room in archived_rooms:
            # Archived rooms have pre-calculated metrics
            total_stt_minutes += room.stt_minutes
            total_cost += room.total_cost_usd

            room_history_list.append({
                "room_code": room.room_code,
                "created_at": room.created_at,
                "recording": room.recording,
                "is_public": room.is_public,
                "requires_login": room.requires_login,
                "max_participants": room.max_participants,
                "stt_minutes": float(room.stt_minutes),
                "stt_cost_usd": float(room.stt_cost_usd),
                "mt_cost_usd": float(room.mt_cost_usd),
                "total_cost_usd": float(room.total_cost_usd),
                "participant_count": room.total_participants,
                "archived": True,
                "archived_at": room.archived_at,
                "duration_minutes": float(room.duration_minutes),
                "total_messages": room.total_messages
            })

    # Sort by created_at descending
    room_history_list.sort(key=lambda x: x["created_at"], reverse=True)

    # Apply pagination
    total_rooms = len(room_history_list)
    room_history_list = room_history_list[offset:offset + limit]

    # Convert to Pydantic models
    room_history_out = [RoomHistoryOut(**room) for room in room_history_list]

    return UserHistoryOut(
        total_rooms=total_rooms,
        total_stt_minutes=float(total_stt_minutes),
        total_cost_usd=float(total_cost),
        rooms=room_history_out
    )

@router.get("/stats")
def get_user_stats(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user statistics (total rooms, total minutes, etc.) including archived rooms"""
    user_email = user.get("email")
    user_obj = db.scalar(select(User).where(User.email == user_email))
    if not user_obj:
        raise HTTPException(404, "User not found")

    # Get all active rooms by user
    active_rooms = db.scalars(
        select(Room).where(Room.owner_id == user_obj.id)
    ).all()

    # Get all archived rooms
    archived_rooms = db.scalars(
        select(RoomArchive).where(RoomArchive.owner_id == user_obj.id)
    ).all()

    total_rooms = len(active_rooms) + len(archived_rooms)
    total_recorded_rooms = sum(1 for r in active_rooms if r.recording) + sum(1 for r in archived_rooms if r.recording)

    # Get costs from active rooms
    room_codes = [room.code for room in active_rooms]

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

    # Add costs from archived rooms (pre-calculated)
    for room in archived_rooms:
        total_stt_minutes += room.stt_minutes
        total_stt_cost += room.stt_cost_usd
        total_mt_cost += room.mt_cost_usd

    return {
        "total_rooms": total_rooms,
        "total_active_rooms": len(active_rooms),
        "total_archived_rooms": len(archived_rooms),
        "total_recorded_rooms": total_recorded_rooms,
        "total_stt_minutes": float(total_stt_minutes),
        "total_stt_cost_usd": float(total_stt_cost),
        "total_mt_cost_usd": float(total_mt_cost),
        "total_cost_usd": float(total_stt_cost + total_mt_cost),
        "member_since": user_obj.created_at
    }
