import asyncio
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select, text, or_
from sqlalchemy.orm import Session
from .db import SessionLocal
from .models import Room
from .jwt_tools import verify_token

# Import working OpenAI translation
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'routers', 'mt'))
from openai_backend import translate_text as openai_translate

router = APIRouter(prefix="/api/history", tags=["history"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(authorization: str = Header(None)) -> dict:
    """Extract user from JWT token."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization[7:]  # Remove "Bearer " prefix
    try:
        claims = verify_token(token)
        return claims
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

@router.get("/rooms")
def get_rooms_list(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """Get list of rooms - user's own rooms and public rooms"""

    user_id = int(user.get("sub"))

    # Get rooms that are either:
    # 1. Owned by the current user, OR
    # 2. Public (is_public = True)
    rooms = db.execute(
        select(Room)
        .where(or_(Room.owner_id == user_id, Room.is_public == True))
        .order_by(Room.created_at.desc())
    ).scalars().all()

    return {
        "count": len(rooms),
        "rooms": [
            {
                "id": room.id,
                "code": room.code,
                "created_at": room.created_at.isoformat() if room.created_at else None,
                "is_public": room.is_public,
                "is_owner": room.owner_id == user_id
            }
            for room in rooms
        ]
    }

@router.get("/room/{room_code}")
async def get_room_history(room_code: str, target_lang: str = "en", limit: int = 100, db: Session = Depends(get_db)):
    """Get chat history for a room with translations. Auto-translates missing languages."""
    
    # Get room
    room = db.execute(
        select(Room).where(Room.code == room_code)
    ).scalar_one_or_none()
    
    if not room:
        raise HTTPException(404, "Room not found")
    
    # Get segments with translations - FIXED: Use room_code for translations join
    result = db.execute(
        text("""
        SELECT 
            s.segment_id, 
            s.speaker_id, 
            s.text as original_text, 
            s.lang as source_lang, 
            s.final, 
            s.ts_iso,
            t.text as translated_text,
            t.tgt_lang
        FROM segments s
        LEFT JOIN translations t ON t.room_id = :room_code
            AND t.segment_id = CAST(s.segment_id AS INTEGER) 
            AND t.tgt_lang = :target_lang
            AND t.is_final = true
        WHERE s.room_id = :room_id AND s.final = true
        ORDER BY s.id ASC
        LIMIT :limit
        """),
        {"room_id": room.id, "room_code": room_code, "target_lang": target_lang, "limit": limit}
    )
    
    segments = result.fetchall()
    
    # Process segments - translate missing ones
    processed_segments = []
    translations_to_save = []
    
    for s in segments:
        segment_id = s[0]
        speaker = s[1]
        original_text = s[2]
        source_lang = s[3]
        final = s[4]
        timestamp = s[5]
        translated_text = s[6]
        stored_tgt_lang = s[7]
        
        # If translation doesn't exist and target_lang != source_lang, translate it
        # Also handle "auto" as source lang - only translate if no cached translation exists
        if not translated_text and target_lang != source_lang and source_lang != target_lang:
            try:
                print(f"[History] Translating segment {segment_id}: {source_lang}→{target_lang}")
                translated_text = await openai_translate(original_text, source_lang, target_lang)
                
                # Queue for saving
                translations_to_save.append({
                    "room_code": room_code,
                    "segment_id": segment_id,
                    "src_lang": source_lang,
                    "tgt_lang": target_lang,
                    "text": translated_text
                })
            except Exception as e:
                print(f"[History] Translation failed for segment {segment_id}: {e}")
                translated_text = original_text  # Fallback
        
        processed_segments.append({
            "segment_id": segment_id,
            "speaker": speaker,
            "original_text": original_text,
            "source_lang": source_lang,
            "final": final,
            "timestamp": timestamp,
            "translated_text": translated_text or original_text,
            "target_lang": target_lang
        })
    
    # Save new translations to database
    if translations_to_save:
        for trans in translations_to_save:
            try:
                db.execute(
                    text("""
                    INSERT INTO translations (room_id, segment_id, src_lang, tgt_lang, text, is_final, ts_iso, created_at)
                    VALUES (:room_id, :segment_id, :src_lang, :tgt_lang, :text, true, NOW(), NOW())
                    ON CONFLICT (room_id, segment_id, tgt_lang) 
                    DO UPDATE SET text = EXCLUDED.text, ts_iso = NOW()
                    """),
                    {
                        "room_id": room_code,
                        "segment_id": trans["segment_id"],
                        "src_lang": trans["src_lang"],
                        "tgt_lang": trans["tgt_lang"],
                        "text": trans["text"]
                    }
                )
                db.commit()
                print(f"[History] ✓ Cached translation: seg={trans['segment_id']} {trans['src_lang']}→{trans['tgt_lang']}")
            except Exception as e:
                print(f"[History] Failed to cache translation: {e}")
    
    return {
        "room_code": room_code,
        "room_id": room.id,
        "target_lang": target_lang,
        "count": len(processed_segments),
        "segments": processed_segments
    }
