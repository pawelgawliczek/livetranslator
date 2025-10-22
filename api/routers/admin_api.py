"""Admin API endpoints - Phase 0.2 + Language Configuration Management"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
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

# NOTE: Deprecated - replaced by language-based routing (Migration 006)
# class STTSettingsUpdate(BaseModel):
#     stt_partial_provider_default: Optional[str] = None
#     stt_final_provider_default: Optional[str] = None

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

# NOTE: Deprecated - replaced by language-based routing (Migration 006)
# Use /api/admin/routing/stt endpoints instead
# @router.post("/settings/stt")
# def update_stt_settings(...):

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
                "name": "Skip Final (Partial Only)",
                "type": "stt_final",
                "description": "Skip final transcription - use only real-time partials for fastest speed"
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

# ============================================================================
# Language Configuration Management (Migration 007)
# ============================================================================

class LanguageConfigResponse(BaseModel):
    language: str
    language_name: str
    stt_standard: Dict[str, Any]
    stt_budget: Dict[str, Any]
    mt_pairs: int
    status: str

class ProviderHealthResponse(BaseModel):
    provider: str
    service_type: str
    status: str
    consecutive_failures: int
    last_check: Optional[datetime]
    last_success: Optional[datetime]
    response_time_ms: Optional[int]

@router.get("/languages")
def get_language_configurations(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all configured languages with their provider settings"""

    # Query all STT configurations
    stt_query = text("""
        SELECT
            language,
            mode,
            quality_tier,
            provider_primary,
            provider_fallback,
            config,
            enabled
        FROM stt_routing_config
        WHERE language != '*'
        ORDER BY language, mode, quality_tier
    """)

    stt_results = db.execute(stt_query).fetchall()

    # Query MT configuration counts per language
    mt_query = text("""
        SELECT
            src_lang,
            COUNT(*) as pair_count
        FROM mt_routing_config
        WHERE src_lang != '*'
        GROUP BY src_lang
    """)

    mt_results = db.execute(mt_query).fetchall()
    mt_counts = {row[0]: row[1] for row in mt_results}

    # Organize by language
    languages = {}
    language_names = {
        "pl-PL": "Polish",
        "en-US": "English (US)",
        "en-GB": "English (GB)",
        "ar-EG": "Arabic (Egyptian)",
        "es-ES": "Spanish",
        "fr-FR": "French",
        "de-DE": "German",
        "it-IT": "Italian",
        "pt-PT": "Portuguese (EU)",
        "pt-BR": "Portuguese (BR)",
        "ru-RU": "Russian"
    }

    for row in stt_results:
        lang = row[0]
        if lang not in languages:
            # Extract simple language code for MT lookup
            simple_lang = lang.split('-')[0]
            languages[lang] = {
                "language": lang,
                "language_name": language_names.get(lang, lang),
                "stt_standard": {},
                "stt_budget": {},
                "mt_pairs": mt_counts.get(simple_lang, 0),
                "status": "active" if row[6] else "disabled"
            }

        mode = row[1]
        tier = row[2]
        config_data = {
            "provider_primary": row[3],
            "provider_fallback": row[4],
            "config": row[5],
            "enabled": row[6]
        }

        if tier == "standard":
            languages[lang]["stt_standard"][mode] = config_data
        else:
            languages[lang]["stt_budget"][mode] = config_data

    return {
        "languages": list(languages.values()),
        "total_languages": len(languages),
        "total_mt_pairs": sum(mt_counts.values())
    }

@router.get("/providers/health")
def get_provider_health(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get health status of all providers"""

    query = text("""
        SELECT
            provider,
            service_type,
            status,
            consecutive_failures,
            last_check,
            last_success,
            response_time_ms
        FROM provider_health
        ORDER BY service_type, provider
    """)

    results = db.execute(query).fetchall()

    providers = []
    for row in results:
        providers.append({
            "provider": row[0],
            "service_type": row[1],
            "status": row[2],
            "consecutive_failures": row[3],
            "last_check": row[4].isoformat() if row[4] else None,
            "last_success": row[5].isoformat() if row[5] else None,
            "response_time_ms": row[6]
        })

    return {
        "providers": providers,
        "total_providers": len(providers),
        "healthy": len([p for p in providers if p["status"] == "healthy"]),
        "degraded": len([p for p in providers if p["status"] == "degraded"]),
        "down": len([p for p in providers if p["status"] == "down"])
    }

@router.get("/languages/{language}/config")
def get_language_config_detail(
    language: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get detailed configuration for a specific language"""

    # Get STT configs
    stt_query = text("""
        SELECT
            mode,
            quality_tier,
            provider_primary,
            provider_fallback,
            config,
            enabled,
            updated_at
        FROM stt_routing_config
        WHERE language = :language
        ORDER BY mode, quality_tier
    """)

    stt_results = db.execute(stt_query, {"language": language}).fetchall()

    if not stt_results:
        raise HTTPException(status_code=404, detail=f"Language {language} not configured")

    # Get MT configs
    simple_lang = language.split('-')[0]
    mt_query = text("""
        SELECT
            src_lang,
            tgt_lang,
            quality_tier,
            provider_primary,
            provider_fallback,
            config,
            enabled
        FROM mt_routing_config
        WHERE src_lang = :src_lang OR tgt_lang = :tgt_lang
        ORDER BY tgt_lang, quality_tier
    """)

    mt_results = db.execute(mt_query, {
        "src_lang": simple_lang,
        "tgt_lang": simple_lang
    }).fetchall()

    return {
        "language": language,
        "stt_configs": [
            {
                "mode": row[0],
                "quality_tier": row[1],
                "provider_primary": row[2],
                "provider_fallback": row[3],
                "config": row[4],
                "enabled": row[5],
                "updated_at": row[6].isoformat() if row[6] else None
            }
            for row in stt_results
        ],
        "mt_configs": [
            {
                "src_lang": row[0],
                "tgt_lang": row[1],
                "quality_tier": row[2],
                "provider_primary": row[3],
                "provider_fallback": row[4],
                "config": row[5],
                "enabled": row[6]
            }
            for row in mt_results
        ]
    }

@router.post("/providers/{provider}/health/reset")
def reset_provider_health(
    provider: str,
    service_type: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Reset health status for a provider (mark as healthy)"""

    update_query = text("""
        UPDATE provider_health
        SET status = 'healthy',
            consecutive_failures = 0,
            last_check = NOW(),
            updated_at = NOW()
        WHERE provider = :provider AND service_type = :service_type
        RETURNING provider, status
    """)

    result = db.execute(update_query, {
        "provider": provider,
        "service_type": service_type
    }).fetchone()

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Provider {provider} ({service_type}) not found"
        )

    db.commit()

    # Clear language router cache
    try:
        from .stt.language_router import clear_cache
        clear_cache()
    except Exception as e:
        print(f"[Admin API] Failed to clear cache: {e}")

    return {
        "message": f"Provider {provider} ({service_type}) health reset to healthy",
        "provider": result[0],
        "status": result[1]
    }

@router.get("/stats")
def get_system_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get system-wide statistics"""

    stats_query = text("""
        SELECT
            (SELECT COUNT(*) FROM stt_routing_config WHERE language != '*') as stt_configs,
            (SELECT COUNT(DISTINCT language) FROM stt_routing_config WHERE language != '*') as languages_configured,
            (SELECT COUNT(*) FROM mt_routing_config) as mt_configs,
            (SELECT COUNT(*) FROM provider_health WHERE status = 'healthy') as healthy_providers,
            (SELECT COUNT(*) FROM provider_health) as total_providers
    """)

    result = db.execute(stats_query).fetchone()

    return {
        "stt_configs": result[0],
        "languages_configured": result[1],
        "mt_configs": result[2],
        "healthy_providers": result[3],
        "total_providers": result[4],
        "system_status": "operational" if result[3] == result[4] else "degraded"
    }
