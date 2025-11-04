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
from ..models import Room, RoomParticipant, User, QuotaTransaction
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

class TranslationResult(BaseModel):
    """Translation result for a target language"""
    target_lang: str
    text: str
    provider: str

class TranscriptDirectResponse(BaseModel):
    """Response model for POST /api/transcript-direct"""
    success: bool
    segment_id: str
    translations: list[TranslationResult] = []
    quota_remaining_seconds: int
    quota_deducted_seconds: int

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
    2. Estimate quota usage (default 3s per sentence or use estimated_seconds)
    3. Deduct quota (check participant quota → admin fallback if exhausted)
    4. Publish to stt_events Redis channel (skip STT router)
    5. Trigger MT translation
    6. Return success with translations (synchronous for fast feedback)

    Rate Limit: 100/min per user
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
            SELECT id, user_id, quota_source, is_using_admin_quota
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

    # 3. Estimate quota usage
    # Default: 3 seconds per sentence (can be overridden by client)
    quota_seconds = request.estimated_seconds
    if quota_seconds == 3:  # Default - estimate from text
        sentence_count = request.text.count('.') + request.text.count('!') + request.text.count('?')
        sentence_count = max(1, sentence_count)  # At least 1 sentence
        quota_seconds = sentence_count * 3

    # 4. Check quota availability
    available_quota = db.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": current_user.id}
    ).scalar() or 0

    quota_user_id = current_user.id
    quota_source = "own"

    if available_quota < quota_seconds:
        # Check if room admin can provide fallback quota
        if room.owner_id != current_user.id:
            admin_quota = db.execute(
                text("SELECT get_user_quota_available(:user_id)"),
                {"user_id": room.owner_id}
            ).scalar() or 0

            if admin_quota >= quota_seconds:
                # Use admin quota
                logger.info(
                    f"User {current_user.id} exhausted quota, using admin "
                    f"{room.owner_id} quota for {quota_seconds}s"
                )
                quota_user_id = room.owner_id
                quota_source = "admin"

                # Update participant record
                db.execute(
                    text("""
                        UPDATE room_participants
                        SET is_using_admin_quota = TRUE,
                            quota_source = 'admin'
                        WHERE id = :id
                    """),
                    {"id": participant.id}
                )
                db.commit()
            else:
                # Both exhausted - return 402 Payment Required
                raise HTTPException(
                    status_code=402,
                    detail={
                        "message": "Quota exhausted",
                        "quota_exhausted": True,
                        "remaining_seconds": 0,
                        "upgrade_required": True
                    }
                )
        else:
            # Room owner exhausted their own quota
            raise HTTPException(
                status_code=402,
                detail={
                    "message": "Quota exhausted",
                    "quota_exhausted": True,
                    "remaining_seconds": available_quota,
                    "upgrade_required": True
                }
            )

    # 5. Deduct quota directly (no internal HTTP call)
    transaction = QuotaTransaction(
        user_id=quota_user_id,
        room_id=room.id,
        room_code=request.room_code,
        transaction_type="deduct",
        amount_seconds=-quota_seconds,  # Negative for deduction
        quota_type=quota_source,
        provider_used="apple_stt",
        service_type="stt",
        description=f"STT usage via apple_stt"
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    # Invalidate cache
    cache_key = f"quota:status:{quota_user_id}"
    redis_client.delete(cache_key)

    new_remaining = available_quota - quota_seconds if quota_source == "own" else available_quota

    logger.info(
        f"Quota deducted: user={quota_user_id}, amount={quota_seconds}s, "
        f"remaining={new_remaining}s, provider=apple_stt"
    )

    # 6. Generate segment_id if not provided
    segment_id = request.segment_id or f"ios_{current_user.id}_{int(datetime.utcnow().timestamp() * 1000)}"

    # 7. Publish to stt_events Redis channel (skip STT router)
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
        f"user={current_user.id}, segment={segment_id}, "
        f"quota_deducted={quota_seconds}s"
    )

    # 8. For synchronous response, we would need to wait for translations
    # For now, return success immediately (translations via WebSocket)
    # TODO: Implement synchronous translation wait with timeout

    return TranscriptDirectResponse(
        success=True,
        segment_id=segment_id,
        translations=[],  # Sent via WebSocket
        quota_remaining_seconds=new_remaining,
        quota_deducted_seconds=quota_seconds
    )
