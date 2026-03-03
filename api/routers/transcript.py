"""
Transcript Direct API router for iOS app.

Handles pre-transcribed text from Apple STT (client-side transcription).
Bypasses STT router and sends directly to MT router.
"""

import logging
import json
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import text

from ..db import SessionLocal
from ..auth import get_current_user
from ..models import Room, RoomParticipant, User
import os

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["transcript"])

# Redis client for pub/sub (sync)
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

class TranscriptDirectRequest(BaseModel):
    """Request model for POST /api/transcript-direct"""
    room_code: str = Field(min_length=4, max_length=16)
    text: str = Field(min_length=1, max_length=5000)
    speaker_email: str
    is_final: bool = True
    segment_id: Optional[str] = None
    estimated_seconds: int = Field(default=3, ge=0, le=300, description="Estimated duration in seconds")
    source_lang: str = Field(default="en", pattern="^[a-z]{2}(-[A-Z]{2})?$")
    timestamp: Optional[datetime] = None

class TranscriptDirectResponse(BaseModel):
    """Response model for POST /api/transcript-direct"""
    success: bool
    segment_id: str

# ========================================
# Endpoints
# ========================================

@router.post("/transcript-direct", response_model=TranscriptDirectResponse)
def submit_transcript_direct(
    request: TranscriptDirectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    iOS sends pre-transcribed text from Apple STT.

    Flow:
    1. Validate user is participant in room
    2. Publish to stt_events Redis channel (skip STT router)
    3. Return success

    Authentication: Required (JWT)
    """
    # 1. Validate room exists
    room = db.execute(
        text("SELECT id, code, owner_id FROM rooms WHERE code = :code"),
        {"code": request.room_code}
    ).fetchone()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # 2. Check user is participant in room
    participant = db.execute(
        text("""
            SELECT id, user_id
            FROM room_participants
            WHERE room_id = :room_id
            AND user_id = :user_id
            AND is_active = TRUE
        """),
        {"room_id": room.id, "user_id": current_user.id}
    ).fetchone()

    if not participant:
        raise HTTPException(
            status_code=403,
            detail="User is not an active participant in this room"
        )

    # 3. Generate segment_id if not provided
    segment_id = request.segment_id or f"ios_{current_user.id}_{int(datetime.utcnow().timestamp() * 1000)}"

    # 4. Publish to stt_events Redis channel (skip STT router)
    stt_event = {
        "type": "transcript",
        "room_code": request.room_code,
        "room_id": room.id,
        "segment_id": segment_id,
        "text": request.text,
        "source_lang": request.source_lang,
        "speaker_email": request.speaker_email,
        "is_final": request.is_final,
        "timestamp": (request.timestamp or datetime.utcnow()).isoformat(),
        "provider": "apple_stt",
        "platform": "ios",
        "user_id": current_user.id
    }

    # Publish to Redis channel (MT router will pick it up)
    redis_client.publish("stt_events", json.dumps(stt_event))

    logger.info(
        f"iOS transcript submitted: room={request.room_code}, "
        f"user={current_user.id}, segment={segment_id}"
    )

    return TranscriptDirectResponse(
        success=True,
        segment_id=segment_id
    )
