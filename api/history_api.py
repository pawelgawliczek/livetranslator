from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Room

router = APIRouter(prefix="/history", tags=["history"])

def get_db():
    db = SessionLocal()
    try: 
        yield db
    finally: 
        db.close()

@router.get("/room/{room_code}")
def get_room_history(room_code: str, limit: int = 100, db: Session = Depends(get_db)):
    """Get chat history for a room"""
    
    # Get room
    room = db.execute(
        select(Room).where(Room.code == room_code)
    ).scalar_one_or_none()
    
    if not room:
        raise HTTPException(404, "Room not found")
    
    # Get segments using text()
    result = db.execute(
        text("""
        SELECT segment_id, speaker_id, text, lang, final, ts_iso
        FROM segments
        WHERE room_id = :room_id
        ORDER BY id ASC
        LIMIT :limit
        """),
        {"room_id": room.id, "limit": limit}
    )
    
    segments = result.fetchall()
    
    return {
        "room_code": room_code,
        "room_id": room.id,
        "count": len(segments),
        "segments": [
            {
                "segment_id": s[0],
                "speaker": s[1],
                "text": s[2],
                "lang": s[3],
                "final": s[4],
                "timestamp": s[5]
            }
            for s in segments
        ]
    }
