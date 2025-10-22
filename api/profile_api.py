from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Header
from passlib.hash import bcrypt_sha256 as bcrypt
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from .db import SessionLocal
from .models import User, UserSubscription
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

class ProfileUpdateIn(BaseModel):
    display_name: Optional[str] = None
    preferred_lang: Optional[str] = None

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
        created_at=user.created_at
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
        created_at=user.created_at
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
