"""
Guest Session API Endpoints for LiveTranslator.

Handles:
- POST /api/guest/create - Create guest session with device fingerprinting
- GET /api/guest/status - Get session status
- POST /api/guest/activity - Update activity (keep-alive)

Feature ID: 8 - Week 4
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from ..db import SessionLocal
from ..services.guest_session_service import GuestSessionService

logger = logging.getLogger(__name__)
router = APIRouter(tags=["guest-session"])


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

class CreateGuestSessionRequest(BaseModel):
    room_code: str = Field(min_length=1, max_length=16, description="Room code to join")
    device_fingerprint: str = Field(min_length=10, description="Unique device identifier")
    user_name: str = Field(min_length=1, max_length=100, description="Guest display name")
    language_code: str = Field(min_length=2, max_length=10, description="Language code (e.g., 'es', 'fr')")


class CreateGuestSessionResponse(BaseModel):
    session_token: str
    room_id: int
    user_name: str
    language_code: str
    expires_at: str
    created_at: str


class SessionStatusResponse(BaseModel):
    session_token: str
    status: str
    user_name: str
    language_code: str
    created_at: str
    expires_at: str
    last_activity_at: str | None
    total_duration_seconds: int
    time_remaining_seconds: int


class UpdateActivityRequest(BaseModel):
    session_token: str = Field(description="Session token (UUID)")


class UpdateActivityResponse(BaseModel):
    status: str
    last_activity_at: str


# ========================================
# Endpoints
# ========================================

@router.post("/api/guest/create", response_model=CreateGuestSessionResponse)
def create_guest_session(
    request: CreateGuestSessionRequest,
    db: Session = Depends(get_db)
):
    """
    Create guest session with device fingerprinting.

    Requirements:
    - Device fingerprint >= 10 characters
    - 1-hour session TTL
    - Prevents multiple active sessions per device per room

    Returns:
        200: Session created
        404: Room not found
        409: Active session already exists (rejoin with existing token)
        422: Invalid device fingerprint
    """
    service = GuestSessionService(db)

    # Get room ID from code
    from sqlalchemy import text
    room = db.execute(
        text("SELECT id FROM rooms WHERE code = :code"),
        {"code": request.room_code}
    ).fetchone()

    if not room:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Room not found"
        )

    try:
        session = service.create_session(
            device_fingerprint=request.device_fingerprint,
            room_id=room.id,
            user_name=request.user_name,
            language_code=request.language_code
        )

        return CreateGuestSessionResponse(**session)

    except IntegrityError as e:
        # Active session exists
        if hasattr(e, 'params') and isinstance(e.params, dict):
            error_data = e.params
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": error_data.get("error", "active_session_exists"),
                    "existing_session_token": error_data.get("existing_session_token"),
                    "expires_at": error_data.get("expires_at"),
                    "message": error_data.get("message", "Active session exists")
                }
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Active session already exists for this device in this room"
            )

    except ValueError as e:
        error_msg = str(e)

        if "Invalid device fingerprint" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=error_msg
            )
        elif "Room not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

    except Exception as e:
        logger.error(f"Error creating guest session: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create guest session"
        )


@router.get("/api/guest/status", response_model=SessionStatusResponse)
def get_session_status(
    session_token: str = Query(..., description="Session token (UUID)"),
    db: Session = Depends(get_db)
):
    """
    Get guest session status.

    Returns:
        200: Session status
        404: Session not found or expired
    """
    service = GuestSessionService(db)

    try:
        session = service.get_session_status(session_token)

        return SessionStatusResponse(**session)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Error getting session status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get session status"
        )


@router.post("/api/guest/activity", response_model=UpdateActivityResponse)
def update_activity(
    request: UpdateActivityRequest,
    db: Session = Depends(get_db)
):
    """
    Update guest session activity (keep-alive).
    Client sends this every 60 seconds.

    Returns:
        200: Activity updated
        404: Session not found or expired
    """
    service = GuestSessionService(db)

    try:
        result = service.update_activity(request.session_token)

        return UpdateActivityResponse(**result)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Error updating activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update activity"
        )
