"""
API endpoints for room management.

Handles:
- Creating new rooms
- Listing user's rooms
- Getting room details
- Getting room participants
"""

from fastapi import APIRouter, HTTPException, Depends, Header, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
import redis
import json
import os

from .db import SessionLocal
from .models import Room, RoomArchive, RoomSpeaker
from .jwt_tools import verify_token
from .auth import get_optional_current_user

router = APIRouter(prefix="/api/rooms", tags=["rooms"])

# Redis for cache invalidation
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
CACHE_CLEAR_CHANNEL = "stt_cache_clear"


class CreateRoomRequest(BaseModel):
    """Request to create a new room."""
    code: str
    is_public: Optional[bool] = False
    requires_login: Optional[bool] = False
    max_participants: Optional[int] = 10


class RoomResponse(BaseModel):
    """Response with room details."""
    id: int
    code: str
    owner_id: int
    is_owner: bool = False  # Whether the current user is the room owner
    is_public: bool
    recording: bool
    requires_login: bool
    max_participants: int
    created_at: datetime
    admin_left_at: datetime | None = None
    discovery_mode: str = "disabled"
    speakers_locked: bool = False


class RoomStatusResponse(BaseModel):
    """Room status including admin presence."""
    code: str
    admin_present: bool
    admin_left_at: datetime | None = None
    expires_at: datetime | None = None  # When room will be deleted (admin_left_at + 30 min)

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat() + 'Z' if v else None
        }


def get_db():
    """Get database session."""
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


class ParticipantInfo(BaseModel):
    """Information about a connected participant."""
    display_name: str
    email: str
    is_guest: bool
    preferred_lang: str
    is_speaking: bool


class ParticipantsResponse(BaseModel):
    """Response with list of participants."""
    participants: List[ParticipantInfo]


@router.post("", response_model=RoomResponse)
async def create_room(
    request: CreateRoomRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Create a new room.

    Requires authentication. The authenticated user becomes the room owner.

    Args:
        request: Room creation parameters
        db: Database session
        user: Authenticated user from JWT token

    Returns:
        RoomResponse with created room details

    Raises:
        HTTPException: 400 if room code already exists
    """
    user_id = user.get("sub")

    # Check if room code already exists in active rooms
    existing_room = db.query(Room).filter(Room.code == request.code).first()
    if existing_room:
        raise HTTPException(status_code=400, detail="Room code already exists")

    # Check if room code exists in archived rooms
    # This prevents reusing codes that would violate the unique constraint on room_archive
    archived_room = db.query(RoomArchive).filter(RoomArchive.room_code == request.code).first()
    if archived_room:
        raise HTTPException(status_code=400, detail="Room code already exists in archive. Please choose a different code.")

    # Create new room
    room = Room(
        code=request.code,
        owner_id=user_id,
        is_public=request.is_public,
        requires_login=request.requires_login,
        max_participants=request.max_participants,
        recording=False,  # Default to not recording
        created_at=datetime.utcnow()
    )

    db.add(room)
    db.commit()
    db.refresh(room)

    return RoomResponse(
        id=room.id,
        code=room.code,
        owner_id=room.owner_id,
        is_public=room.is_public,
        recording=room.recording,
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at,
        admin_left_at=room.admin_left_at,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


@router.post("/multi-speaker", response_model=RoomResponse)
async def create_multi_speaker_room(
    request: CreateRoomRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Create a new multi-speaker room with discovery mode enabled.

    This is a specialized endpoint for creating rooms designed for multi-speaker
    diarization (single device, multiple speakers). The room is created with
    discovery_mode set to 'enabled' so speakers can be enrolled immediately.

    Args:
        request: Room creation parameters
        db: Database session
        user: Authenticated user from JWT token

    Returns:
        RoomResponse with created room details (discovery_mode='enabled')

    Raises:
        HTTPException: 400 if room code already exists
    """
    user_id = user.get("sub")

    # Check if room code already exists in active rooms
    existing_room = db.query(Room).filter(Room.code == request.code).first()
    if existing_room:
        raise HTTPException(status_code=400, detail="Room code already exists")

    # Check if room code exists in archived rooms
    archived_room = db.query(RoomArchive).filter(RoomArchive.room_code == request.code).first()
    if archived_room:
        raise HTTPException(status_code=400, detail="Room code already exists in archive. Please choose a different code.")

    # Create new multi-speaker room with discovery mode enabled
    room = Room(
        code=request.code,
        owner_id=user_id,
        is_public=request.is_public,
        requires_login=request.requires_login,
        max_participants=request.max_participants,
        recording=False,
        created_at=datetime.utcnow(),
        discovery_mode='enabled',  # Start in discovery mode
        speakers_locked=False  # Not locked yet, will be locked when discovery completes
    )

    db.add(room)
    db.commit()
    db.refresh(room)

    return RoomResponse(
        id=room.id,
        code=room.code,
        owner_id=room.owner_id,
        is_public=room.is_public,
        recording=room.recording,
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at,
        admin_left_at=room.admin_left_at,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


@router.get("/{room_code}", response_model=RoomResponse)
async def get_room(
    room_code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_optional_current_user)
):
    """
    Get room details by room code.

    Args:
        room_code: The room code to look up
        db: Database session
        user: Optional authenticated user

    Returns:
        RoomResponse with room details

    Raises:
        HTTPException: 404 if room not found
    """
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Determine if current user is the owner
    is_owner = False
    if user:
        user_id = int(user.get("sub", 0))
        is_owner = (user_id == room.owner_id)

    return RoomResponse(
        id=room.id,
        code=room.code,
        owner_id=room.owner_id,
        is_owner=is_owner,
        is_public=room.is_public,
        recording=room.recording,
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at,
        admin_left_at=room.admin_left_at,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


@router.get("/{room_code}/participants", response_model=ParticipantsResponse)
async def get_room_participants(
    room_code: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Get list of participants currently connected to a room.

    Args:
        room_code: The room code
        request: FastAPI request object (to access app state)
        user: Authenticated user

    Returns:
        ParticipantsResponse with list of connected participants

    Note:
        This endpoint checks WebSocket connections via the ws_manager.
        Returns participant info including display name, language preferences, and speaking status.
    """
    # Access ws_manager from app state
    wsman = getattr(request.app.state, 'wsman', None)
    if not wsman:
        raise HTTPException(status_code=500, detail="WebSocket manager not available")

    # Get all WebSocket connections for this room
    room_connections = wsman.rooms.get(room_code, set())

    # Group connections by user to deduplicate (same user with multiple tabs/devices)
    user_map = {}

    for ws in room_connections:
        # Extract user info from WebSocket state
        user_email = getattr(ws.state, 'email', 'Unknown')
        user_id = getattr(ws.state, 'user', None)

        # Use user_id as the unique key (handles both authenticated users and guests)
        unique_key = str(user_id) if user_id else user_email

        # Determine if guest by checking user_id format
        is_guest = user_id and str(user_id).startswith('guest:')

        # Extract display name
        if is_guest:
            # For guests, user_id format is "guest:{name}:{timestamp}"
            parts = str(user_id).split(':', 2)
            display_name = parts[1] if len(parts) > 1 else 'Guest'
        else:
            display_name = user_email.split('@')[0] if '@' in user_email else user_email

        # Get user's preferred language
        preferred_lang = getattr(ws.state, 'preferred_lang', 'en')

        # Store or update user info (last connection wins for language preference)
        user_map[unique_key] = ParticipantInfo(
            display_name=display_name,
            email=user_email,
            is_guest=is_guest,
            preferred_lang=preferred_lang,
            is_speaking=False
        )

    # Convert map to list
    participants = list(user_map.values())

    return ParticipantsResponse(participants=participants)


class UpdateRecordingRequest(BaseModel):
    """Request to update room recording setting."""
    recording: bool


@router.patch("/{room_code}/recording", response_model=RoomResponse)
async def update_room_recording(
    room_code: str,
    request: UpdateRecordingRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Toggle room recording/persistence setting.

    Args:
        room_code: The room code
        request: Recording setting update
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        RoomResponse with updated room details

    Raises:
        HTTPException: 404 if room not found, 403 if not owner
    """
    user_id = int(user.get("sub"))

    # Get room - support both sync and async sessions
    if hasattr(db, 'execute'):
        # AsyncSession
        result = await db.execute(select(Room).where(Room.code == room_code))
        room = result.scalar_one_or_none()
    else:
        # Sync Session
        room = db.query(Room).filter(Room.code == room_code).first()

    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify user owns the room
    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can modify recording settings")

    # Update recording setting
    room.recording = request.recording

    # Commit - support both sync and async
    if hasattr(db, 'execute'):
        await db.commit()
        await db.refresh(room)
    else:
        db.commit()
        db.refresh(room)

    return RoomResponse(
        id=room.id,
        code=room.code,
        owner_id=room.owner_id,
        is_public=room.is_public,
        recording=room.recording,
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at,
        admin_left_at=room.admin_left_at,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


class UpdatePublicRequest(BaseModel):
    """Request to update room public/private setting."""
    is_public: bool


@router.patch("/{room_code}/public", response_model=RoomResponse)
async def update_room_public(
    room_code: str,
    request: UpdatePublicRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Toggle room public/private setting.

    Args:
        room_code: The room code
        request: Public setting update
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        RoomResponse with updated room details

    Raises:
        HTTPException: 404 if room not found, 403 if not owner
    """
    user_id = int(user.get("sub"))

    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify user owns the room
    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can modify public settings")

    # Update public setting
    room.is_public = request.is_public
    db.commit()
    db.refresh(room)

    return RoomResponse(
        id=room.id,
        code=room.code,
        owner_id=room.owner_id,
        is_public=room.is_public,
        recording=room.recording,
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at,
        admin_left_at=room.admin_left_at,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


@router.get("/{room_code}/status", response_model=RoomStatusResponse)
async def get_room_status(
    room_code: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get room status including admin presence and expiration time.

    Args:
        room_code: The room code
        request: FastAPI request object (to access ws_manager)
        db: Database session
        user: Authenticated user

    Returns:
        RoomStatusResponse with admin presence and expiration info
    """
    from datetime import timedelta

    # Get room from database
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check if admin is currently connected via WebSocket
    wsman = getattr(request.app.state, 'wsman', None)
    admin_present = False

    if wsman:
        for ws in wsman.rooms.get(room_code, []):
            user_id = getattr(ws.state, 'user', None)  # Fixed: was 'user_id', should be 'user'
            if user_id and not str(user_id).startswith('guest:'):
                try:
                    # Convert to int for comparison with owner_id
                    if int(user_id) == room.owner_id:
                        admin_present = True
                        break
                except (ValueError, TypeError):
                    # Skip if user_id can't be converted to int
                    continue

    # Calculate expiration time if admin has left
    expires_at = None
    if room.admin_left_at:
        # Always calculate expires_at if admin_left_at is set
        # This ensures clients get the countdown even during the debounce period
        expires_at = room.admin_left_at + timedelta(minutes=30)

    # Refresh user's language TTL in Redis (keeps them active for translation routing)
    wsman = getattr(request.app.state, 'wsman', None)

    if wsman and wsman.redis:
        user_id = user.get("sub")
        user_lang = user.get("preferred_lang", "en")
        key = f"room:{room_code}:active_lang:{user_id}"
        # Refresh TTL to 15 seconds (3x the 5s poll interval)
        await wsman.redis.setex(key, 15, user_lang)

    return RoomStatusResponse(
        code=room.code,
        admin_present=admin_present,
        admin_left_at=room.admin_left_at,
        expires_at=expires_at
    )

# NOTE: Per-room STT settings removed in favor of language-based routing (Migration 006)
# STT provider selection is now based on detected/selected language globally
# See: api/routers/stt/language_router.py for new routing logic


# ===== Multi-Speaker Diarization Endpoints =====

class SpeakerInfo(BaseModel):
    """Information about a speaker in a room."""
    speaker_id: int
    display_name: str
    language: str
    color: str


class SpeakerResponse(BaseModel):
    """Response with speaker details."""
    id: int
    speaker_id: int
    display_name: str
    language: str
    color: str
    created_at: datetime


class SpeakersListResponse(BaseModel):
    """Response with list of speakers."""
    speakers: List[SpeakerResponse]
    discovery_mode: str
    speakers_locked: bool


class UpdateSpeakersRequest(BaseModel):
    """Request to add or update speakers (bulk operation for discovery)."""
    speakers: List[SpeakerInfo]


class UpdateSpeakerRequest(BaseModel):
    """Request to update a single speaker."""
    display_name: Optional[str] = None
    language: Optional[str] = None
    color: Optional[str] = None


class UpdateDiscoveryModeRequest(BaseModel):
    """Request to update room discovery mode."""
    discovery_mode: str  # "disabled", "enabled", "locked"


@router.get("/{room_code}/speakers", response_model=SpeakersListResponse)
async def get_room_speakers(
    room_code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get list of speakers in a room.

    Args:
        room_code: The room code
        db: Database session
        user: Authenticated user

    Returns:
        SpeakersListResponse with list of speakers and discovery settings

    Raises:
        HTTPException: 404 if room not found
    """
    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Get all speakers for this room
    speakers = db.query(RoomSpeaker).filter(
        RoomSpeaker.room_id == room.id
    ).order_by(RoomSpeaker.speaker_id).all()

    speaker_responses = [
        SpeakerResponse(
            id=s.id,
            speaker_id=s.speaker_id,
            display_name=s.display_name,
            language=s.language,
            color=s.color,
            created_at=s.created_at
        )
        for s in speakers
    ]

    return SpeakersListResponse(
        speakers=speaker_responses,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


@router.post("/{room_code}/speakers", response_model=SpeakersListResponse)
async def update_room_speakers(
    room_code: str,
    request: UpdateSpeakersRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Add or update speakers in a room (bulk operation for discovery).

    This endpoint replaces all existing speakers with the provided list.
    Used during speaker discovery phase.

    Args:
        room_code: The room code
        request: List of speakers to set
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        SpeakersListResponse with updated speakers

    Raises:
        HTTPException: 404 if room not found, 403 if not owner or speakers locked
    """
    user_id = int(user.get("sub"))

    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify user owns the room
    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can manage speakers")

    # Check if speakers are locked
    if room.speakers_locked:
        raise HTTPException(status_code=403, detail="Speakers are locked. Cannot modify.")

    # Delete existing speakers
    db.query(RoomSpeaker).filter(RoomSpeaker.room_id == room.id).delete()

    # Add new speakers
    for speaker_info in request.speakers:
        speaker = RoomSpeaker(
            room_id=room.id,
            speaker_id=speaker_info.speaker_id,
            display_name=speaker_info.display_name,
            language=speaker_info.language,
            color=speaker_info.color,
            created_at=datetime.utcnow()
        )
        db.add(speaker)

    db.commit()

    # Get updated speakers
    speakers = db.query(RoomSpeaker).filter(
        RoomSpeaker.room_id == room.id
    ).order_by(RoomSpeaker.speaker_id).all()

    speaker_responses = [
        SpeakerResponse(
            id=s.id,
            speaker_id=s.speaker_id,
            display_name=s.display_name,
            language=s.language,
            color=s.color,
            created_at=s.created_at
        )
        for s in speakers
    ]

    return SpeakersListResponse(
        speakers=speaker_responses,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


@router.patch("/{room_code}/speakers/{speaker_id}", response_model=SpeakerResponse)
async def update_speaker(
    room_code: str,
    speaker_id: int,
    request: UpdateSpeakerRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Update a specific speaker's details.

    Args:
        room_code: The room code
        speaker_id: The speaker ID to update
        request: Speaker update fields
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        SpeakerResponse with updated speaker details

    Raises:
        HTTPException: 404 if room or speaker not found, 403 if not owner or speakers locked
    """
    user_id = int(user.get("sub"))

    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify user owns the room
    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can manage speakers")

    # Check if speakers are locked
    if room.speakers_locked:
        raise HTTPException(status_code=403, detail="Speakers are locked. Cannot modify.")

    # Get speaker
    speaker = db.query(RoomSpeaker).filter(
        RoomSpeaker.room_id == room.id,
        RoomSpeaker.speaker_id == speaker_id
    ).first()

    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    # Update fields
    if request.display_name is not None:
        speaker.display_name = request.display_name
    if request.language is not None:
        speaker.language = request.language
    if request.color is not None:
        speaker.color = request.color

    db.commit()
    db.refresh(speaker)

    return SpeakerResponse(
        id=speaker.id,
        speaker_id=speaker.speaker_id,
        display_name=speaker.display_name,
        language=speaker.language,
        color=speaker.color,
        created_at=speaker.created_at
    )


@router.delete("/{room_code}/speakers/{speaker_id}")
async def delete_speaker(
    room_code: str,
    speaker_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Delete a speaker from a room.

    Args:
        room_code: The room code
        speaker_id: The speaker ID to delete
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        Success message

    Raises:
        HTTPException: 404 if room or speaker not found, 403 if not owner or speakers locked
    """
    user_id = int(user.get("sub"))

    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify user owns the room
    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can manage speakers")

    # Check if speakers are locked
    if room.speakers_locked:
        raise HTTPException(status_code=403, detail="Speakers are locked. Cannot modify.")

    # Get speaker
    speaker = db.query(RoomSpeaker).filter(
        RoomSpeaker.room_id == room.id,
        RoomSpeaker.speaker_id == speaker_id
    ).first()

    if not speaker:
        raise HTTPException(status_code=404, detail="Speaker not found")

    db.delete(speaker)
    db.commit()

    return {"message": "Speaker deleted successfully"}


@router.patch("/{room_code}/discovery-mode", response_model=RoomResponse)
async def update_discovery_mode(
    room_code: str,
    request: UpdateDiscoveryModeRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Update room discovery mode.

    Args:
        room_code: The room code
        request: Discovery mode setting
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        RoomResponse with updated room details

    Raises:
        HTTPException: 404 if room not found, 403 if not owner, 400 if invalid mode
    """
    user_id = int(user.get("sub"))

    # Validate discovery mode
    valid_modes = ["disabled", "enabled", "locked"]
    if request.discovery_mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid discovery mode. Must be one of: {', '.join(valid_modes)}"
        )

    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify user owns the room
    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can modify discovery mode")

    # Update discovery mode
    room.discovery_mode = request.discovery_mode

    # Update speakers_locked flag based on discovery mode
    if request.discovery_mode == "locked":
        room.speakers_locked = True
    elif request.discovery_mode == "enabled":
        # Re-enable discovery: unlock speakers for re-configuration
        room.speakers_locked = False

    db.commit()
    db.refresh(room)

    # Invalidate multi-speaker cache for this room
    # This ensures STT routing picks up the updated speakers_locked state immediately
    try:
        r = redis.from_url(REDIS_URL)
        cache_message = json.dumps({
            "room_code": room_code,
            "type": "multi_speaker",
            "discovery_mode": request.discovery_mode,
            "speakers_locked": room.speakers_locked
        })
        r.publish("routing_cache_clear", cache_message)
        print(f"[RoomsAPI] Cache invalidated for room {room_code} (discovery_mode={request.discovery_mode})")
    except Exception as e:
        print(f"[RoomsAPI] Failed to invalidate cache: {e}")
        # Non-critical error, continue

    return RoomResponse(
        id=room.id,
        code=room.code,
        owner_id=room.owner_id,
        is_public=room.is_public,
        recording=room.recording,
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at,
        admin_left_at=room.admin_left_at,
        discovery_mode=room.discovery_mode,
        speakers_locked=room.speakers_locked
    )


# ===== TTS (Text-to-Speech) Endpoints =====

class TTSEnableRequest(BaseModel):
    """Request to enable/disable TTS for a room."""
    enabled: bool


class TTSVoiceSettings(BaseModel):
    """Room TTS voice settings."""
    voices: dict  # {"en": "en-US-Wavenet-D", "pl": "pl-PL-Wavenet-A", ...}


class TTSSettingsResponse(BaseModel):
    """Response with TTS settings."""
    tts_enabled: bool
    tts_voice_overrides: dict


@router.post("/{room_code}/tts/enable")
async def enable_room_tts(
    room_code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Enable TTS for a room.

    Args:
        room_code: The room code
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        dict: {"enabled": true}

    Raises:
        HTTPException: 404 if room not found, 403 if not owner
    """
    user_id = int(user.get("sub"))

    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can modify TTS settings")

    room.tts_enabled = True
    db.commit()

    return {"enabled": True}


@router.post("/{room_code}/tts/disable")
async def disable_room_tts(
    room_code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Disable TTS for a room.

    Args:
        room_code: The room code
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        dict: {"enabled": false}

    Raises:
        HTTPException: 404 if room not found, 403 if not owner
    """
    user_id = int(user.get("sub"))

    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can modify TTS settings")

    room.tts_enabled = False
    db.commit()

    return {"enabled": False}


@router.get("/{room_code}/tts/settings", response_model=TTSSettingsResponse)
async def get_room_tts_settings(
    room_code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get room TTS settings.

    Args:
        room_code: The room code
        db: Database session
        user: Authenticated user

    Returns:
        TTSSettingsResponse with TTS enabled status and voice overrides

    Raises:
        HTTPException: 404 if room not found
    """
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    return TTSSettingsResponse(
        tts_enabled=room.tts_enabled if hasattr(room, 'tts_enabled') else True,
        tts_voice_overrides=room.tts_voice_overrides if hasattr(room, 'tts_voice_overrides') else {}
    )


@router.put("/{room_code}/tts/settings", response_model=TTSSettingsResponse)
async def update_room_tts_settings(
    room_code: str,
    settings: TTSVoiceSettings,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Update room TTS voice settings.

    Args:
        room_code: The room code
        settings: Voice settings to update
        db: Database session
        user: Authenticated user (must be room owner)

    Returns:
        TTSSettingsResponse with updated settings

    Raises:
        HTTPException: 404 if room not found, 403 if not owner
    """
    user_id = int(user.get("sub"))

    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can modify TTS settings")

    room.tts_voice_overrides = settings.voices
    db.commit()
    db.refresh(room)

    return TTSSettingsResponse(
        tts_enabled=room.tts_enabled if hasattr(room, 'tts_enabled') else True,
        tts_voice_overrides=room.tts_voice_overrides if hasattr(room, 'tts_voice_overrides') else {}
    )
