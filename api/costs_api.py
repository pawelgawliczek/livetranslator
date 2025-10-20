from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import RoomCost

router = APIRouter(prefix="/costs", tags=["costs"])

def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally: 
        db.close()

@router.get("/room/{room_id}")
def get_room_costs(room_id: str, db: Session = Depends(get_db)):
    """Get aggregated costs for a room"""
    
    # Aggregate by pipeline
    results = db.execute(
        select(
            RoomCost.pipeline,
            RoomCost.mode,
            func.count(RoomCost.id).label('events'),
            func.sum(RoomCost.units).label('total_units'),
            func.sum(RoomCost.amount_usd).label('total_cost')
        )
        .where(RoomCost.room_id == room_id)
        .group_by(RoomCost.pipeline, RoomCost.mode)
    ).all()
    
    # Calculate totals
    total_cost = sum(r.total_cost for r in results if r.total_cost)
    
    breakdown = {}
    for r in results:
        breakdown[r.pipeline] = {
            "mode": r.mode,
            "events": r.events,
            "total_units": r.total_units,
            "cost_usd": float(r.total_cost) if r.total_cost else 0
        }
    
    return {
        "room_id": room_id,
        "total_cost_usd": float(total_cost) if total_cost else 0,
        "breakdown": breakdown
    }

@router.get("/recent")
def get_recent_costs(limit: int = 10, db: Session = Depends(get_db)):
    """Get recent cost entries across all rooms"""
    
    results = db.execute(
        select(RoomCost)
        .order_by(RoomCost.ts.desc())
        .limit(limit)
    ).scalars().all()
    
    return [{
        "room_id": r.room_id,
        "pipeline": r.pipeline,
        "mode": r.mode,
        "units": r.units,
        "unit_type": r.unit_type,
        "cost_usd": float(r.amount_usd),
        "timestamp": r.ts.isoformat()
    } for r in results]
