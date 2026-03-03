from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from passlib.hash import bcrypt_sha256 as bcrypt
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from .db import SessionLocal
from .models import User
from .auth_deps import get_current_user

router = APIRouter(prefix="/api/profile", tags=["profile"])

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

class ProfileOut(BaseModel):
    id: int
    email: str
    display_name: str
    preferred_lang: str
    google_id: Optional[str]
    has_password: bool
    is_admin: bool
    created_at: datetime
    audio_threshold: Optional[float] = 0.02
    preferred_mic_device_id: Optional[str] = None

class ProfileUpdateIn(BaseModel):
    display_name: Optional[str] = None
    preferred_lang: Optional[str] = None
    audio_threshold: Optional[float] = None
    preferred_mic_device_id: Optional[str] = None

class PasswordChangeIn(BaseModel):
    current_password: Optional[str] = None
    new_password: str

@router.get("", response_model=ProfileOut)
def get_profile(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user's profile"""
    user_email = user.get("email")
    user = db.scalar(select(User).where(User.email == user_email))
    if not user:
        raise HTTPException(404, "User not found")

    return ProfileOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_lang=user.preferred_lang,
        google_id=user.google_id,
        has_password=user.password_hash is not None,
        is_admin=user.is_admin,
        created_at=user.created_at,
        audio_threshold=user.audio_threshold,
        preferred_mic_device_id=user.preferred_mic_device_id
    )

@router.patch("", response_model=ProfileOut)
def update_profile(
    update: ProfileUpdateIn,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user profile"""
    user_email = user.get("email")
    user = db.scalar(select(User).where(User.email == user_email))
    if not user:
        raise HTTPException(404, "User not found")

    if update.display_name is not None:
        user.display_name = update.display_name

    if update.preferred_lang is not None:
        user.preferred_lang = update.preferred_lang

    if update.audio_threshold is not None:
        user.audio_threshold = update.audio_threshold

    # Allow explicitly setting to None to clear device selection
    if "preferred_mic_device_id" in update.model_fields_set:
        user.preferred_mic_device_id = update.preferred_mic_device_id

    db.commit()
    db.refresh(user)

    return ProfileOut(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        preferred_lang=user.preferred_lang,
        google_id=user.google_id,
        has_password=user.password_hash is not None,
        is_admin=user.is_admin,
        created_at=user.created_at,
        audio_threshold=user.audio_threshold,
        preferred_mic_device_id=user.preferred_mic_device_id
    )

@router.post("/password")
def change_password(
    password_change: PasswordChangeIn,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    user_email = user.get("email")
    user = db.scalar(select(User).where(User.email == user_email))
    if not user:
        raise HTTPException(404, "User not found")

    # If user has a password, verify current password
    if user.password_hash:
        if not password_change.current_password:
            raise HTTPException(400, "Current password required")
        if not bcrypt.verify(password_change.current_password, user.password_hash):
            raise HTTPException(401, "Invalid current password")

    # Set new password
    user.password_hash = bcrypt.hash(password_change.new_password)
    db.commit()

    return {"message": "Password changed successfully"}

@router.delete("")
def delete_account(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Delete user account (soft delete - just marks as deleted)"""
    user_email = user.get("email")
    user = db.scalar(select(User).where(User.email == user_email))
    if not user:
        raise HTTPException(404, "User not found")

    # For now, we'll just delete the user
    # In production, you might want to implement soft delete or anonymization
    db.delete(user)
    db.commit()

    return {"message": "Account deleted successfully"}


# ===== TTS Settings Endpoints =====

class TTSSettingsOut(BaseModel):
    tts_enabled: bool
    tts_voice_preferences: dict
    tts_volume: float
    tts_rate: float
    tts_pitch: float


class TTSSettingsUpdateIn(BaseModel):
    tts_enabled: Optional[bool] = None
    tts_voice_preferences: Optional[dict] = None
    tts_volume: Optional[float] = None
    tts_rate: Optional[float] = None
    tts_pitch: Optional[float] = None


@router.get("/tts", response_model=TTSSettingsOut)
def get_user_tts_settings(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user TTS settings"""
    user_email = user.get("email")
    user = db.scalar(select(User).where(User.email == user_email))
    if not user:
        raise HTTPException(404, "User not found")

    return TTSSettingsOut(
        tts_enabled=user.tts_enabled if hasattr(user, 'tts_enabled') else True,
        tts_voice_preferences=user.tts_voice_preferences if hasattr(user, 'tts_voice_preferences') else {},
        tts_volume=user.tts_volume if hasattr(user, 'tts_volume') else 1.0,
        tts_rate=user.tts_rate if hasattr(user, 'tts_rate') else 1.0,
        tts_pitch=user.tts_pitch if hasattr(user, 'tts_pitch') else 0.0
    )


@router.put("/tts", response_model=TTSSettingsOut)
def update_user_tts_settings(
    update: TTSSettingsUpdateIn,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user TTS settings"""
    user_email = user.get("email")
    user = db.scalar(select(User).where(User.email == user_email))
    if not user:
        raise HTTPException(404, "User not found")

    if update.tts_enabled is not None:
        user.tts_enabled = update.tts_enabled

    if update.tts_voice_preferences is not None:
        user.tts_voice_preferences = update.tts_voice_preferences

    if update.tts_volume is not None:
        # Validate range
        if not 0.0 <= update.tts_volume <= 2.0:
            raise HTTPException(400, "TTS volume must be between 0.0 and 2.0")
        user.tts_volume = update.tts_volume

    if update.tts_rate is not None:
        # Validate range
        if not 0.25 <= update.tts_rate <= 4.0:
            raise HTTPException(400, "TTS rate must be between 0.25 and 4.0")
        user.tts_rate = update.tts_rate

    if update.tts_pitch is not None:
        # Validate range
        if not -20.0 <= update.tts_pitch <= 20.0:
            raise HTTPException(400, "TTS pitch must be between -20.0 and 20.0")
        user.tts_pitch = update.tts_pitch

    db.commit()
    db.refresh(user)

    return TTSSettingsOut(
        tts_enabled=user.tts_enabled if hasattr(user, 'tts_enabled') else True,
        tts_voice_preferences=user.tts_voice_preferences if hasattr(user, 'tts_voice_preferences') else {},
        tts_volume=user.tts_volume if hasattr(user, 'tts_volume') else 1.0,
        tts_rate=user.tts_rate if hasattr(user, 'tts_rate') else 1.0,
        tts_pitch=user.tts_pitch if hasattr(user, 'tts_pitch') else 0.0
    )
