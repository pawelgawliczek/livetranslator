"""
Language-Based TTS Provider Router
Follows same pattern as STT/MT language routing

Selects optimal TTS provider based on:
- Target language
- Quality tier (standard/budget)
- Provider health status
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import json

try:
    import asyncpg
except ImportError:
    asyncpg = None
    print("[TTS LanguageRouter] Warning: asyncpg not installed")

# Configuration
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://lt_user:changeme@postgres:5432/livetranslator")
CACHE_TTL_SECONDS = 300  # 5 minutes cache
CACHE_CLEAR_CHANNEL = "routing_cache_clear"

# In-memory cache
_routing_cache = {}  # (language, quality_tier) -> {provider, fallback, config, cached_at}
_db_pool = None


async def init_db_pool():
    """Initialize database connection pool (async)."""
    global _db_pool
    if _db_pool is None and asyncpg:
        try:
            # Parse DSN
            dsn = POSTGRES_DSN.replace("postgresql://", "").replace("postgres://", "")
            if "@" in dsn:
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
                print(f"[TTS LanguageRouter] Database pool initialized")
        except Exception as e:
            print(f"[TTS LanguageRouter] Failed to initialize database pool: {e}")
            _db_pool = None


async def check_provider_health(provider: str) -> Dict[str, Any]:
    """
    Check health status of a TTS provider.

    Returns:
    {
        'provider': 'google_tts',
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
                    WHERE provider = $1 AND service_type = 'tts'
                    """,
                    provider
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
            print(f"[TTS LanguageRouter] Failed to check provider health for {provider}: {e}")

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
    success: bool,
    response_time_ms: Optional[int] = None,
    error: Optional[str] = None
):
    """
    Update TTS provider health status after synthesis.

    Args:
        provider: Provider name (google_tts, azure_tts, etc.)
        success: Whether the synthesis succeeded
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
                            response_time_ms = $2,
                            updated_at = NOW()
                        WHERE provider = $1 AND service_type = 'tts'
                        """,
                        provider, response_time_ms
                    )
                else:
                    # Increment failures and update status
                    await conn.execute(
                        """
                        UPDATE provider_health
                        SET consecutive_failures = consecutive_failures + 1,
                            last_check = NOW(),
                            last_error = $2,
                            status = CASE
                                WHEN consecutive_failures + 1 >= 3 THEN 'down'
                                WHEN consecutive_failures + 1 >= 1 THEN 'degraded'
                                ELSE 'healthy'
                            END,
                            updated_at = NOW()
                        WHERE provider = $1 AND service_type = 'tts'
                        """,
                        provider, error
                    )
                    print(f"[TTS LanguageRouter] Provider {provider} failed: {error}")
        except Exception as e:
            print(f"[TTS LanguageRouter] Failed to update provider health: {e}")


def normalize_language(lang: str) -> str:
    """
    Normalize language code to simple format (en, pl, ar).

    Examples:
    - "en-US" -> "en"
    - "pl-PL" -> "pl"
    - "ar-EG" -> "ar"
    - "en" -> "en"
    """
    if not lang:
        return "*"

    # Strip locale suffix
    return lang.split("-")[0].lower()


async def get_tts_provider_for_language(
    language: str,
    quality_tier: str = 'standard',
    user_preferences: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Get TTS provider configuration for a specific language.

    Args:
        language: Language code (en, pl, ar, etc.)
        quality_tier: 'standard' or 'budget'
        user_preferences: Optional user voice preferences {en: "en-US-Wavenet-D", ...}

    Returns:
    {
        'provider': 'google_tts',
        'fallback': 'azure_tts',
        'config': {
            'voice_id': 'en-US-Neural2-D',
            'pitch': 0.0,
            'speaking_rate': 1.0,
            'voice_gender': 'MALE'
        },
        'language': 'en'
    }
    """
    # Normalize language code
    normalized_lang = normalize_language(language)

    # Check cache
    cache_key = (normalized_lang, quality_tier)
    if cache_key in _routing_cache:
        cache_entry = _routing_cache[cache_key]
        if (datetime.now() - cache_entry["cached_at"]).seconds < CACHE_TTL_SECONDS:
            result = cache_entry.copy()

            # Override voice_id if user has preference for this language
            if user_preferences and normalized_lang in user_preferences:
                result["config"] = result["config"].copy()
                result["config"]["voice_id"] = user_preferences[normalized_lang]
                print(f"[TTS LanguageRouter] Using user voice preference: {user_preferences[normalized_lang]}")

            return result

    # Initialize pool if needed
    if _db_pool is None:
        await init_db_pool()

    # Default config (fallback to Google TTS if database unavailable)
    default_config = {
        'provider': 'google_tts',
        'fallback': 'azure_tts',
        'config': {
            'voice_id': 'en-US-Neural2-D',
            'pitch': 0.0,
            'speaking_rate': 1.0,
            'voice_gender': 'MALE'
        },
        'language': normalized_lang
    }

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                # Try exact language match first
                row = await conn.fetchrow(
                    """
                    SELECT provider_primary, provider_fallback, config
                    FROM tts_routing_config
                    WHERE language = $1 AND quality_tier = $2 AND enabled = TRUE
                    LIMIT 1
                    """,
                    normalized_lang, quality_tier
                )

                # Fallback to wildcard if language not found
                if not row:
                    row = await conn.fetchrow(
                        """
                        SELECT provider_primary, provider_fallback, config
                        FROM tts_routing_config
                        WHERE language = '*' AND quality_tier = $1 AND enabled = TRUE
                        LIMIT 1
                        """,
                        quality_tier
                    )

                if row:
                    # Check primary provider health
                    provider = row['provider_primary']
                    health = await check_provider_health(provider)

                    # Use fallback if primary is down
                    if health['status'] == 'down' and row['provider_fallback']:
                        print(f"[TTS LanguageRouter] Primary provider {provider} is down, using fallback {row['provider_fallback']}")
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

                    # Override voice_id if user has preference for this language
                    if user_preferences and normalized_lang in user_preferences:
                        result["config"] = result["config"].copy()
                        result["config"]["voice_id"] = user_preferences[normalized_lang]
                        print(f"[TTS LanguageRouter] Using user voice preference: {user_preferences[normalized_lang]}")

                    # Cache result
                    _routing_cache[cache_key] = result

                    print(f"[TTS LanguageRouter] TTS routing: lang={normalized_lang}, tier={quality_tier} -> {provider}")
                    return result

        except Exception as e:
            print(f"[TTS LanguageRouter] Failed to fetch TTS routing config: {e}")

    # Return default if database query failed
    print(f"[TTS LanguageRouter] Using default TTS provider: google_tts")
    return default_config


def clear_cache(language: str = None):
    """
    Clear routing cache for specific language or all languages.

    Args:
        language: Specific language to clear (None = clear all)
    """
    global _routing_cache

    if language is None:
        # Clear all caches
        _routing_cache.clear()
        print(f"[TTS LanguageRouter] All TTS routing caches cleared")
    else:
        # Clear specific entries
        keys_to_remove = [key for key in _routing_cache.keys() if key[0] == language]
        for key in keys_to_remove:
            del _routing_cache[key]
        print(f"[TTS LanguageRouter] Cleared {len(keys_to_remove)} TTS routing cache entries (lang={language})")


async def cache_invalidation_listener():
    """
    Listen for cache invalidation messages from Redis.
    Should be run as background task.
    """
    try:
        import redis.asyncio as redis
    except ImportError:
        print("[TTS LanguageRouter] Warning: redis.asyncio not available")
        return

    try:
        REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
        r = redis.from_url(REDIS_URL, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(CACHE_CLEAR_CHANNEL)

        print(f"[TTS LanguageRouter] Cache invalidation listener started on {CACHE_CLEAR_CHANNEL}")

        async for msg in pubsub.listen():
            if not msg or msg.get("type") != "message":
                continue

            try:
                data = json.loads(msg["data"]) if isinstance(msg["data"], str) else msg["data"]
                service_type = data.get("service_type") if isinstance(data, dict) else None

                # Only clear TTS cache if service_type is 'tts' or None (clear all)
                if service_type in [None, 'tts']:
                    language = data.get("language") if isinstance(data, dict) else None
                    clear_cache(language)
            except Exception as e:
                print(f"[TTS LanguageRouter] Cache clear error: {e}")
    except Exception as e:
        print(f"[TTS LanguageRouter] Cache invalidation listener failed: {e}")
