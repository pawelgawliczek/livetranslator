from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Room, Event

router = APIRouter(prefix="/rooms", tags=["rooms"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

@router.get("/{code}/events")
def list_events(code: str, limit: int = 50, db: Session = Depends(get_db)):
    room = db.scalar(select(Room).where(Room.code == code))
    if not room:
        raise HTTPException(404, "room_not_found")
    q = select(Event).where(Event.room_id == room.id).order_by(Event.id.desc()).limit(limit)
    rows = db.execute(q).scalars().all()
    return [dict(id=e.id, segment_id=e.segment_id, revision=e.revision, final=e.is_final,
                 src=e.src_lang, text=e.text, translated_text=e.translated_text,
                 created_at=e.created_at.isoformat()+"Z") for e in rows]
