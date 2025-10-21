"""
API endpoints for guest access.

Handles:
- Creating temporary guest tokens for anonymous room access
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import jwt
from datetime import datetime, timedelta

from .settings import JWT_SECRET

router = APIRouter(prefix="/api/guest", tags=["guest"])


class GuestTokenRequest(BaseModel):
    """Request to create a guest token."""
    display_name: str
    room_code: str
    invite_code: str
    language: str = "en"


class GuestTokenResponse(BaseModel):
    """Response with guest token."""
    token: str
    expires_in: int  # seconds


@router.post("/token", response_model=GuestTokenResponse)
async def create_guest_token(request: GuestTokenRequest):
    """
    Create a temporary guest token for anonymous room access.

    The token is valid for 24 hours and allows the guest to join the specified room.

    Args:
        request: Guest token request with display name, room code, and invite code

    Returns:
        GuestTokenResponse with JWT token
    """
    # Validate invite code format (basic check)
    if not request.invite_code or len(request.invite_code) < 10:
        raise HTTPException(status_code=400, detail="Invalid invite code")

    # Create JWT for guest
    # Use a special subject format for guests: guest:{display_name}:{timestamp}
    now = datetime.utcnow()
    exp = now + timedelta(hours=24)

    payload = {
        "sub": f"guest:{request.display_name}:{int(now.timestamp())}",
        "email": f"{request.display_name} (Guest)",
        "display_name": request.display_name,
        "room_code": request.room_code,
        "preferred_lang": request.language,
        "is_guest": True,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp())
    }

    secret = JWT_SECRET
    if isinstance(secret, bytes):
        secret = secret.decode('utf-8')

    token = jwt.encode(payload, secret, algorithm="HS256")

    return GuestTokenResponse(
        token=token,
        expires_in=24 * 60 * 60  # 24 hours in seconds
    )
