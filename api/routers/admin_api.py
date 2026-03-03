"""Admin API endpoints - Phase 0.2 + Language Configuration Management + Phase 3 Admin Panel APIs"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, text
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from decimal import Decimal
import redis.asyncio as redis
import json
import os
from ..auth import require_admin, get_db
from ..models import User, SystemSettings
from ..services.debug_tracker import get_debug_info, calculate_stt_cost, calculate_mt_cost

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

# ============================================================================
# Message Debug Info (Admin Debug Feature - Phase 3)
# ============================================================================

@router.get("/message-debug/{room_code}/{segment_id}")
def get_message_debug_info(
    room_code: str,
    segment_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get complete debug information for a message by room_code and segment_id.

    Returns debug data from Redis (if available, <24h old) or reconstructs
    from database (for older messages or if Redis expired).

    Only accessible by admin users.
    """

    # Try Redis first (fast path for recent messages)
    import redis as redis_sync
    r = redis_sync.from_url(REDIS_URL, decode_responses=True)
    try:
        # Use sync Redis for consistency with other endpoints
        debug_key = f"debug:{room_code}:{segment_id}"
        cached = r.get(debug_key)

        if cached:
            import orjson
            return {
                "source": "redis",
                "room_code": room_code,
                "segment_id": segment_id,
                "data": orjson.loads(cached)
            }
    finally:
        r.close()

    # Fallback to database reconstruction (for expired or old messages)
    # Query segment info - need to join with rooms to get room by code
    segment_query = text("""
        SELECT
            s.id,
            s.room_id,
            s.text,
            s.lang as source_lang,
            s.speaker_id as speaker,
            s.ts_iso as created_at,
            r.code as room_code
        FROM segments s
        JOIN rooms r ON s.room_id = r.id
        WHERE r.code = :room_code
          AND s.segment_id = :segment_id
    """)

    segment = db.execute(segment_query, {"room_code": room_code, "segment_id": str(segment_id)}).fetchone()

    if not segment:
        raise HTTPException(
            status_code=404,
            detail=f"Segment {segment_id} not found in room {room_code}"
        )

    # Query STT costs
    stt_query = text("""
        SELECT
            provider,
            units,
            unit_type,
            amount_usd,
            ts
        FROM room_costs
        WHERE segment_id = :segment_id
          AND pipeline = 'stt'
        ORDER BY ts DESC
        LIMIT 1
    """)

    stt_result = db.execute(stt_query, {"segment_id": segment_id}).fetchone()

    # Query MT costs
    mt_query = text("""
        SELECT
            provider,
            units,
            unit_type,
            amount_usd,
            ts
        FROM room_costs
        WHERE segment_id = :segment_id
          AND pipeline = 'mt'
        ORDER BY ts ASC
    """)

    mt_results = db.execute(mt_query, {"segment_id": segment_id}).fetchall()

    # Query translations
    translations_query = text("""
        SELECT
            target_lang,
            text
        FROM translations
        WHERE segment_id = :segment_id
        ORDER BY created_at ASC
    """)

    translations = db.execute(translations_query, {"segment_id": segment_id}).fetchall()

    # Reconstruct debug info from database
    debug_data = {
        "segment_id": segment_id,
        "room_code": segment[6],  # room_code from JOIN
        "timestamp": segment[5] if segment[5] else None,
        "stt": None,
        "mt": [],
        "totals": {
            "stt_cost_usd": 0.0,
            "mt_cost_usd": 0.0,
            "total_cost_usd": 0.0,
            "mt_translations": 0
        }
    }

    # Build STT section
    if stt_result:
        debug_data["stt"] = {
            "provider": stt_result[0],
            "language": segment[3] or "auto",
            "mode": "database_reconstructed",
            "latency_ms": None,  # Not available from database
            "audio_duration_sec": float(stt_result[1]) if stt_result[1] else 0.0,
            "cost_usd": float(stt_result[3]),
            "cost_breakdown": {
                "unit_type": stt_result[2],
                "units": float(stt_result[1]) if stt_result[1] else 0.0,
                "rate_per_unit": float(stt_result[3]) / float(stt_result[1]) if stt_result[1] and float(stt_result[1]) > 0 else 0.0
            },
            "routing_reason": "Reconstructed from database",
            "fallback_triggered": None,  # Not available
            "text": segment[2]
        }
        debug_data["totals"]["stt_cost_usd"] = float(stt_result[3])

    # Build MT section
    translations_map = {row[0]: row[1] for row in translations}

    for mt_row in mt_results:
        provider = mt_row[0]
        units = float(mt_row[1]) if mt_row[1] else 0.0
        unit_type = mt_row[2]
        cost_usd = float(mt_row[3])

        # Try to determine target language from translations
        # This is approximate since we don't store language pairs in room_costs
        tgt_lang = "unknown"
        translated_text = None

        # Match by cost amount (rough heuristic)
        for lang, trans_text in translations_map.items():
            if lang not in [segment[3], "auto"]:  # Not source language
                tgt_lang = lang
                translated_text = trans_text
                break

        mt_entry = {
            "src_lang": segment[3] or "auto",
            "tgt_lang": tgt_lang,
            "provider": provider,
            "latency_ms": None,  # Not available from database
            "cost_usd": cost_usd,
            "cost_breakdown": {
                "unit_type": unit_type,
                "units": units,
                "rate_per_unit": cost_usd / units if units > 0 else 0.0
            },
            "routing_reason": "Reconstructed from database",
            "fallback_triggered": None,  # Not available
            "throttled": False,
            "text": translated_text or "(text not available)"
        }

        debug_data["mt"].append(mt_entry)
        debug_data["totals"]["mt_cost_usd"] += cost_usd

    debug_data["totals"]["total_cost_usd"] = (
        debug_data["totals"]["stt_cost_usd"] +
        debug_data["totals"]["mt_cost_usd"]
    )
    debug_data["totals"]["mt_translations"] = len(debug_data["mt"])

    return {
        "source": "database",
        "segment_id": segment_id,
        "note": "Reconstructed from database. Some fields (latency, routing details) unavailable for old messages.",
        "data": debug_data
    }

# ============================================================================
# Phase 3 Admin Panel APIs (Financial, User, System Analytics)
# ============================================================================

# Response Models
class UserAcquisitionResponse(BaseModel):
    date: str
    new_users: int
    activated_users: int
    fast_activation: int

class UserEngagementResponse(BaseModel):
    metric_date: str
    dau: int
    wau: int
    mau: int

class SystemPerformanceResponse(BaseModel):
    service: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    total_requests: int

class ActiveRoomResponse(BaseModel):
    room_code: str
    room_id: int
    owner_email: str
    participant_count: int
    created_at: datetime
    is_multi_speaker: bool

class UserSearchResult(BaseModel):
    user_id: int
    email: str
    display_name: str
    signup_date: datetime

# Endpoint 3: User Acquisition (US-004)
@router.get("/users/acquisition")
def get_user_acquisition(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    granularity: Optional[str] = Query("day", description="hour|day|week|month"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get user acquisition metrics: signups, activation rates, fast activation.

    US-004: User Acquisition Metrics Page
    - New signups per day
    - Activated users (created at least 1 room)
    - Fast activation (created room within 1 hour of signup)
    - Previous period comparison for trends
    """
    # Default to last 30 days
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()

    # Validate date range (max 1 year)
    date_diff = end_date - start_date
    if date_diff.days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 1 year")

    # Calculate previous period for comparison
    period_duration = end_date - start_date
    prev_end_date = start_date - timedelta(seconds=1)
    prev_start_date = prev_end_date - period_duration

    # Query for current period
    query = text("""
        WITH daily_signups AS (
            SELECT
                DATE(created_at) as signup_date,
                id as user_id,
                created_at
            FROM users
            WHERE created_at >= :start_date
              AND created_at <= :end_date
        ),
        activations AS (
            SELECT DISTINCT
                r.owner_id as user_id,
                MIN(r.created_at) as first_room_created
            FROM rooms r
            INNER JOIN daily_signups ds ON r.owner_id = ds.user_id
            GROUP BY r.owner_id
        )
        SELECT
            ds.signup_date as date,
            COUNT(DISTINCT ds.user_id) as new_signups,
            COUNT(DISTINCT a.user_id) as activated,
            ROUND(
                COALESCE(COUNT(DISTINCT a.user_id)::numeric / NULLIF(COUNT(DISTINCT ds.user_id), 0) * 100, 0),
                1
            ) as activation_pct,
            COUNT(DISTINCT CASE
                WHEN a.first_room_created <= ds.created_at + INTERVAL '1 hour'
                THEN a.user_id
            END) as fast_activated,
            ROUND(
                COALESCE(COUNT(DISTINCT CASE
                    WHEN a.first_room_created <= ds.created_at + INTERVAL '1 hour'
                    THEN a.user_id
                END)::numeric / NULLIF(COUNT(DISTINCT ds.user_id), 0) * 100, 0),
                1
            ) as fast_activation_pct
        FROM daily_signups ds
        LEFT JOIN activations a ON ds.user_id = a.user_id
        GROUP BY ds.signup_date
        ORDER BY ds.signup_date DESC
    """)

    results = db.execute(query, {"start_date": start_date, "end_date": end_date}).fetchall()

    # Query for previous period summary
    prev_query = text("""
        WITH prev_signups AS (
            SELECT id as user_id, created_at
            FROM users
            WHERE created_at >= :prev_start AND created_at <= :prev_end
        ),
        prev_activations AS (
            SELECT DISTINCT
                r.owner_id as user_id,
                MIN(r.created_at) as first_room_created
            FROM rooms r
            INNER JOIN prev_signups ps ON r.owner_id = ps.user_id
            GROUP BY r.owner_id
        )
        SELECT
            COUNT(DISTINCT ps.user_id) as total_signups,
            COUNT(DISTINCT pa.user_id) as activated_users,
            ROUND(
                COALESCE(COUNT(DISTINCT pa.user_id)::numeric / NULLIF(COUNT(DISTINCT ps.user_id), 0) * 100, 0),
                1
            ) as activation_rate,
            COUNT(DISTINCT CASE
                WHEN pa.first_room_created <= ps.created_at + INTERVAL '1 hour'
                THEN pa.user_id
            END) as fast_activated_users,
            ROUND(
                COALESCE(COUNT(DISTINCT CASE
                    WHEN pa.first_room_created <= ps.created_at + INTERVAL '1 hour'
                    THEN pa.user_id
                END)::numeric / NULLIF(COUNT(DISTINCT ps.user_id), 0) * 100, 0),
                1
            ) as fast_activation_rate
        FROM prev_signups ps
        LEFT JOIN prev_activations pa ON ps.user_id = pa.user_id
    """)

    prev_result = db.execute(prev_query, {
        "prev_start": prev_start_date,
        "prev_end": prev_end_date
    }).fetchone()

    # Build daily breakdown
    daily = []
    for row in results:
        daily.append({
            "date": row[0].strftime('%Y-%m-%d'),
            "new_signups": row[1],
            "activated": row[2],
            "activation_pct": float(row[3]),
            "fast_activated": row[4],
            "fast_activation_pct": float(row[5])
        })

    # Calculate summary metrics
    total_signups = sum(d["new_signups"] for d in daily)
    total_activated = sum(d["activated"] for d in daily)
    total_fast_activated = sum(d["fast_activated"] for d in daily)

    activation_rate = round(total_activated / total_signups * 100, 1) if total_signups > 0 else 0.0
    fast_activation_rate = round(total_fast_activated / total_signups * 100, 1) if total_signups > 0 else 0.0

    # Previous period data
    prev_total_signups = prev_result[0] if prev_result else 0
    prev_activation_rate = float(prev_result[2]) if prev_result else 0.0
    prev_fast_activation_rate = float(prev_result[4]) if prev_result else 0.0

    return {
        "summary": {
            "total_signups": total_signups,
            "activated_users": total_activated,
            "activation_rate": activation_rate,
            "fast_activated_users": total_fast_activated,
            "fast_activation_rate": fast_activation_rate,
            "previous_period": {
                "total_signups": prev_total_signups,
                "activation_rate": prev_activation_rate,
                "fast_activation_rate": prev_fast_activation_rate
            }
        },
        "daily": daily,
        "metadata": {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "granularity": granularity,
            "total_days": len(daily)
        }
    }

# Endpoint 4: User Engagement (DAU/WAU/MAU)
@router.get("/users/engagement")
def get_user_engagement(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get user engagement metrics: DAU, WAU, MAU.
    Calculates from room_participants table.
    """
    # Default to last 30 days
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()

    # Calculate DAU from room participants
    query = text("""
        SELECT
            DATE(joined_at) as metric_date,
            COUNT(DISTINCT user_id) as dau
        FROM room_participants
        WHERE joined_at >= :start_date AND joined_at <= :end_date
        GROUP BY DATE(joined_at)
        ORDER BY metric_date DESC
        LIMIT 30
    """)

    results = db.execute(query, {"start_date": start_date, "end_date": end_date}).fetchall()

    metrics = []
    for row in results:
        metrics.append({
            "metric_date": row[0].strftime('%Y-%m-%d'),
            "dau": row[1] or 0,
            "wau": None,
            "mau": None
        })

    return {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "metrics": metrics
    }

# Endpoint 5: User Retention (Cohort Analysis)
@router.get("/users/retention")
def get_user_retention(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get cohort retention rates.
    Shows what % of users return after 1 day, 7 days, 30 days.
    """
    # Default to last 90 days for cohorts
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=90)
    if not end_date:
        end_date = datetime.utcnow()

    query = text("""
        WITH user_cohorts AS (
            SELECT
                user_id,
                DATE(created_at) as cohort_date,
                created_at
            FROM users
            WHERE created_at >= :start_date AND created_at <= :end_date
        ),
        user_activity AS (
            SELECT DISTINCT
                rp.user_id,
                DATE(rp.joined_at) as activity_date
            FROM room_participants rp
            WHERE rp.user_id IS NOT NULL
              AND rp.joined_at >= :start_date
        )
        SELECT
            uc.cohort_date,
            COUNT(DISTINCT uc.user_id) as cohort_size,
            COUNT(DISTINCT CASE
                WHEN ua.activity_date BETWEEN uc.cohort_date + INTERVAL '1 day'
                    AND uc.cohort_date + INTERVAL '2 days'
                THEN uc.user_id
            END) as day_1_retention,
            COUNT(DISTINCT CASE
                WHEN ua.activity_date BETWEEN uc.cohort_date + INTERVAL '7 days'
                    AND uc.cohort_date + INTERVAL '8 days'
                THEN uc.user_id
            END) as day_7_retention,
            COUNT(DISTINCT CASE
                WHEN ua.activity_date BETWEEN uc.cohort_date + INTERVAL '30 days'
                    AND uc.cohort_date + INTERVAL '31 days'
                THEN uc.user_id
            END) as day_30_retention
        FROM user_cohorts uc
        LEFT JOIN user_activity ua ON uc.user_id = ua.user_id
        GROUP BY uc.cohort_date
        ORDER BY uc.cohort_date DESC
    """)

    results = db.execute(query, {"start_date": start_date, "end_date": end_date}).fetchall()

    cohorts = []
    for row in results:
        cohort_size = row[1]
        day_1 = row[2]
        day_7 = row[3]
        day_30 = row[4]

        cohorts.append({
            "cohort_date": row[0].strftime('%Y-%m-%d'),
            "cohort_size": cohort_size,
            "day_1_retention": day_1,
            "day_1_retention_pct": round(day_1 / cohort_size * 100, 1) if cohort_size > 0 else 0.0,
            "day_7_retention": day_7,
            "day_7_retention_pct": round(day_7 / cohort_size * 100, 1) if cohort_size > 0 else 0.0,
            "day_30_retention": day_30,
            "day_30_retention_pct": round(day_30 / cohort_size * 100, 1) if cohort_size > 0 else 0.0
        })

    return {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "cohorts": cohorts
    }

# Endpoint 6: System Performance (Provider Costs Only)
@router.get("/system/performance")
def get_system_performance(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get system performance metrics: provider costs and request counts.
    Note: Latency metrics not available (events table lacks timing data).
    """
    # Default to last 24 hours
    if not start_date:
        start_date = datetime.utcnow() - timedelta(hours=24)
    if not end_date:
        end_date = datetime.utcnow()

    # Get provider-level performance from room_costs
    provider_query = text("""
        SELECT
            pipeline as service,
            provider,
            COUNT(*) as request_count,
            AVG(amount_usd) as avg_cost_per_request,
            SUM(amount_usd) as total_cost
        FROM room_costs
        WHERE ts >= :start_date AND ts <= :end_date
          AND provider IS NOT NULL
        GROUP BY pipeline, provider
        ORDER BY pipeline, request_count DESC
    """)

    provider_results = db.execute(provider_query, {"start_date": start_date, "end_date": end_date}).fetchall()

    providers = []
    for row in provider_results:
        providers.append({
            "service": row[0],
            "provider": row[1],
            "request_count": row[2],
            "avg_cost_per_request": round(float(row[3]), 6),
            "total_cost": round(float(row[4]), 4)
        })

    return {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "message": "Latency metrics not available (events table lacks timing data)",
        "providers": providers,
        "recommendation": "Add latency tracking in future migration"
    }

# Endpoint 8: Search Users (US-009)
@router.get("/users/search")
def search_users(
    q: str = Query("", description="Search query (email or user ID)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Search for users by email or user ID.
    Returns user details and signup date.
    Limited to 50 results.
    """
    if not q or q.strip() == "":
        return {"results": []}

    query = q.strip()

    # Try to parse as user ID (integer)
    try:
        user_id = int(query)
        search_by_id = True
    except ValueError:
        search_by_id = False

    if search_by_id:
        sql_query = text("""
            SELECT u.id, u.email, u.display_name, u.created_at
            FROM users u
            WHERE u.id = :query
            LIMIT 1
        """)
        results = db.execute(sql_query, {"query": user_id}).fetchall()
    else:
        sql_query = text("""
            SELECT u.id, u.email, u.display_name, u.created_at
            FROM users u
            WHERE LOWER(u.email) LIKE LOWER(:query)
            ORDER BY u.created_at DESC
            LIMIT 50
        """)
        search_pattern = f"%{query}%"
        results = db.execute(sql_query, {"query": search_pattern}).fetchall()

    user_results = []
    for row in results:
        signup_date = row[3]
        if signup_date:
            signup_date_str = signup_date.isoformat() if not isinstance(signup_date, str) else signup_date
        else:
            signup_date_str = None

        user_results.append({
            "user_id": row[0],
            "email": row[1],
            "display_name": row[2] or "",
            "signup_date": signup_date_str
        })

    return {"results": user_results}


# Endpoint 9: Active Rooms
@router.get("/rooms/active")
def get_active_rooms(
    limit: int = Query(50, le=500, description="Max 500 results per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    start_date: Optional[datetime] = Query(None, description="Activity start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Activity end date (ISO format)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get currently active rooms with participant counts (paginated).
    Shows rooms with recent activity (default: last 24 hours).
    """
    # Default to last 24 hours if not specified
    if not start_date:
        start_date = datetime.utcnow() - timedelta(hours=24)
    if not end_date:
        end_date = datetime.utcnow()

    query = text("""
        SELECT
            r.code as room_code,
            r.id as room_id,
            r.created_at,
            r.is_public,
            r.speakers_locked,
            u.email as owner_email,
            u.display_name as owner_name,
            COUNT(DISTINCT rp.user_id) as participant_count,
            MAX(rp.joined_at) as last_join_time
        FROM rooms r
        JOIN users u ON r.owner_id = u.id
        LEFT JOIN room_participants rp ON r.id = rp.room_id AND rp.is_active = TRUE
        WHERE rp.joined_at >= :start_date
          AND rp.joined_at <= :end_date
        GROUP BY r.id, r.code, r.created_at, r.is_public, r.speakers_locked, u.email, u.display_name
        ORDER BY last_join_time DESC
        LIMIT :limit OFFSET :offset
    """)

    results = db.execute(query, {
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
        "offset": offset
    }).fetchall()

    rooms = []
    for row in results:
        rooms.append({
            "room_code": row[0],
            "room_id": row[1],
            "created_at": row[2],
            "is_public": row[3],
            "is_multi_speaker": row[4],
            "owner_email": row[5],
            "owner_name": row[6],
            "participant_count": row[7],
            "last_activity": row[8]
        })

    return {
        "active_rooms": rooms,
        "total_returned": len(rooms),
        "limit": limit,
        "offset": offset,
        "has_more": len(rooms) == limit
    }

# ============================================================================
# US-003: System Settings Page APIs
# ============================================================================

class FeatureFlagUpdate(BaseModel):
    value: str  # String representation (parsed based on value_type)

class ProviderRoutingUpdate(BaseModel):
    provider_primary: Optional[str] = None
    provider_fallback: Optional[str] = None
    enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

class RateLimitUpdate(BaseModel):
    limits: Dict[str, int]  # key -> new_value mapping

@router.get("/settings/feature-flags")
def get_feature_flags(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get all feature flags with metadata (US-003)"""
    query = text("""
        SELECT
            ss.key,
            ss.value,
            ss.value_type,
            ss.description,
            ss.category,
            ss.updated_at,
            u.email as updated_by_email
        FROM system_settings ss
        LEFT JOIN users u ON ss.updated_by = u.id
        WHERE ss.category IN ('stt', 'mt', 'ui')
        ORDER BY ss.category, ss.key
    """)

    results = db.execute(query).fetchall()

    flags = []
    for row in results:
        # Parse value based on type
        value = row[1]
        if row[2] == 'boolean':
            value = value.lower() == 'true'
        elif row[2] == 'integer':
            value = int(value)

        flags.append({
            "key": row[0],
            "value": value,
            "value_type": row[2],
            "description": row[3],
            "category": row[4],
            "updated_at": row[5].isoformat() if row[5] else None,
            "updated_by": row[6]
        })

    return {"flags": flags}

@router.put("/settings/feature-flags/{key}")
def update_feature_flag(
    key: str,
    update: FeatureFlagUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update a single feature flag (US-003)"""
    # Get current value
    query = text("""
        SELECT value, value_type
        FROM system_settings
        WHERE key = :key
    """)

    result = db.execute(query, {"key": key}).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail=f"Feature flag '{key}' not found")

    old_value = result[0]
    value_type = result[1]

    # Validate value based on type
    new_value = update.value
    if value_type == 'boolean':
        if new_value.lower() not in ['true', 'false']:
            raise HTTPException(status_code=400, detail="Boolean value must be 'true' or 'false'")
    elif value_type == 'integer':
        try:
            int(new_value)
        except ValueError:
            raise HTTPException(status_code=400, detail="Integer value required")

    # Update setting
    update_query = text("""
        UPDATE system_settings
        SET value = :value,
            updated_at = NOW(),
            updated_by = :admin_id
        WHERE key = :key
        RETURNING updated_at
    """)

    updated_at = db.execute(update_query, {
        "key": key,
        "value": new_value,
        "admin_id": admin.id
    }).fetchone()[0]

    db.commit()

    return {
        "message": f"Feature flag '{key}' updated",
        "key": key,
        "old_value": old_value == 'true' if value_type == 'boolean' else old_value,
        "new_value": new_value == 'true' if value_type == 'boolean' else new_value,
        "updated_at": updated_at.isoformat()
    }

@router.get("/settings/rate-limits")
def get_rate_limits(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get rate limit settings (US-003)"""
    query = text("""
        SELECT key, value, description, updated_at
        FROM system_settings
        WHERE category = 'performance'
        ORDER BY key
    """)

    results = db.execute(query).fetchall()

    limits = []
    for row in results:
        limits.append({
            "key": row[0],
            "value": int(row[1]),
            "description": row[2],
            "updated_at": row[3].isoformat() if row[3] else None
        })

    return {"limits": limits}

@router.put("/settings/rate-limits")
def update_rate_limits(
    update: RateLimitUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update multiple rate limits at once (US-003)"""
    updated_keys = []

    for key, value in update.limits.items():
        # Validate key exists and is performance category
        query = text("""
            SELECT value_type, category
            FROM system_settings
            WHERE key = :key
        """)

        result = db.execute(query, {"key": key}).fetchone()

        if not result:
            raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

        if result[1] != 'performance':
            raise HTTPException(status_code=400, detail=f"Setting '{key}' is not a rate limit")

        # Update setting
        update_query = text("""
            UPDATE system_settings
            SET value = :value,
                updated_at = NOW(),
                updated_by = :admin_id
            WHERE key = :key
        """)

        db.execute(update_query, {
            "key": key,
            "value": str(value),
            "admin_id": admin.id
        })

        updated_keys.append(key)

    db.commit()

    return {
        "message": f"Updated {len(updated_keys)} rate limits",
        "updated": updated_keys
    }

@router.put("/routing/stt/{id}")
def update_stt_routing(
    id: int,
    update: ProviderRoutingUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Update STT routing configuration (US-003)"""
    # Get current config
    query = text("""
        SELECT language, mode, quality_tier
        FROM stt_routing_config
        WHERE id = :id
    """)

    result = db.execute(query, {"id": id}).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail=f"STT routing config {id} not found")

    language, mode, quality_tier = result

    # Build update query dynamically
    updates = []
    params = {"id": id}

    if update.provider_primary is not None:
        updates.append("provider_primary = :provider_primary")
        params["provider_primary"] = update.provider_primary

    if update.provider_fallback is not None:
        updates.append("provider_fallback = :provider_fallback")
        params["provider_fallback"] = update.provider_fallback

    if update.enabled is not None:
        updates.append("enabled = :enabled")
        params["enabled"] = update.enabled

    if update.config is not None:
        updates.append("config = :config")
        params["config"] = json.dumps(update.config)

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    updates.append("updated_at = NOW()")

    update_query = text(f"""
        UPDATE stt_routing_config
        SET {', '.join(updates)}
        WHERE id = :id
        RETURNING updated_at
    """)

    updated_at = db.execute(update_query, params).fetchone()[0]
    db.commit()

    # Clear language router cache
    cache_cleared = False
    try:
        from .stt.language_router import clear_cache
        clear_cache(language=language, service_type='stt')
        cache_cleared = True
    except Exception as e:
        print(f"[Admin API] Failed to clear cache: {e}")

    return {
        "message": f"STT routing config updated for {language} {mode}/{quality_tier}",
        "id": id,
        "language": language,
        "mode": mode,
        "quality_tier": quality_tier,
        "cache_cleared": cache_cleared,
        "updated_at": updated_at.isoformat()
    }

@router.get("/system/usage-stats")
def get_usage_stats(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get current system usage vs configured limits (US-003)"""
    # Get rate limits from system_settings
    limits_query = text("""
        SELECT key, value
        FROM system_settings
        WHERE category = 'performance'
    """)

    limits = {row[0]: int(row[1]) for row in db.execute(limits_query).fetchall()}

    # Get active rooms count
    active_rooms_query = text("""
        SELECT COUNT(DISTINCT r.id)
        FROM rooms r
        JOIN room_participants rp ON r.id = rp.room_id
        WHERE rp.joined_at > NOW() - INTERVAL '1 hour'
          AND rp.is_active = true
    """)

    active_rooms = db.execute(active_rooms_query).scalar() or 0

    # Get MT requests last minute (approximate from room_costs)
    mt_requests_query = text("""
        SELECT COUNT(*)
        FROM room_costs
        WHERE pipeline = 'mt'
          AND ts > NOW() - INTERVAL '1 minute'
    """)

    mt_requests = db.execute(mt_requests_query).scalar() or 0

    return {
        "stt_active_connections": 0,  # Placeholder - requires Redis tracking
        "stt_max_connections": limits.get("stt_max_concurrent_connections", 100),
        "active_rooms": active_rooms,
        "max_room_participants": limits.get("max_room_participants", 50),
        "mt_requests_last_minute": mt_requests,
        "mt_limit_per_minute": limits.get("api_requests_per_minute_global", 1000)
    }

# ============================================================================
# US-007: Support Tools Page APIs
# ============================================================================

@router.get("/rooms/lookup")
def lookup_room(
    q: str = Query(..., description="Room code or room ID"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Lookup room by code or ID with full details (US-007).
    Returns room metadata, participant counts, message count, and cost summary.
    """
    # Try parsing as ID first
    try:
        room_id = int(q)
        query_filter = "r.id = :query_id"
        params = {"query_id": room_id}
    except ValueError:
        query_filter = "UPPER(r.code) = UPPER(:query)"
        params = {"query": q}

    query = text(f"""
        SELECT
            r.code as room_code,
            r.id as room_id,
            r.created_at,
            r.is_public,
            r.speakers_locked as is_multi_speaker,
            u.email as owner_email,
            u.id as owner_id,
            COUNT(DISTINCT rp.id) as total_participants,
            COUNT(DISTINCT CASE WHEN rp.left_at IS NULL THEN rp.id END) as participant_count,
            COUNT(DISTINCT s.id) as message_count,
            COALESCE(SUM(CASE WHEN rc.pipeline = 'stt' THEN rc.amount_usd ELSE 0 END), 0) as stt_cost,
            COALESCE(SUM(CASE WHEN rc.pipeline = 'mt' THEN rc.amount_usd ELSE 0 END), 0) as mt_cost
        FROM rooms r
        JOIN users u ON r.owner_id = u.id
        LEFT JOIN room_participants rp ON r.id = rp.room_id
        LEFT JOIN segments s ON r.id = s.room_id
        LEFT JOIN room_costs rc ON CAST(r.id AS TEXT) = rc.room_id
        WHERE {query_filter}
        GROUP BY r.id, r.code, r.created_at, r.is_public, r.speakers_locked, u.email, u.id
    """)

    result = db.execute(query, params).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail="Room not found")

    stt_cost = float(result[10] or 0)
    mt_cost = float(result[11] or 0)

    return {
        "room_code": result[0],
        "room_id": result[1],
        "created_at": result[2].isoformat() if result[2] else None,
        "is_public": result[3],
        "is_multi_speaker": result[4],
        "owner_email": result[5],
        "owner_id": result[6],
        "total_participants": result[7],
        "participant_count": result[8],
        "message_count": result[9],
        "cost_summary": {
            "stt_cost_usd": stt_cost,
            "mt_cost_usd": mt_cost,
            "total_cost_usd": stt_cost + mt_cost
        },
        "status": "active"
    }

@router.get("/rooms/{room_code}/messages")
def get_room_messages(
    room_code: str,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get message history for a room (US-007).
    Returns paginated list of segments with speaker information.
    """
    # Get messages
    query = text("""
        SELECT
            s.segment_id,
            s.ts_iso as timestamp,
            s.text,
            s.lang,
            s.final as is_final,
            s.speaker_id,
            COALESCE(u.email, 'Unknown') as speaker_email
        FROM segments s
        LEFT JOIN room_participants rp ON s.room_id = rp.room_id AND s.speaker_id = rp.id
        LEFT JOIN users u ON rp.user_id = u.id
        WHERE s.room_id = (SELECT id FROM rooms WHERE code = :room_code)
        ORDER BY s.segment_id DESC
        LIMIT :limit OFFSET :offset
    """)

    results = db.execute(query, {"room_code": room_code.upper(), "limit": limit, "offset": offset}).fetchall()

    # Count total messages
    count_query = text("""
        SELECT COUNT(*) FROM segments WHERE room_id = (SELECT id FROM rooms WHERE code = :room_code)
    """)
    total = db.execute(count_query, {"room_code": room_code.upper()}).scalar() or 0

    messages = []
    for row in results:
        messages.append({
            "segment_id": row[0],
            "timestamp": row[1].isoformat() if row[1] else None,
            "text": row[2],
            "lang": row[3],
            "is_final": row[4],
            "speaker_id": row[5],
            "speaker_email": row[6]
        })

    return {
        "messages": messages,
        "total": total,
        "has_more": (offset + limit) < total
    }

@router.get("/debug/redis/keys")
def list_redis_keys(
    pattern: str = Query(..., description="Redis key pattern"),
    limit: int = Query(50, le=100),
    admin: User = Depends(require_admin)
):
    """
    List Redis keys matching pattern (US-007).
    Uses SCAN for non-blocking operation. Limited to safe prefixes.
    """
    import redis as redis_sync

    # Validate pattern (security)
    allowed_prefixes = ['room:', 'debug:', 'stt_cache:', 'mt_cache:']
    if not any(pattern.startswith(prefix) for prefix in allowed_prefixes):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pattern. Must start with: {', '.join(allowed_prefixes)}"
        )

    r = redis_sync.from_url(REDIS_URL, decode_responses=True)
    try:
        keys = []
        cursor = 0

        # SCAN for keys (safe, non-blocking)
        while len(keys) < limit:
            cursor, batch = r.scan(cursor, match=pattern, count=100)
            keys.extend(batch)
            if cursor == 0:
                break

        keys = keys[:limit]

        # Get metadata for each key
        key_data = []
        for key in keys:
            key_type = r.type(key)
            ttl = r.ttl(key)
            try:
                size = r.memory_usage(key) or 0
            except:
                size = 0

            key_data.append({
                "key": key,
                "type": key_type,
                "ttl": ttl,
                "size_bytes": size
            })

        return {
            "keys": key_data,
            "total": len(key_data),
            "truncated": len(key_data) >= limit
        }
    finally:
        r.close()

@router.get("/debug/redis/get")
def get_redis_value(
    key: str = Query(..., description="Redis key"),
    admin: User = Depends(require_admin)
):
    """
    Get Redis key value (US-007).
    Supports string, hash, list, set, and sorted set types.
    """
    import redis as redis_sync

    r = redis_sync.from_url(REDIS_URL, decode_responses=True)
    try:
        key_type = r.type(key)
        ttl = r.ttl(key)

        if key_type == 'string':
            raw = r.get(key)
        elif key_type == 'hash':
            raw = r.hgetall(key)
        elif key_type == 'list':
            raw = r.lrange(key, 0, 100)  # Limit to 100 items
        elif key_type == 'set':
            raw = list(r.smembers(key))[:100]
        elif key_type == 'zset':
            raw = r.zrange(key, 0, 100)
        else:
            raw = f"<{key_type} not displayable>"

        # Try to parse as JSON
        try:
            if isinstance(raw, str):
                value = json.loads(raw)
            else:
                value = raw
        except:
            value = raw

        # Truncate large values
        raw_str = str(raw)
        if len(raw_str) > 10240:
            raw_str = raw_str[:10240] + "... (truncated)"

        return {
            "key": key,
            "type": key_type,
            "value": value,
            "ttl": ttl,
            "raw": raw_str
        }
    finally:
        r.close()

@router.post("/cache/clear")
def clear_cache(
    request: dict,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Clear cache by type (US-007).
    Supports room_translations, stt_cache, mt_cache, all_stt.
    Clears matching Redis keys.
    """
    import redis as redis_sync

    cache_type = request.get("cache_type")
    room_code = request.get("room_code")

    if cache_type == "room_translations" and not room_code:
        raise HTTPException(status_code=400, detail="room_code required for room_translations")

    r = redis_sync.from_url(REDIS_URL, decode_responses=True)
    try:
        keys_deleted = 0

        if cache_type == "room_translations":
            patterns = [f"stt_cache:{room_code.upper()}:*", f"mt_cache:{room_code.upper()}:*"]
        elif cache_type == "stt_cache":
            patterns = ["stt_cache:*"]
        elif cache_type == "mt_cache":
            patterns = ["mt_cache:*"]
        elif cache_type == "all_stt":
            patterns = ["stt_*"]
        else:
            raise HTTPException(status_code=400, detail="Invalid cache_type")

        # SCAN + DEL for each pattern
        for pattern in patterns:
            cursor = 0
            while True:
                cursor, keys = r.scan(cursor, match=pattern, count=100)
                if keys:
                    keys_deleted += r.delete(*keys)
                if cursor == 0:
                    break

        return {
            "message": "Cache cleared",
            "keys_deleted": keys_deleted,
            "cache_type": cache_type,
            "room_code": room_code
        }
    finally:
        r.close()

@router.get("/cache/stats")
def get_cache_stats(admin: User = Depends(require_admin)):
    """
    Get cache statistics (US-007).
    Shows Redis memory usage and key counts by type.
    """
    import redis as redis_sync

    r = redis_sync.from_url(REDIS_URL, decode_responses=True)
    try:
        info = r.info()

        # Count keys by pattern
        patterns = {
            "stt_cache": "stt_cache:*",
            "mt_cache": "mt_cache:*",
            "room_presence": "room:*:presence",
            "debug_keys": "debug:*"
        }

        breakdown = {}
        for name, pattern in patterns.items():
            cursor = 0
            count = 0
            while True:
                cursor, keys = r.scan(cursor, match=pattern, count=100)
                count += len(keys)
                if cursor == 0:
                    break
            breakdown[name] = count

        return {
            "redis_info": {
                "used_memory_human": info.get("used_memory_human", "Unknown"),
                "total_keys": r.dbsize(),
                "uptime_days": info.get("uptime_in_seconds", 0) // 86400
            },
            "cache_breakdown": breakdown
        }
    finally:
        r.close()
