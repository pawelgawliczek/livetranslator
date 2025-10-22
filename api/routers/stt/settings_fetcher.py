"""
STT Settings Fetcher
Fetches STT provider settings from database (room-specific or global defaults)
with caching to minimize database queries.
Supports instant cache invalidation via Redis pub/sub.
"""
import os
import asyncio
from datetime import datetime, timedelta
try:
    import asyncpg
except ImportError:
    asyncpg = None
    print("[Settings] Warning: asyncpg not installed, using psycopg2 instead")
    import psycopg2

# Configuration
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://livetranslator:changeme@postgres:5432/livetranslator")
CACHE_TTL_SECONDS = 300  # 5 minutes cache (will be invalidated instantly via Redis)
CACHE_CLEAR_CHANNEL = "stt_cache_clear"

# In-memory cache
_settings_cache = {}  # room_code -> {partial, final, cached_at}
_global_cache = None  # Global defaults cache
_db_pool = None


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
                host, port = host_port_db[0].rsplit(":", 1) if ":" in host_port_db[0] else (host_port_db[0], "5432")
                database = host_port_db[1] if len(host_port_db) > 1 else "livetranslator"

                _db_pool = await asyncpg.create_pool(
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    database=database,
                    min_size=1,
                    max_size=3
                )
                print(f"[Settings] Database pool initialized")
        except Exception as e:
            print(f"[Settings] Failed to initialize database pool: {e}")
            _db_pool = None


def init_db_sync():
    """Initialize database connection (synchronous fallback)."""
    # For sync connections, we'll just validate the DSN
    try:
        # Convert to psycopg2 DSN
        dsn = POSTGRES_DSN.replace("postgresql+asyncpg://", "postgresql://")
        return dsn
    except Exception as e:
        print(f"[Settings] Failed to initialize sync database: {e}")
        return None


async def get_global_stt_defaults():
    """Fetch global STT default settings from system_settings table."""
    global _global_cache

    # Check cache
    if _global_cache and (datetime.now() - _global_cache["cached_at"]).seconds < CACHE_TTL_SECONDS:
        return _global_cache["partial"], _global_cache["final"]

    # Initialize pool if needed
    if _db_pool is None:
        await init_db_pool()

    # Fallback to environment variables if no database access
    default_partial = os.getenv("LT_STT_PARTIAL_MODE", "openai_chunked")
    default_final = os.getenv("LT_STT_FINAL_MODE", "openai")

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                # Fetch global defaults from system_settings
                partial_row = await conn.fetchrow(
                    "SELECT value FROM system_settings WHERE key = 'stt_partial_provider_default'"
                )
                final_row = await conn.fetchrow(
                    "SELECT value FROM system_settings WHERE key = 'stt_final_provider_default'"
                )

                if partial_row:
                    default_partial = partial_row["value"]
                if final_row:
                    default_final = final_row["value"]

                print(f"[Settings] Global defaults: partial={default_partial}, final={default_final}")
        except Exception as e:
            print(f"[Settings] Failed to fetch global defaults: {e}")

    # Cache result
    _global_cache = {
        "partial": default_partial,
        "final": default_final,
        "cached_at": datetime.now()
    }

    return default_partial, default_final


async def get_room_stt_settings(room_code: str):
    """
    Fetch STT settings for a specific room.
    Returns: (partial_provider, final_provider)
    - Returns room-specific settings if set
    - Falls back to global defaults if room settings are NULL
    """
    # Check cache
    if room_code in _settings_cache:
        cache_entry = _settings_cache[room_code]
        if (datetime.now() - cache_entry["cached_at"]).seconds < CACHE_TTL_SECONDS:
            return cache_entry["partial"], cache_entry["final"]

    # Initialize pool if needed
    if _db_pool is None:
        await init_db_pool()

    # Get global defaults first
    default_partial, default_final = await get_global_stt_defaults()

    # Try to fetch room-specific overrides
    partial_provider = default_partial
    final_provider = default_final

    if _db_pool:
        try:
            async with _db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT stt_partial_provider, stt_final_provider FROM rooms WHERE code = $1",
                    room_code
                )

                if row:
                    # Use room-specific settings if not NULL
                    if row["stt_partial_provider"]:
                        partial_provider = row["stt_partial_provider"]
                    if row["stt_final_provider"]:
                        final_provider = row["stt_final_provider"]

                    print(f"[Settings] Room {room_code}: partial={partial_provider}, final={final_provider}")
        except Exception as e:
            print(f"[Settings] Failed to fetch room settings for {room_code}: {e}")

    # Cache result
    _settings_cache[room_code] = {
        "partial": partial_provider,
        "final": final_provider,
        "cached_at": datetime.now()
    }

    return partial_provider, final_provider


def clear_cache(room_code: str = None):
    """Clear settings cache for a specific room or all rooms."""
    global _settings_cache, _global_cache
    if room_code:
        _settings_cache.pop(room_code, None)
        print(f"[Settings] Cache cleared for room {room_code}")
    else:
        _settings_cache.clear()
        _global_cache = None
        print(f"[Settings] All caches cleared")
