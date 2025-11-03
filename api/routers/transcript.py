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
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis

from ..db import get_async_db
from ..auth import get_current_user_id
from ..models import Room, RoomParticipant, User
from ..settings import REDIS_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["transcript"])

# Redis client for pub/sub
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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
async def submit_transcript_direct(
    request: TranscriptDirectRequest,
    current_user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_async_db)
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
    result = await db.execute(
        select(Room).where(Room.code == request.room_code)
    )
    room = result.scalar_one_or_none()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # 2. Check user is participant in room
    result = await db.execute(
        select(RoomParticipant)
        .where(RoomParticipant.room_id == room.id)
        .where(RoomParticipant.user_id == current_user_id)
        .where(RoomParticipant.is_active == True)
    )
    participant = result.scalar_one_or_none()

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
    result = await db.execute(
        text("SELECT get_user_quota_available(:user_id)"),
        {"user_id": current_user_id}
    )
    available_quota = result.scalar() or 0

    if available_quota < quota_seconds:
        # Check if room admin can provide fallback quota
        if room.owner_id != current_user_id:
            result = await db.execute(
                text("SELECT get_user_quota_available(:user_id)"),
                {"user_id": room.owner_id}
            )
            admin_quota = result.scalar() or 0

            if admin_quota >= quota_seconds:
                # Use admin quota
                logger.info(
                    f"User {current_user_id} exhausted quota, using admin "
                    f"{room.owner_id} quota for {quota_seconds}s"
                )
                quota_user_id = room.owner_id
                quota_source = "admin"

                # Update participant record
                participant.is_using_admin_quota = True
                participant.quota_source = "admin"
                await db.commit()
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
    else:
        # Use participant's own quota
        quota_user_id = current_user_id
        quota_source = "own"

    # 5. Deduct quota via internal API
    from .quota import QuotaDeductRequest
    quota_request = QuotaDeductRequest(
        user_id=quota_user_id,
        room_code=request.room_code,
        amount_seconds=quota_seconds,
        service_type="stt",  # Apple STT (free for us, but count toward quota)
        provider_used="apple_stt",
        quota_source=quota_source
    )

    # Call quota deduction (internal)
    import httpx
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/quota/deduct",
            json=quota_request.dict(),
            headers={"X-Internal-API-Key": "internal"}  # TODO: Use actual key
        )

        if response.status_code != 200:
            logger.error(f"Quota deduction failed: {response.text}")
            raise HTTPException(
                status_code=500,
                detail="Failed to deduct quota"
            )

        quota_response = response.json()

    # 6. Generate segment_id if not provided
    segment_id = request.segment_id or f"ios_{current_user_id}_{int(datetime.utcnow().timestamp() * 1000)}"

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
        "user_id": current_user_id
    }

    # Publish to Redis channel (MT router will pick it up)
    await redis_client.publish("stt_events", json.dumps(stt_event))

    logger.info(
        f"iOS transcript submitted: room={request.room_code}, "
        f"user={current_user_id}, segment={segment_id}, "
        f"quota_deducted={quota_seconds}s"
    )

    # 8. For synchronous response, we would need to wait for translations
    # For now, return success immediately (translations via WebSocket)
    # TODO: Implement synchronous translation wait with timeout

    return TranscriptDirectResponse(
        success=True,
        segment_id=segment_id,
        translations=[],  # Sent via WebSocket
        quota_remaining_seconds=quota_response["remaining_seconds"],
        quota_deducted_seconds=quota_seconds
    )
