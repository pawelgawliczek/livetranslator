from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Room, Event, User

def ensure_room(db: Session, code: str) -> int:
    r = db.scalar(select(Room).where(Room.code == code))
    if r: return r.id
    owner = db.scalar(select(User).order_by(User.id.asc()))
    r = Room(code=code, owner_id=(owner.id if owner else 1))
    db.add(r); db.commit(); db.refresh(r)
    return r.id

def save_stt_event(room_code: str, segment_id: int, revision: int, is_final: bool,
                   src_lang: str|None, text: str, translated_text: str=""):
    db = SessionLocal()
    try:
        rid = ensure_room(db, room_code)
        ev = Event(room_id=rid, segment_id=segment_id, revision=revision or 0,
                   is_final=bool(is_final), src_lang=src_lang or "auto",
                   text=text or "", translated_text=translated_text or "")
        db.add(ev); db.commit()
    finally:
        db.close()

def upsert_final_translation(room_code: str, segment_id: int,
                             src_lang: str|None, text: str, translated_text: str):
    db = SessionLocal()
    try:
        rid = ensure_room(db, room_code)
        # find latest final event for this segment
        q = (select(Event)
             .where(Event.room_id == rid, Event.segment_id == segment_id, Event.is_final == True)  # noqa: E712
             .order_by(Event.id.desc()))
        ev = db.execute(q).scalars().first()
        if ev:
            ev.translated_text = translated_text or ""
            if not ev.text: ev.text = text or ""
            if not ev.src_lang: ev.src_lang = src_lang or "auto"
            db.commit()
        else:
            ev = Event(room_id=rid, segment_id=segment_id, revision=-1, is_final=True,
                       src_lang=src_lang or "auto", text=text or "", translated_text=translated_text or "")
            db.add(ev); db.commit()
    finally:
        db.close()
