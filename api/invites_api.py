"""
API endpoints for room invitations.

Handles:
- Generating invite codes (time-limited JWT tokens)
- Generating QR codes for room invites
- Validating invite codes
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from .db import SessionLocal
from .models import Room
from .jwt_tools import verify_token
from .utils.invite_code import generate_invite_code, verify_invite_code, get_room_code_from_invite
from .utils.qr_code import generate_qr_code
from .settings import settings


router = APIRouter(prefix="/api/invites", tags=["invites"])


class InviteResponse(BaseModel):
    """Response when generating an invite."""
    invite_code: str
    invite_url: str
    qr_code: str  # Base64-encoded PNG
    expires_in_minutes: int
    room_code: str


class ValidateInviteResponse(BaseModel):
    """Response when validating an invite."""
    valid: bool
    room_code: Optional[str] = None
    room_id: Optional[int] = None
    is_public: Optional[bool] = None
    requires_login: Optional[bool] = None
    max_participants: Optional[int] = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user_email(token: str) -> str:
    """Extract user email from JWT token."""
    try:
        claims = verify_token(token)
        return claims.get("email", "unknown")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authentication token")


@router.post("/generate/{room_code}", response_model=InviteResponse)
async def generate_room_invite(
    room_code: str,
    db: Session = Depends(get_db)
):
    """
    Generate a time-limited invite code and QR code for a room.

    The invite code is valid for 30 minutes.
    No authentication required - anyone can generate an invite for a room.

    Args:
        room_code: The room code to generate invite for

    Returns:
        InviteResponse with invite_code, invite_url, and qr_code
    """
    # Verify room exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")

    # Generate invite code (JWT with room_code + expiration)
    invite_code = generate_invite_code(room_code)

    # Build invite URL
    domain = settings.LT_DOMAIN
    invite_url = f"https://{domain}/join/{invite_code}"

    # Generate QR code
    qr_code_data = generate_qr_code(invite_url)

    return InviteResponse(
        invite_code=invite_code,
        invite_url=invite_url,
        qr_code=qr_code_data,
        expires_in_minutes=30,
        room_code=room_code
    )


@router.get("/validate/{invite_code}", response_model=ValidateInviteResponse)
async def validate_invite(
    invite_code: str,
    db: Session = Depends(get_db)
):
    """
    Validate an invite code and return room information.

    Args:
        invite_code: The JWT invite token to validate

    Returns:
        ValidateInviteResponse with room info if valid
    """
    # Verify and decode invite code
    payload = verify_invite_code(invite_code)

    if not payload:
        return ValidateInviteResponse(valid=False)

    room_code = payload.get("room_code")
    if not room_code:
        return ValidateInviteResponse(valid=False)

    # Verify room still exists
    room = db.query(Room).filter(Room.code == room_code).first()
    if not room:
        return ValidateInviteResponse(valid=False)

    return ValidateInviteResponse(
        valid=True,
        room_code=room.code,
        room_id=room.id,
        is_public=room.is_public,
        requires_login=room.requires_login,
        max_participants=room.max_participants
    )


@router.get("/room/{invite_code}/code")
async def get_room_code(invite_code: str):
    """
    Extract room code from invite code (convenience endpoint).

    Args:
        invite_code: The JWT invite token

    Returns:
        {"room_code": "room-123"} if valid, 400 if invalid
    """
    room_code = get_room_code_from_invite(invite_code)

    if not room_code:
        raise HTTPException(status_code=400, detail="Invalid or expired invite code")

    return {"room_code": room_code}
