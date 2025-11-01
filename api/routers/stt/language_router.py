"""
Language-Based STT Provider Router
Replaces settings_fetcher.py with intelligent language-aware routing

This module provides language-based provider selection for STT services:
- Routes based on (language, mode, quality_tier) instead of per-room configuration
- Supports automatic fallback on provider health issues
- Caches routing decisions in Redis (5-minute TTL)
- Integrates with provider health monitoring
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple
import json

try:
    import asyncpg
except ImportError:
    asyncpg = None
    print("[LanguageRouter] Warning: asyncpg not installed, using psycopg2 instead")
    import psycopg2

# Configuration
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://lt_user:changeme@postgres:5432/livetranslator")
CACHE_TTL_SECONDS = 300  # 5 minutes cache (will be invalidated instantly via Redis)
MULTI_SPEAKER_CACHE_TTL_SECONDS = 60  # 60 seconds cache for multi-speaker mode checks
CACHE_CLEAR_CHANNEL = "routing_cache_clear"
MULTI_SPEAKER_STT_ENABLED = os.getenv("MULTI_SPEAKER_STT_ENABLED", "true").lower() == "true"

# In-memory cache
_routing_cache = {}  # (language, mode, quality_tier) -> {provider, fallback, config, cached_at}
_multi_speaker_cache = {}  # room_code -> {is_multi_speaker, room_id, speakers, cached_at}
_db_pool = None
_multi_speaker_query_locks = {}  # room_code -> asyncio.Lock (prevent duplicate queries)


async def init_db_pool():
    """Initialize database connection pool (async)."""
    global _db_pool
    if _db_pool is None and asyncpg:
        try:
            # Convert psycopg2 DSN to asyncpg DSN if needed
            dsn = POSTGRES_DSN.replace("postgresql://", "").replace("postgres://", "")
            if "@" in dsn:
                # Format: user:pass@host:port/db
                creds, rest = dsn.split("@")
                user, password = creds.split(":")
                host_port_db = rest.split("/")
                host_port = host_port_db[0]
                if ":" in host_port:
                    host, port = host_port.rsplit(":", 1)
                else:
                    host, port = host_port, "5432"
                database = host_port_db[1] if len(host_port_db) > 1 else "livetranslator"

                _db_pool = await asyncpg.create_pool(
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    database=database,
                    min_size=1,
                    max_size=5
                )
                print(f"[LanguageRouter] Database pool initialized")
        except Exception as e:
            print(f"[LanguageRouter] Failed to initialize database pool: {e}")
            _db_pool = None


def _normalize_language(lang: str) -> str:
    """
    Normalize language code for routing lookup.

    Examples:
    - "pl" -> "pl-PL"
    - "en" -> "en-US"
    - "ar" -> "ar-EG"
    - "pl-PL" -> "pl-PL"
    - "auto" -> "*" (fallback)
    """
    if not lang or lang == "auto":
        return "*"

    # Already in correct format (e.g., pl-PL, en-US)
    if "-" in lang and len(lang) == 5:
        return lang

    # Common mappings
    mappings = {
        # European languages
        "pl": "pl-PL",
        "en": "en-EN",
        "es": "es-ES",
        "fr": "fr-FR",
        "de": "de-DE",
        "it": "it-IT",
        "pt": "pt-PT",
        "ru": "ru-RU",

        # Asian languages
        "ar": "ar-EG",
        "zh": "zh-CN",
        "ja": "ja-JP",
        "ko": "ko-KR",
        "hi": "hi-IN",
        "th": "th-TH",
        "vi": "vi-VN",

        # Additional variants
        "he": "he-IL",
        "tr": "tr-TR",
        "id": "id-ID"
    }

    return mappings.get(lang.lower(), "*")


# Public API for normalizing language codes
normalize_language_code = _normalize_language


async def check_provider_health(provider: str, service_type: str) -> Dict[str, Any]:
    """
    Check health status of a provider.

    Returns:
    {
        'provider': 'speechmatics',
        'status': 'healthy' | 'degraded' | 'down',
        'consecutive_failures': 0,
        'last_check': datetime,
        'response_time_ms': 150
    }
    """
    if _db_pool is None:
        await init_db_pool()

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT status, consecutive_failures, last_check, response_time_ms
                    FROM provider_health
                    WHERE provider = $1 AND service_type = $2
                    """,
                    provider, service_type
                )

                if row:
                    return {
                        'provider': provider,
                        'status': row['status'],
                        'consecutive_failures': row['consecutive_failures'],
                        'last_check': row['last_check'],
                        'response_time_ms': row['response_time_ms']
                    }
        except Exception as e:
            print(f"[LanguageRouter] Failed to check provider health for {provider}: {e}")

    # Default to healthy if we can't check
    return {
        'provider': provider,
        'status': 'healthy',
        'consecutive_failures': 0,
        'last_check': datetime.now(),
        'response_time_ms': None
    }


async def update_provider_health(
    provider: str,
    service_type: str,
    success: bool,
    response_time_ms: Optional[int] = None,
    error: Optional[str] = None
):
    """
    Update provider health status after an API call.

    Args:
        provider: Provider name (speechmatics, google_v2, etc.)
        service_type: 'stt' or 'mt'
        success: Whether the API call succeeded
        response_time_ms: Response time in milliseconds
        error: Error message if failed
    """
    if _db_pool is None:
        await init_db_pool()

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                if success:
                    # Reset consecutive failures on success
                    await conn.execute(
                        """
                        UPDATE provider_health
                        SET status = 'healthy',
                            consecutive_failures = 0,
                            last_check = NOW(),
                            last_success = NOW(),
                            response_time_ms = $3,
                            updated_at = NOW()
                        WHERE provider = $1 AND service_type = $2
                        """,
                        provider, service_type, response_time_ms
                    )
                else:
                    # Increment failures and update status
                    await conn.execute(
                        """
                        UPDATE provider_health
                        SET consecutive_failures = consecutive_failures + 1,
                            last_check = NOW(),
                            last_error = $3,
                            status = CASE
                                WHEN consecutive_failures + 1 >= 3 THEN 'down'
                                WHEN consecutive_failures + 1 >= 1 THEN 'degraded'
                                ELSE 'healthy'
                            END,
                            updated_at = NOW()
                        WHERE provider = $1 AND service_type = $2
                        """,
                        provider, service_type, error
                    )
                    print(f"[LanguageRouter] ⚠️ Provider {provider} ({service_type}) failed: {error}")
        except Exception as e:
            print(f"[LanguageRouter] Failed to update provider health: {e}")


async def check_multi_speaker_mode(room_code: str) -> Tuple[bool, Optional[int], Optional[Dict]]:
    """
    Check if a room is in multi-speaker mode with diarization enabled.

    Returns:
        (is_multi_speaker, room_db_id, speakers_dict)
        - is_multi_speaker: True if speakers_locked is enabled
        - room_db_id: Database ID of the room (for logging/metrics)
        - speakers_dict: {speaker_id: {display_name, language, color}, ...}

    Uses 60-second caching to reduce database load.
    """
    # Feature flag kill switch
    if not MULTI_SPEAKER_STT_ENABLED:
        return (False, None, None)

    # Check cache
    if room_code in _multi_speaker_cache:
        cache_entry = _multi_speaker_cache[room_code]
        age_seconds = (datetime.now() - cache_entry["cached_at"]).total_seconds()
        if age_seconds < MULTI_SPEAKER_CACHE_TTL_SECONDS:
            return (cache_entry["is_multi_speaker"], cache_entry["room_id"], cache_entry["speakers"])

    # Acquire lock to prevent duplicate queries for the same room
    if room_code not in _multi_speaker_query_locks:
        _multi_speaker_query_locks[room_code] = asyncio.Lock()

    async with _multi_speaker_query_locks[room_code]:
        # Double-check cache after acquiring lock (another coroutine may have fetched it)
        if room_code in _multi_speaker_cache:
            cache_entry = _multi_speaker_cache[room_code]
            age_seconds = (datetime.now() - cache_entry["cached_at"]).total_seconds()
            if age_seconds < MULTI_SPEAKER_CACHE_TTL_SECONDS:
                return (cache_entry["is_multi_speaker"], cache_entry["room_id"], cache_entry["speakers"])

        # Initialize pool if needed
        if _db_pool is None:
            await init_db_pool()

        # Graceful fallback on database errors
        if _db_pool is None:
            return (False, None, None)

        try:
            async with _db_pool.acquire() as conn:
                # Query room for multi-speaker mode (discovery or locked)
                room_row = await conn.fetchrow(
                    """
                    SELECT id, speakers_locked, discovery_mode
                    FROM rooms
                    WHERE code = $1
                    """,
                    room_code
                )

                # Check if multi-speaker mode is active:
                # - discovery_mode='enabled' → Need diarization to DETECT speakers
                # - speakers_locked=true → Need diarization to MAP to enrolled speakers
                if not room_row:
                    # Room not found
                    cache_result = {
                        "is_multi_speaker": False,
                        "room_id": None,
                        "speakers": None,
                        "cached_at": datetime.now()
                    }
                    _multi_speaker_cache[room_code] = cache_result
                    return (False, None, None)

                is_discovery = room_row['discovery_mode'] == 'enabled'
                is_locked = room_row['speakers_locked']

                if not is_discovery and not is_locked:
                    # Not a multi-speaker room
                    cache_result = {
                        "is_multi_speaker": False,
                        "room_id": room_row['id'],
                        "speakers": None,
                        "cached_at": datetime.now()
                    }
                    _multi_speaker_cache[room_code] = cache_result
                    return (False, room_row['id'], None)

                # Fetch enrolled speakers (may be empty during discovery)
                speaker_rows = await conn.fetch(
                    """
                    SELECT speaker_id, display_name, language, color
                    FROM room_speakers
                    WHERE room_id = $1
                    ORDER BY speaker_id ASC
                    """,
                    room_row['id']
                )

                if not speaker_rows:
                    # No speakers enrolled yet
                    if is_discovery:
                        # Discovery mode: Enable diarization to DETECT speakers
                        cache_result = {
                            "is_multi_speaker": True,
                            "room_id": room_row['id'],
                            "speakers": {},  # Empty dict - speakers will be detected
                            "cached_at": datetime.now()
                        }
                        _multi_speaker_cache[room_code] = cache_result
                        print(f"[LanguageRouter] ✅ Multi-speaker DISCOVERY mode for room {room_code}")
                        return (True, room_row['id'], {})
                    else:
                        # Locked but no speakers (error state)
                        cache_result = {
                            "is_multi_speaker": False,
                            "room_id": room_row['id'],
                            "speakers": None,
                            "cached_at": datetime.now()
                        }
                        _multi_speaker_cache[room_code] = cache_result
                        print(f"[LanguageRouter] ⚠️  Room {room_code} locked but no speakers enrolled")
                        return (False, room_row['id'], None)

                # Build speakers dictionary
                speakers_dict = {
                    row['speaker_id']: {
                        'display_name': row['display_name'],
                        'language': row['language'],
                        'color': row['color']
                    }
                    for row in speaker_rows
                }

                # Cache result
                cache_result = {
                    "is_multi_speaker": True,
                    "room_id": room_row['id'],
                    "speakers": speakers_dict,
                    "cached_at": datetime.now()
                }
                _multi_speaker_cache[room_code] = cache_result

                print(f"[LanguageRouter] ✅ Multi-speaker room {room_code}: {len(speakers_dict)} speakers, using Speechmatics diarization")
                return (True, room_row['id'], speakers_dict)

        except Exception as e:
            print(f"[LanguageRouter] Failed to check multi-speaker mode for room {room_code}: {e}")
            # Graceful fallback: return False to use standard routing
            return (False, None, None)


async def get_stt_provider_for_language(
    language: str,
    mode: str,
    quality_tier: str = 'standard',
    room_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get STT provider configuration for a specific language and mode.

    Args:
        language: Language code (pl-PL, ar-EG, en-US, auto, etc.)
        mode: 'partial' or 'final'
        quality_tier: 'standard' or 'budget'
        room_id: Optional room code for multi-speaker mode detection

    Returns:
    {
        'provider': 'speechmatics',
        'fallback': 'google_v2',
        'config': {
            'diarization': True,
            'max_delay': 1.5,
            'operating_point': 'enhanced'
        },
        'language': 'pl-PL',  # Normalized language code
        'multi_speaker_optimized': True,  # Only for multi-speaker rooms
        'room_id': 123,  # Database room ID (only for multi-speaker rooms)
        'speakers': {...}  # Speaker configuration (only for multi-speaker rooms)
    }
    """
    # Guard clause: If room_id is None, use standard path (zero changes)
    if room_id is None:
        # Standard path - existing logic unchanged
        return await _get_standard_provider(language, mode, quality_tier)

    # Check multi-speaker mode
    is_multi_speaker, room_db_id, speakers = await check_multi_speaker_mode(room_id)

    if not is_multi_speaker:
        # Room exists but not in multi-speaker mode - use standard path
        return await _get_standard_provider(language, mode, quality_tier)

    # Multi-speaker mode detected - route to Speechmatics with diarization
    # IMPORTANT: Use language detection during discovery to identify each speaker's language
    # During discovery (speakers not locked), use 'auto' for language detection
    # After locked, can use specific language if all speakers speak the same language
    is_discovery = len(speakers) == 0  # Empty speakers dict = discovery mode

    return {
        'provider': 'speechmatics',
        'fallback': None,  # Future: 'google_v2' with diarization support
        'config': {
            'diarization': 'speaker',
            'max_delay': 1.0,
            'operating_point': 'enhanced',
            'enable_language_detection': True  # Enable automatic language detection
        },
        # Use 'auto' for language detection during discovery
        'language': 'auto' if is_discovery else _normalize_language(language),
        'multi_speaker_optimized': True,
        'room_id': room_db_id,
        'speakers': speakers,
        'is_discovery': is_discovery
    }


async def _get_standard_provider(
    language: str,
    mode: str,
    quality_tier: str = 'standard'
) -> Dict[str, Any]:
    """
    Standard provider selection logic (original implementation).
    Separated for clean separation between standard and multi-speaker modes.
    """
    # Normalize language code
    normalized_lang = _normalize_language(language)

    # Check cache
    cache_key = (normalized_lang, mode, quality_tier)
    if cache_key in _routing_cache:
        cache_entry = _routing_cache[cache_key]
        if (datetime.now() - cache_entry["cached_at"]).seconds < CACHE_TTL_SECONDS:
            return cache_entry

    # Initialize pool if needed
    if _db_pool is None:
        await init_db_pool()

    # Default config (fallback to OpenAI if database unavailable)
    default_provider = os.getenv("LT_STT_PARTIAL_MODE", "openai") if mode == "partial" else os.getenv("LT_STT_FINAL_MODE", "openai")
    default_config = {
        'provider': default_provider,
        'fallback': 'openai',
        'config': {'diarization': False},
        'language': normalized_lang
    }

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                # Try exact language match first
                row = await conn.fetchrow(
                    """
                    SELECT provider_primary, provider_fallback, config
                    FROM stt_routing_config
                    WHERE language = $1 AND mode = $2 AND quality_tier = $3 AND enabled = TRUE
                    LIMIT 1
                    """,
                    normalized_lang, mode, quality_tier
                )

                # Fallback to wildcard if language not found
                if not row:
                    row = await conn.fetchrow(
                        """
                        SELECT provider_primary, provider_fallback, config
                        FROM stt_routing_config
                        WHERE language = '*' AND mode = $1 AND quality_tier = $2 AND enabled = TRUE
                        LIMIT 1
                        """,
                        mode, quality_tier
                    )

                if row:
                    # Check primary provider health
                    provider = row['provider_primary']
                    health = await check_provider_health(provider, 'stt')

                    # Use fallback if primary is down
                    if health['status'] == 'down' and row['provider_fallback']:
                        print(f"[LanguageRouter] ⚠️ Primary provider {provider} is down, using fallback {row['provider_fallback']}")
                        provider = row['provider_fallback']

                    # Parse config if it's a JSON string
                    config = row['config']
                    if isinstance(config, str):
                        config = json.loads(config)

                    result = {
                        'provider': provider,
                        'fallback': row['provider_fallback'],
                        'config': config,
                        'language': normalized_lang,
                        'cached_at': datetime.now()
                    }

                    # Cache result
                    _routing_cache[cache_key] = result

                    print(f"[LanguageRouter] 🎯 STT routing: lang={normalized_lang}, mode={mode}, tier={quality_tier} → {provider}")
                    return result

        except Exception as e:
            print(f"[LanguageRouter] Failed to fetch STT routing config: {e}")

    # Return default if database query failed
    print(f"[LanguageRouter] ⚠️ Using default STT provider: {default_provider}")
    return default_config


async def get_mt_provider_for_pair(
    src_lang: str,
    tgt_lang: str,
    quality_tier: str = 'standard'
) -> Dict[str, Any]:
    """
    Get MT provider configuration for a specific language pair.

    Args:
        src_lang: Source language code (en, pl, ar, etc.)
        tgt_lang: Target language code (en, pl, ar, etc.)
        quality_tier: 'standard' or 'budget'

    Returns:
    {
        'provider': 'deepl',
        'fallback': 'azure_translator',
        'config': {
            'use_context': True,
            'use_glossary': True
        },
        'src_lang': 'pl',
        'tgt_lang': 'en'
    }
    """
    # Normalize to simple language codes (pl, en, ar) not full codes (pl-PL)
    src_simple = src_lang.split("-")[0].lower() if src_lang else "*"
    tgt_simple = tgt_lang.split("-")[0].lower() if tgt_lang else "*"

    # Check cache
    cache_key = (src_simple, tgt_simple, quality_tier, 'mt')
    if cache_key in _routing_cache:
        cache_entry = _routing_cache[cache_key]
        if (datetime.now() - cache_entry["cached_at"]).seconds < CACHE_TTL_SECONDS:
            return cache_entry

    # Initialize pool if needed
    if _db_pool is None:
        await init_db_pool()

    # Default config (fallback to OpenAI if database unavailable)
    default_provider = os.getenv("LT_MT_MODE", "openai")
    default_config = {
        'provider': default_provider,
        'fallback': 'openai',
        'config': {},
        'src_lang': src_simple,
        'tgt_lang': tgt_simple
    }

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                # Try exact language pair match first
                row = await conn.fetchrow(
                    """
                    SELECT provider_primary, provider_fallback, config
                    FROM mt_routing_config
                    WHERE src_lang = $1 AND tgt_lang = $2 AND quality_tier = $3 AND enabled = TRUE
                    LIMIT 1
                    """,
                    src_simple, tgt_simple, quality_tier
                )

                # Fallback to wildcard matches (prioritize specific over wildcard)
                if not row:
                    row = await conn.fetchrow(
                        """
                        SELECT provider_primary, provider_fallback, config
                        FROM mt_routing_config
                        WHERE quality_tier = $3 AND enabled = TRUE
                          AND (
                              (src_lang = $1 AND tgt_lang = '*') OR
                              (src_lang = '*' AND tgt_lang = $2) OR
                              (src_lang = '*' AND tgt_lang = '*')
                          )
                        ORDER BY
                            CASE
                                WHEN src_lang = $1 AND tgt_lang = '*' THEN 1
                                WHEN src_lang = '*' AND tgt_lang = $2 THEN 2
                                ELSE 3
                            END
                        LIMIT 1
                        """,
                        src_simple, tgt_simple, quality_tier
                    )

                if row:
                    # Check primary provider health
                    provider = row['provider_primary']
                    health = await check_provider_health(provider, 'mt')

                    # Use fallback if primary is down
                    if health['status'] == 'down' and row['provider_fallback']:
                        print(f"[LanguageRouter] ⚠️ Primary MT provider {provider} is down, using fallback {row['provider_fallback']}")
                        provider = row['provider_fallback']

                    result = {
                        'provider': provider,
                        'fallback': row['provider_fallback'],
                        'config': row['config'],
                        'src_lang': src_simple,
                        'tgt_lang': tgt_simple,
                        'cached_at': datetime.now()
                    }

                    # Cache result
                    _routing_cache[cache_key] = result

                    print(f"[LanguageRouter] 🎯 MT routing: {src_simple}→{tgt_simple}, tier={quality_tier} → {provider}")
                    return result

        except Exception as e:
            print(f"[LanguageRouter] Failed to fetch MT routing config: {e}")

    # Return default if database query failed
    print(f"[LanguageRouter] ⚠️ Using default MT provider: {default_provider}")
    return default_config


def clear_cache(language: str = None, service_type: str = None, room_code: str = None):
    """
    Clear routing cache for specific language or all languages.

    Args:
        language: Specific language to clear (None = clear all)
        service_type: 'stt' or 'mt' or 'multi_speaker' (None = clear all)
        room_code: Specific room code for multi-speaker cache (None = clear all rooms)
    """
    global _routing_cache, _multi_speaker_cache

    # Handle multi-speaker cache clearing
    if service_type == "multi_speaker" and room_code:
        if room_code in _multi_speaker_cache:
            del _multi_speaker_cache[room_code]
            print(f"[LanguageRouter] 🔄 Cleared multi-speaker cache for room {room_code}")
        return

    if language is None and service_type is None:
        # Clear all caches
        _routing_cache.clear()
        _multi_speaker_cache.clear()
        print(f"[LanguageRouter] 🔄 All routing caches cleared (including multi-speaker)")
    else:
        # Clear specific entries
        keys_to_remove = [
            key for key in _routing_cache.keys()
            if (language is None or key[0] == language) and
               (service_type is None or ('mt' if len(key) == 4 else 'stt') == service_type)
        ]
        for key in keys_to_remove:
            del _routing_cache[key]
        print(f"[LanguageRouter] 🔄 Cleared {len(keys_to_remove)} routing cache entries (lang={language}, type={service_type})")


async def cache_invalidation_listener():
    """
    Listen for cache invalidation messages from Redis.
    Should be run as background task.
    """
    try:
        import redis.asyncio as redis
    except ImportError:
        import redis
        print("[LanguageRouter] Warning: redis.asyncio not available, using sync redis")

    try:
        REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
        r = redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(CACHE_CLEAR_CHANNEL)

        print(f"[LanguageRouter] Cache invalidation listener started on {CACHE_CLEAR_CHANNEL}")

        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue

            try:
                data = json.loads(msg["data"]) if isinstance(msg["data"], str) else msg["data"]
                language = data.get("language") if isinstance(data, dict) else None
                service_type = data.get("service_type") if isinstance(data, dict) else None
                cache_type = data.get("type") if isinstance(data, dict) else None
                room_code = data.get("room_code") if isinstance(data, dict) else None

                # Handle multi-speaker cache invalidation
                if cache_type == "multi_speaker" and room_code:
                    clear_cache(service_type="multi_speaker", room_code=room_code)
                else:
                    clear_cache(language, service_type)
            except Exception as e:
                print(f"[LanguageRouter] Cache clear error: {e}")
    except Exception as e:
        print(f"[LanguageRouter] Cache invalidation listener failed: {e}")


# Backwards compatibility alias (for gradual migration)
get_room_stt_settings = get_stt_provider_for_language
