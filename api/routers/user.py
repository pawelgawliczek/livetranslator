"""
User profile and preferences API router.

Handles:
- PATCH /api/user/email-preferences - Update email notification preferences (US-012)
- GET /api/user/email-preferences - Get email notification preferences
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ..auth import get_current_user
from ..db import SessionLocal
from ..models import User
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/user", tags=["user"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class EmailPreferencesRequest(BaseModel):
    email_notifications_enabled: bool


@router.patch("/email-preferences")
def update_email_preferences(
    request: EmailPreferencesRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update user email notification preferences.

    Allows users to opt-out of email notifications (GDPR compliance).
    """
    current_user.email_notifications_enabled = request.email_notifications_enabled
    db.commit()

    logger.info(
        "email_preferences_updated",
        extra={
            "user_id": current_user.id,
            "enabled": request.email_notifications_enabled
        }
    )

    return {
        "success": True,
        "email_notifications_enabled": current_user.email_notifications_enabled
    }


@router.get("/email-preferences")
def get_email_preferences(
    current_user: User = Depends(get_current_user)
):
    """Get current email notification preferences."""
    return {
        "email_notifications_enabled": current_user.email_notifications_enabled
    }
