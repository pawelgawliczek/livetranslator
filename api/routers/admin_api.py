"""Admin API endpoints - Phase 0.2"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import redis
import json
import os
from ..auth import require_admin, get_db
from ..models import User, SystemSettings

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Redis for cache invalidation
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
CACHE_CLEAR_CHANNEL = "stt_cache_clear"

class STTSettingsUpdate(BaseModel):
    stt_partial_provider_default: Optional[str] = None
    stt_final_provider_default: Optional[str] = None

class ProviderInfo(BaseModel):
    id: str
    name: str
    type: str  # "stt_partial", "stt_final", "mt"
    description: str

@router.get("/test")
def test_admin_access(admin: User = Depends(require_admin)):
    """Test endpoint to verify admin access works"""
    return {
        "message": "Admin access verified",
        "admin_email": admin.email,
        "admin_id": admin.id
    }

@router.get("/settings/stt")
def get_stt_settings(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Get current STT configuration"""
    settings = db.scalars(select(SystemSettings)).all()
    return {
        "settings": [
            {"key": s.key, "value": s.value, "updated_at": s.updated_at.isoformat()}
            for s in settings
        ]
    }

@router.post("/settings/stt")
def update_stt_settings(
    update: STTSettingsUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update STT default settings"""
    updated_settings = []

    if update.stt_partial_provider_default is not None:
        setting = db.scalar(
            select(SystemSettings).where(SystemSettings.key == "stt_partial_provider_default")
        )
        if setting:
            setting.value = update.stt_partial_provider_default
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSettings(
                key="stt_partial_provider_default",
                value=update.stt_partial_provider_default
            )
            db.add(setting)
        updated_settings.append(setting.key)

    if update.stt_final_provider_default is not None:
        setting = db.scalar(
            select(SystemSettings).where(SystemSettings.key == "stt_final_provider_default")
        )
        if setting:
            setting.value = update.stt_final_provider_default
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSettings(
                key="stt_final_provider_default",
                value=update.stt_final_provider_default
            )
            db.add(setting)
        updated_settings.append(setting.key)

    db.commit()

    # Invalidate cache in STT router (clear all caches for global settings)
    try:
        r = redis.from_url(REDIS_URL)
        r.publish(CACHE_CLEAR_CHANNEL, json.dumps({}))  # Empty dict = clear all
        print(f"[Admin API] Published cache clear for global settings")
    except Exception as e:
        print(f"[Admin API] Failed to publish cache clear: {e}")

    return {
        "message": "STT settings updated successfully",
        "updated": updated_settings
    }

@router.get("/providers")
def get_available_providers(admin: User = Depends(require_admin)):
    """List all available STT and MT providers"""
    return {
        "stt_partial": [
            {
                "id": "openai_chunked",
                "name": "OpenAI Whisper (Chunked)",
                "type": "stt_partial",
                "description": "OpenAI's Whisper API with chunked audio processing"
            },
            {
                "id": "deepgram",
                "name": "Deepgram",
                "type": "stt_partial",
                "description": "Deepgram streaming STT with real-time speaker diarization"
            },
            {
                "id": "local",
                "name": "Local Whisper",
                "type": "stt_partial",
                "description": "Local Whisper model (offline, slower)"
            }
        ],
        "stt_final": [
            {
                "id": "openai",
                "name": "OpenAI Whisper",
                "type": "stt_final",
                "description": "OpenAI's Whisper API for final transcription"
            },
            {
                "id": "elevenlabs",
                "name": "ElevenLabs",
                "type": "stt_final",
                "description": "ElevenLabs batch transcription with speaker diarization and audio events"
            },
            {
                "id": "local",
                "name": "Local Whisper",
                "type": "stt_final",
                "description": "Local Whisper model for final transcription (offline, no API costs)"
            },
            {
                "id": "none",
                "name": "None",
                "type": "stt_final",
                "description": "Skip final transcription (use partial only)"
            }
        ],
        "mt": [
            {
                "id": "openai",
                "name": "OpenAI GPT-4o-mini",
                "type": "mt",
                "description": "OpenAI's GPT-4o-mini for translation"
            }
        ]
    }
