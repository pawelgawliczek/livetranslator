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

from .db import SessionLocal
from .models import Room
from .jwt_tools import verify_token

router = APIRouter(tags=["rooms"])


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
    requires_login: bool
    max_participants: int
    created_at: datetime


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
    source_lang: str
    target_lang: str
    is_speaking: bool


class ParticipantsResponse(BaseModel):
    """Response with list of participants."""
    participants: List[ParticipantInfo]


@router.post("/rooms", response_model=RoomResponse)
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
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at
    )


@router.get("/rooms/{room_code}", response_model=RoomResponse)
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
        requires_login=room.requires_login,
        max_participants=room.max_participants,
        created_at=room.created_at
    )


@router.get("/api/rooms/{room_code}/participants", response_model=ParticipantsResponse)
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

    participants = []

    # Get all WebSocket connections for this room
    room_connections = wsman.rooms.get(room_code, set())

    for ws in room_connections:
        # Extract user info from WebSocket state
        user_email = getattr(ws.state, 'email', 'Unknown')
        user_id = getattr(ws.state, 'user', None)

        # Determine if guest by checking user_id format
        is_guest = user_id and str(user_id).startswith('guest:')

        # Extract display name
        if is_guest:
            # For guests, user_id format is "guest:{name}:{timestamp}"
            parts = str(user_id).split(':', 2)
            display_name = parts[1] if len(parts) > 1 else 'Guest'
        else:
            display_name = user_email.split('@')[0] if '@' in user_email else user_email

        participants.append(ParticipantInfo(
            display_name=display_name,
            email=user_email,
            is_guest=is_guest,
            source_lang="auto",  # TODO: Store language preferences in WebSocket state
            target_lang="en",    # TODO: Store language preferences in WebSocket state
            is_speaking=False    # TODO: Track speaking status
        ))

    return ParticipantsResponse(participants=participants)
