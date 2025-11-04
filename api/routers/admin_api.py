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
class FinancialSummaryResponse(BaseModel):
    period: str
    total_revenue_usd: float
    total_cost_usd: float
    gross_profit_usd: float
    gross_margin_pct: float
    stripe_revenue: float
    apple_revenue: float
    credit_revenue: float

class TierAnalysisResponse(BaseModel):
    tier_name: str
    user_count: int
    total_revenue: float
    avg_quota_used_hours: float
    total_cost: float
    profit_per_user: float

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
    paying_users: int
    free_users: int

class SystemPerformanceResponse(BaseModel):
    service: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    total_requests: int

class QuotaUtilizationResponse(BaseModel):
    tier_name: str
    total_users: int
    avg_quota_used_pct: float
    total_quota_used_hours: float
    total_quota_allocated_hours: float

class ActiveRoomResponse(BaseModel):
    room_code: str
    room_id: int
    owner_email: str
    participant_count: int
    created_at: datetime
    is_multi_speaker: bool

class GrantCreditsRequest(BaseModel):
    bonus_hours: float
    reason: str

class UserSearchResult(BaseModel):
    user_id: int
    email: str
    display_name: str
    tier_name: Optional[str]
    quota_used_hours: float
    quota_limit_hours: Optional[float]
    signup_date: datetime

# Endpoint 1: Financial Summary
@router.get("/financial/summary")
def get_financial_summary(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    granularity: Optional[str] = Query("day", description="hour|day|week|month"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get financial summary: revenue, costs, profit, margins from materialized view.
    Query admin_financial_summary view with date range filtering.
    """
    # Default to last 30 days if not specified
    if not start_date:
        start_date = datetime.utcnow() - timedelta(days=30)
    if not end_date:
        end_date = datetime.utcnow()

    # Query materialized view
    query = text("""
        SELECT
            day,
            platform,
            revenue_usd,
            transaction_count
        FROM admin_financial_summary
        WHERE day >= :start_date AND day <= :end_date
        ORDER BY day DESC, platform
    """)

    results = db.execute(query, {"start_date": start_date, "end_date": end_date}).fetchall()

    # Get costs for the same period
    costs_query = text("""
        SELECT COALESCE(SUM(amount_usd), 0) as total_cost
        FROM room_costs
        WHERE ts >= :start_date AND ts <= :end_date
    """)

    total_cost = float(db.execute(costs_query, {"start_date": start_date, "end_date": end_date}).scalar() or 0)

    # Aggregate by day
    daily_data = {}
    for row in results:
        day_str = row[0].strftime('%Y-%m-%d')
        if day_str not in daily_data:
            daily_data[day_str] = {
                "stripe_revenue": 0.0,
                "apple_revenue": 0.0,
                "credit_revenue": 0.0
            }

        platform = row[1]
        revenue = float(row[2])

        if platform == "stripe":
            daily_data[day_str]["stripe_revenue"] += revenue
        elif platform == "apple":
            daily_data[day_str]["apple_revenue"] += revenue
        elif platform == "credit":
            daily_data[day_str]["credit_revenue"] += revenue

    # Calculate totals
    total_revenue = sum(
        day["stripe_revenue"] + day["apple_revenue"] + day["credit_revenue"]
        for day in daily_data.values()
    )

    gross_profit = total_revenue - total_cost
    gross_margin = (gross_profit / total_revenue * 100) if total_revenue > 0 else 0.0

    stripe_revenue = sum(day["stripe_revenue"] for day in daily_data.values())
    apple_revenue = sum(day["apple_revenue"] for day in daily_data.values())
    credit_revenue = sum(day["credit_revenue"] for day in daily_data.values())

    return {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "total_revenue_usd": round(total_revenue, 2),
        "total_cost_usd": round(total_cost, 2),
        "gross_profit_usd": round(gross_profit, 2),
        "gross_margin_pct": round(gross_margin, 2),
        "stripe_revenue": round(stripe_revenue, 2),
        "apple_revenue": round(apple_revenue, 2),
        "credit_revenue": round(credit_revenue, 2)
    }

# Endpoint 2: Tier Analysis
@router.get("/financial/tier-analysis")
def get_tier_analysis(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get tier profitability analysis from admin_tier_analysis materialized view.
    Shows Free/Plus/Pro revenue, costs, and profit per user.
    """
    # Default to current month if not specified
    if not start_date:
        start_date = datetime.utcnow().replace(day=1)
    if not end_date:
        end_date = datetime.utcnow()

    # Query materialized view
    query = text("""
        SELECT
            tier_name,
            display_name,
            active_users,
            monthly_recurring_revenue,
            total_costs_usd,
            gross_profit_usd
        FROM admin_tier_analysis
        ORDER BY tier_name
    """)

    results = db.execute(query).fetchall()

    tiers = []
    for row in results:
        tier_name = row[0]
        active_users = row[2]
        mrr = float(row[3] or 0)
        costs = float(row[4] or 0)
        profit = float(row[5] or 0)

        # Calculate average quota used
        quota_query = text("""
            SELECT AVG(quota_used_hours) as avg_quota
            FROM (
                SELECT
                    qt.user_id,
                    SUM(-qt.amount_seconds) / 3600.0 as quota_used_hours
                FROM quota_transactions qt
                JOIN user_subscriptions us ON qt.user_id = us.user_id
                JOIN subscription_tiers st ON us.tier_id = st.id
                WHERE st.tier_name = :tier_name
                  AND qt.transaction_type = 'deduct'
                  AND qt.created_at >= :start_date
                  AND qt.created_at <= :end_date
                GROUP BY qt.user_id
            ) user_quotas
        """)

        avg_quota = db.execute(quota_query, {
            "tier_name": tier_name,
            "start_date": start_date,
            "end_date": end_date
        }).scalar() or 0.0

        profit_per_user = profit / active_users if active_users > 0 else 0.0

        tiers.append({
            "tier_name": tier_name,
            "user_count": active_users,
            "total_revenue": round(mrr, 2),
            "avg_quota_used_hours": round(float(avg_quota), 2),
            "total_cost": round(costs, 2),
            "profit_per_user": round(profit_per_user, 2)
        })

    return {"tiers": tiers}

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
            COUNT(DISTINCT user_id) as dau,
            COUNT(DISTINCT user_id) FILTER (
                WHERE user_id IN (
                    SELECT user_id FROM user_subscriptions
                    WHERE status = 'active'
                    AND tier_id IN (SELECT id FROM subscription_tiers WHERE tier_name IN ('plus', 'pro'))
                )
            ) as paying_users,
            COUNT(DISTINCT user_id) FILTER (
                WHERE user_id IN (
                    SELECT user_id FROM user_subscriptions
                    WHERE tier_id IN (SELECT id FROM subscription_tiers WHERE tier_name = 'free')
                )
            ) as free_users
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
            "wau": None,  # Removed - requires separate calculation
            "mau": None,  # Removed - requires separate calculation
            "paying_users": row[2] or 0,
            "free_users": row[3] or 0
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

# Endpoint 7: Quota Utilization
@router.get("/system/quota-utilization")
def get_quota_utilization(
    start_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get quota usage by tier from quota_transactions table.
    Shows how much quota each tier is consuming.
    """
    # Default to current billing period
    if not start_date:
        start_date = datetime.utcnow().replace(day=1)
    if not end_date:
        end_date = datetime.utcnow()

    query = text("""
        SELECT
            st.tier_name,
            st.display_name,
            st.monthly_quota_hours,
            COUNT(DISTINCT qt.user_id) as total_users,
            SUM(-qt.amount_seconds) / 3600.0 as total_quota_used_hours,
            AVG(-qt.amount_seconds) / 3600.0 as avg_quota_per_user_hours
        FROM subscription_tiers st
        LEFT JOIN user_subscriptions us ON st.id = us.tier_id
        LEFT JOIN quota_transactions qt ON us.user_id = qt.user_id
            AND qt.transaction_type = 'deduct'
            AND qt.created_at >= :start_date
            AND qt.created_at <= :end_date
        WHERE us.status = 'active'
        GROUP BY st.id, st.tier_name, st.display_name, st.monthly_quota_hours
        ORDER BY st.tier_name
    """)

    results = db.execute(query, {"start_date": start_date, "end_date": end_date}).fetchall()

    utilization = []
    for row in results:
        tier_name = row[0]
        monthly_quota = float(row[2]) if row[2] else 0.0
        total_users = row[3] or 0
        total_used = float(row[4] or 0)
        avg_per_user = float(row[5] or 0)

        total_allocated = monthly_quota * total_users if monthly_quota > 0 else 0.0
        avg_utilization_pct = (total_used / total_allocated * 100) if total_allocated > 0 else 0.0

        utilization.append({
            "tier_name": tier_name,
            "total_users": total_users,
            "avg_quota_used_pct": round(avg_utilization_pct, 2),
            "total_quota_used_hours": round(total_used, 2),
            "total_quota_allocated_hours": round(total_allocated, 2),
            "avg_quota_per_user_hours": round(avg_per_user, 2)
        })

    return {
        "period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        "utilization": utilization
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
    Returns user details including tier, quota, and signup date.
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
        # Search by user ID (exact match)
        sql_query = text("""
            SELECT
                u.id as user_id,
                u.email,
                u.display_name,
                st.tier_name,
                COALESCE(SUM(-qt.amount_seconds) / 3600.0, 0) as quota_used_hours,
                st.monthly_quota_hours as quota_limit_hours,
                u.created_at as signup_date
            FROM users u
            LEFT JOIN user_subscriptions us ON u.id = us.user_id
            LEFT JOIN subscription_tiers st ON us.tier_id = st.id
            LEFT JOIN quota_transactions qt ON u.id = qt.user_id
                AND qt.transaction_type = 'deduct'
                AND qt.created_at >= us.billing_period_start
            WHERE u.id = :query
            GROUP BY u.id, u.email, u.display_name, st.tier_name, st.monthly_quota_hours, u.created_at
            LIMIT 1
        """)
        results = db.execute(sql_query, {"query": user_id}).fetchall()
    else:
        # Search by email (case-insensitive partial match)
        sql_query = text("""
            SELECT
                u.id as user_id,
                u.email,
                u.display_name,
                st.tier_name,
                COALESCE(SUM(-qt.amount_seconds) / 3600.0, 0) as quota_used_hours,
                st.monthly_quota_hours as quota_limit_hours,
                u.created_at as signup_date
            FROM users u
            LEFT JOIN user_subscriptions us ON u.id = us.user_id
            LEFT JOIN subscription_tiers st ON us.tier_id = st.id
            LEFT JOIN quota_transactions qt ON u.id = qt.user_id
                AND qt.transaction_type = 'deduct'
                AND qt.created_at >= us.billing_period_start
            WHERE LOWER(u.email) LIKE LOWER(:query)
            GROUP BY u.id, u.email, u.display_name, st.tier_name, st.monthly_quota_hours, u.created_at
            ORDER BY u.created_at DESC
            LIMIT 50
        """)
        search_pattern = f"%{query}%"
        results = db.execute(sql_query, {"query": search_pattern}).fetchall()

    # Format results
    user_results = []
    for row in results:
        # Handle signup_date - can be datetime or string (SQLite)
        signup_date = row[6]
        if signup_date:
            if isinstance(signup_date, str):
                signup_date_str = signup_date
            else:
                signup_date_str = signup_date.isoformat()
        else:
            signup_date_str = None

        user_results.append({
            "user_id": row[0],
            "email": row[1],
            "display_name": row[2] or "",
            "tier_name": row[3] or "free",
            "quota_used_hours": round(float(row[4]), 2),
            "quota_limit_hours": float(row[5]) if row[5] else None,
            "signup_date": signup_date_str
        })

    return {"results": user_results}


# Endpoint 9: Grant Credits to User
@router.post("/users/{user_id}/grant-credits")
def grant_credits_to_user(
    user_id: int,
    request: GrantCreditsRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Grant bonus quota to a user (admin action).
    Creates quota_transaction and updates user_subscriptions.
    """
    # Verify user exists
    user_query = text("""
        SELECT id, email, display_name FROM users WHERE id = :user_id
    """)
    user = db.execute(user_query, {"user_id": user_id}).fetchone()

    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    # Convert hours to seconds
    bonus_seconds = int(request.bonus_hours * 3600)

    # Update user subscription
    update_query = text("""
        UPDATE user_subscriptions
        SET bonus_credits_seconds = bonus_credits_seconds + :bonus_seconds
        WHERE user_id = :user_id
        RETURNING user_id, bonus_credits_seconds
    """)

    result = db.execute(update_query, {
        "user_id": user_id,
        "bonus_seconds": bonus_seconds
    }).fetchone()

    if not result:
        raise HTTPException(status_code=404, detail=f"User {user_id} has no subscription")

    # Create quota transaction
    transaction_query = text("""
        INSERT INTO quota_transactions (
            user_id, transaction_type, amount_seconds, quota_type,
            description, metadata, created_at
        ) VALUES (
            :user_id, 'manual_grant', :amount_seconds, 'bonus',
            :description, :metadata, NOW()
        )
        RETURNING id
    """)

    metadata = {
        "granted_by_admin_id": admin.id,
        "granted_by_admin_email": admin.email,
        "reason": request.reason
    }

    db.execute(transaction_query, {
        "user_id": user_id,
        "amount_seconds": bonus_seconds,
        "description": f"Admin grant: {request.reason}",
        "metadata": json.dumps(metadata)
    })

    # Create audit log entry
    audit_query = text("""
        INSERT INTO admin_audit_log (
            admin_id, action, target_user_id, details, created_at
        ) VALUES (
            :admin_id, 'grant_credits', :target_user_id, :details, NOW()
        )
    """)

    audit_details = {
        "bonus_hours": request.bonus_hours,
        "bonus_seconds": bonus_seconds,
        "reason": request.reason,
        "new_total_seconds": result[1]
    }

    db.execute(audit_query, {
        "admin_id": admin.id,
        "target_user_id": user_id,
        "details": json.dumps(audit_details)
    })

    db.commit()

    return {
        "message": f"Granted {request.bonus_hours} hours to user {user[1]}",
        "user_id": user_id,
        "user_email": user[1],
        "bonus_hours_granted": request.bonus_hours,
        "new_total_bonus_hours": round(result[1] / 3600, 2),
        "reason": request.reason
    }

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
