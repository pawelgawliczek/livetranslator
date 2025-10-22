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
from datetime import datetime
import redis
import json
import os

from .db import SessionLocal
from .models import Room
from .jwt_tools import verify_token

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
    is_public: bool
    recording: bool
    requires_login: bool
    max_participants: int
    created_at: datetime
    admin_left_at: datetime | None = None


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

    # Check if room code already exists
    existing = db.query(Room).filter(Room.code == request.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Room code already exists")

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
        admin_left_at=room.admin_left_at
    )


@router.get("/{room_code}", response_model=RoomResponse)
async def get_room(
    room_code: str,
    db: Session = Depends(get_db)
):
    """
    Get room details by room code.

    Args:
        room_code: The room code to look up
        db: Database session

    Returns:
        RoomResponse with room details

    Raises:
        HTTPException: 404 if room not found
    """
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    return RoomResponse(
        id=room.id,
        code=room.code,
        owner_id=room.owner_id,
        is_public=room.is_public,
        recording=room.recording,
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at,
        admin_left_at=room.admin_left_at
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
            is_speaking=False    # TODO: Track speaking status
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

    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Verify user owns the room
    if room.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only room owner can modify recording settings")

    # Update recording setting
    room.recording = request.recording
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
        admin_left_at=room.admin_left_at
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
        admin_left_at=room.admin_left_at
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

    return RoomStatusResponse(
        code=room.code,
        admin_present=admin_present,
        admin_left_at=room.admin_left_at,
        expires_at=expires_at
    )


class STTSettingsResponse(BaseModel):
    """Response with room STT settings."""
    stt_partial_provider: str | None
    stt_final_provider: str | None
    is_using_defaults: bool


class UpdateSTTSettingsRequest(BaseModel):
    """Request to update room STT settings."""
    stt_partial_provider: Optional[str] = None
    stt_final_provider: Optional[str] = None


@router.get("/{room_code}/stt-settings", response_model=STTSettingsResponse)
async def get_room_stt_settings(
    room_code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Get STT provider settings for a specific room.

    Args:
        room_code: The room code
        db: Database session
        user: Authenticated user

    Returns:
        STTSettingsResponse with current STT provider settings

    Raises:
        HTTPException: 404 if room not found
    """
    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Check if using defaults (both NULL)
    is_using_defaults = room.stt_partial_provider is None and room.stt_final_provider is None

    return STTSettingsResponse(
        stt_partial_provider=room.stt_partial_provider,
        stt_final_provider=room.stt_final_provider,
        is_using_defaults=is_using_defaults
    )


@router.patch("/{room_code}/stt-settings", response_model=STTSettingsResponse)
async def update_room_stt_settings(
    room_code: str,
    request: UpdateSTTSettingsRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user)
):
    """
    Update STT provider settings for a specific room.
    Only room owner or admin can update settings.

    Args:
        room_code: The room code
        request: STT settings update
        db: Database session
        user: Authenticated user (must be room owner or admin)

    Returns:
        STTSettingsResponse with updated STT provider settings

    Raises:
        HTTPException: 404 if room not found, 403 if not authorized
    """
    from sqlalchemy import select
    from .models import User

    user_id = int(user.get("sub"))

    # Get room
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Get user to check if admin
    db_user = db.scalar(select(User).where(User.id == user_id))
    if not db_user:
        raise HTTPException(status_code=401, detail="User not found")

    # Verify user is room owner or admin
    if room.owner_id != user_id and not db_user.is_admin:
        raise HTTPException(status_code=403, detail="Only room owner or admin can modify STT settings")

    # Update STT settings
    # Check if field was provided in request (even if None)
    request_dict = request.model_dump(exclude_unset=True)

    if "stt_partial_provider" in request_dict:
        # Empty string or None means use default
        room.stt_partial_provider = request.stt_partial_provider if request.stt_partial_provider else None

    if "stt_final_provider" in request_dict:
        # Empty string or None means use default
        room.stt_final_provider = request.stt_final_provider if request.stt_final_provider else None

    db.commit()
    db.refresh(room)

    # Invalidate cache in STT router for this specific room
    try:
        r = redis.from_url(REDIS_URL)
        r.publish(CACHE_CLEAR_CHANNEL, json.dumps({"room_code": room_code}))
        print(f"[Rooms API] Published cache clear for room: {room_code}")
    except Exception as e:
        print(f"[Rooms API] Failed to publish cache clear: {e}")

    # Check if using defaults
    is_using_defaults = room.stt_partial_provider is None and room.stt_final_provider is None

    return STTSettingsResponse(
        stt_partial_provider=room.stt_partial_provider,
        stt_final_provider=room.stt_final_provider,
        is_using_defaults=is_using_defaults
    )
