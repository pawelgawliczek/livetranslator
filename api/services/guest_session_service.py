"""
Guest Session Service for LiveTranslator.

Manages guest (non-authenticated) user sessions with:
- 1-hour session TTL
- Device fingerprint-based deduplication
- Activity tracking (keep-alive)
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

SESSION_TTL_HOURS = 1


class GuestSessionService:
    def __init__(self, db: Session):
        self.db = db

    def create_session(
        self,
        device_fingerprint: str,
        room_id: int,
        user_name: str,
        language_code: str,
    ) -> dict:
        """
        Create a guest session. Raises IntegrityError if active session
        already exists for this device+room combo.
        """
        if not device_fingerprint or len(device_fingerprint) < 10:
            raise ValueError(
                "Invalid device fingerprint: must be at least 10 characters"
            )

        # Check for existing active session
        existing = self.db.execute(
            text("""
                SELECT session_token, expires_at
                FROM guest_sessions
                WHERE device_fingerprint = :fp
                  AND room_id = :room_id
                  AND expires_at > NOW()
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"fp": device_fingerprint, "room_id": room_id},
        ).fetchone()

        if existing:
            raise IntegrityError(
                "Active session exists",
                params={
                    "error": "active_session_exists",
                    "existing_session_token": str(existing.session_token),
                    "expires_at": existing.expires_at.isoformat(),
                    "message": "Active session already exists for this device in this room",
                },
                orig=None,
            )

        row = self.db.execute(
            text("""
                INSERT INTO guest_sessions
                    (device_fingerprint, room_id, user_name, language_code)
                VALUES (:fp, :room_id, :user_name, :lang)
                RETURNING session_token, room_id, user_name, language_code,
                          expires_at, created_at
            """),
            {
                "fp": device_fingerprint,
                "room_id": room_id,
                "user_name": user_name,
                "lang": language_code,
            },
        ).fetchone()

        self.db.commit()

        return {
            "session_token": str(row.session_token),
            "room_id": row.room_id,
            "user_name": row.user_name,
            "language_code": row.language_code,
            "expires_at": row.expires_at.isoformat(),
            "created_at": row.created_at.isoformat(),
        }

    def get_session_status(self, session_token: str) -> dict:
        """Get current status of a guest session."""
        row = self.db.execute(
            text("""
                SELECT session_token, user_name, language_code,
                       created_at, expires_at, last_activity_at,
                       total_duration_seconds
                FROM guest_sessions
                WHERE session_token = :token::uuid
            """),
            {"token": session_token},
        ).fetchone()

        if not row:
            raise ValueError("Session not found")

        now = datetime.utcnow()
        expired = row.expires_at < now
        remaining = max(0, int((row.expires_at - now).total_seconds()))

        return {
            "session_token": str(row.session_token),
            "status": "expired" if expired else "active",
            "user_name": row.user_name,
            "language_code": row.language_code,
            "created_at": row.created_at.isoformat(),
            "expires_at": row.expires_at.isoformat(),
            "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
            "total_duration_seconds": row.total_duration_seconds,
            "time_remaining_seconds": remaining,
        }

    def update_activity(self, session_token: str) -> dict:
        """Update last activity timestamp (keep-alive)."""
        row = self.db.execute(
            text("""
                UPDATE guest_sessions
                SET last_activity_at = NOW()
                WHERE session_token = :token::uuid
                  AND expires_at > NOW()
                RETURNING last_activity_at
            """),
            {"token": session_token},
        ).fetchone()

        if not row:
            raise ValueError("Session not found or expired")

        self.db.commit()

        return {
            "status": "active",
            "last_activity_at": row.last_activity_at.isoformat(),
        }
