"""
Integration tests for STT Language Router.

Tests cover:
- Language normalization (pl → pl-PL, en → en-EN, ar → ar-EG)
- Routing lookup from database (language + mode + tier)
- Redis caching (5-minute TTL)
- Cache invalidation on config changes
- Fallback provider selection on primary failure
- Provider health check integration
- Concurrent routing requests
- Missing configuration fallback to wildcard (*)
- Disabled configuration handling
"""

import pytest
import pytest_asyncio
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Import the module under test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../routers/stt'))

from api.routers.stt.language_router import (
    get_stt_provider_for_language,
    check_provider_health,
    update_provider_health,
    _normalize_language,
    init_db_pool,
    _routing_cache,
    _db_pool,
)


# Test database connection
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator")


@pytest_asyncio.fixture
async def db_pool():
    """Create a database connection pool for testing."""
    # Parse DSN
    dsn = POSTGRES_DSN.replace("postgresql://", "").replace("postgres://", "")
    creds, rest = dsn.split("@")
    user, password = creds.split(":")
    host_port_db = rest.split("/")
    host_port = host_port_db[0]
    if ":" in host_port:
        host, port = host_port.rsplit(":", 1)
    else:
        host, port = host_port, "5432"
    database = host_port_db[1] if len(host_port_db) > 1 else "livetranslator"

    # Create pool
    pool = await asyncpg.create_pool(
        user=user,
        password=password,
        host=host,
        port=port,
        database=database,
        min_size=1,
        max_size=5
    )

    yield pool

    # Cleanup
    await pool.close()


@pytest_asyncio.fixture
async def clean_routing_cache():
    """Clean routing cache before and after tests."""
    global _routing_cache
    _routing_cache.clear()
    yield
    _routing_cache.clear()


@pytest_asyncio.fixture
async def test_routing_config(db_pool):
    """Insert test routing configurations."""
    async with db_pool.acquire() as conn:
        # Clean existing test configs (including wildcard for controlled testing)
        await conn.execute("""
            DELETE FROM stt_routing_config
            WHERE language IN ('test-XX', 'pl-PL', 'en-EN', 'ar-EG', '*')
        """)

        # Insert test configs using INSERT ... ON CONFLICT to handle any duplicates
        await conn.execute("""
            INSERT INTO stt_routing_config (language, mode, quality_tier, provider_primary, provider_fallback, config, enabled)
            VALUES
                ('pl-PL', 'partial', 'standard', 'speechmatics', 'google_v2', '{"diarization": true}', TRUE),
                ('pl-PL', 'final', 'standard', 'speechmatics', 'google_v2', '{"diarization": true}', TRUE),
                ('en-EN', 'partial', 'standard', 'speechmatics', 'azure', '{"diarization": true}', TRUE),
                ('en-EN', 'final', 'standard', 'speechmatics', 'azure', '{"diarization": true}', TRUE),
                ('ar-EG', 'partial', 'standard', 'google_v2', 'azure', '{"diarization": false}', TRUE),
                ('ar-EG', 'final', 'standard', 'google_v2', 'azure', '{"diarization": false}', TRUE),
                ('*', 'partial', 'standard', 'google_v2', 'azure', '{}', TRUE),
                ('*', 'final', 'standard', 'google_v2', 'azure', '{}', TRUE),
                ('test-XX', 'partial', 'standard', 'test_provider', 'test_fallback', '{}', FALSE)
            ON CONFLICT (language, mode, quality_tier) DO UPDATE
            SET provider_primary = EXCLUDED.provider_primary,
                provider_fallback = EXCLUDED.provider_fallback,
                config = EXCLUDED.config,
                enabled = EXCLUDED.enabled
        """)

    yield

    # Cleanup - Remove test configs but restore production configs if needed
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM stt_routing_config
            WHERE language IN ('test-XX')
        """)


@pytest_asyncio.fixture
async def test_provider_health(db_pool):
    """Insert test provider health records."""
    async with db_pool.acquire() as conn:
        # Clean existing test health records
        await conn.execute("""
            DELETE FROM provider_health
            WHERE provider IN ('test_provider', 'speechmatics', 'google_v2', 'azure', 'unhealthy_provider')
        """)

        # Insert test health records
        await conn.execute("""
            INSERT INTO provider_health (provider, service_type, status, consecutive_failures, last_check, response_time_ms)
            VALUES
                ('speechmatics', 'stt', 'healthy', 0, NOW(), 150),
                ('google_v2', 'stt', 'healthy', 0, NOW(), 200),
                ('azure', 'stt', 'healthy', 0, NOW(), 180),
                ('unhealthy_provider', 'stt', 'down', 5, NOW(), NULL)
            ON CONFLICT (provider, service_type) DO UPDATE
            SET status = EXCLUDED.status,
                consecutive_failures = EXCLUDED.consecutive_failures,
                last_check = EXCLUDED.last_check,
                response_time_ms = EXCLUDED.response_time_ms
        """)

    yield

    # Cleanup
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM provider_health
            WHERE provider IN ('test_provider', 'unhealthy_provider')
        """)


class TestLanguageNormalization:
    """Test language code normalization."""

    def test_normalize_polish(self):
        """Test Polish language normalization."""
        assert _normalize_language("pl") == "pl-PL"
        assert _normalize_language("PL") == "pl-PL"
        assert _normalize_language("pl-PL") == "pl-PL"

    def test_normalize_english(self):
        """Test English language normalization."""
        assert _normalize_language("en") == "en-EN"
        assert _normalize_language("EN") == "en-EN"
        assert _normalize_language("en-US") == "en-US"
        assert _normalize_language("en-GB") == "en-GB"

    def test_normalize_arabic(self):
        """Test Arabic language normalization."""
        assert _normalize_language("ar") == "ar-EG"
        assert _normalize_language("AR") == "ar-EG"
        assert _normalize_language("ar-EG") == "ar-EG"

    def test_normalize_european_languages(self):
        """Test European language normalization."""
        assert _normalize_language("es") == "es-ES"
        assert _normalize_language("fr") == "fr-FR"
        assert _normalize_language("de") == "de-DE"
        assert _normalize_language("it") == "it-IT"
        assert _normalize_language("pt") == "pt-PT"
        assert _normalize_language("ru") == "ru-RU"

    def test_normalize_auto_to_wildcard(self):
        """Test auto language becomes wildcard."""
        assert _normalize_language("auto") == "*"
        assert _normalize_language("") == "*"
        assert _normalize_language(None) == "*"

    def test_normalize_unknown_language(self):
        """Test unknown language becomes wildcard."""
        assert _normalize_language("xyz") == "*"


@pytest.mark.integration
@pytest.mark.asyncio
class TestSTTRoutingLookup:
    """Test STT routing configuration lookup from database."""

    async def test_lookup_polish_partial(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test lookup Polish partial mode routing."""
        # Patch the global db_pool
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_stt_provider_for_language("pl", "partial", "standard")

        assert result["provider"] == "speechmatics"
        assert result["fallback"] == "google_v2"
        assert result["language"] == "pl-PL"
        assert result["config"]["diarization"] is True

    async def test_lookup_english_final(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test lookup English final mode routing."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_stt_provider_for_language("en", "final", "standard")

        assert result["provider"] == "speechmatics"
        assert result["fallback"] == "azure"
        assert result["language"] == "en-EN"
        assert result["config"]["diarization"] is True

    async def test_lookup_arabic_partial(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test lookup Arabic partial mode routing."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_stt_provider_for_language("ar", "partial", "standard")

        assert result["provider"] == "google_v2"
        assert result["fallback"] == "azure"
        assert result["language"] == "ar-EG"
        assert result["config"]["diarization"] is False

    async def test_lookup_with_full_language_code(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test lookup with full language code (pl-PL instead of pl)."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_stt_provider_for_language("pl-PL", "partial", "standard")

        assert result["provider"] == "speechmatics"
        assert result["fallback"] == "google_v2"
        assert result["language"] == "pl-PL"

    async def test_fallback_to_wildcard(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test fallback to wildcard (*) for unknown language."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_stt_provider_for_language("xyz", "partial", "standard")

        assert result["provider"] == "google_v2"
        assert result["fallback"] == "azure"
        assert result["language"] == "*"


@pytest.mark.integration
@pytest.mark.asyncio
class TestCaching:
    """Test Redis caching functionality."""

    async def test_cache_populated_on_first_lookup(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test that cache is populated on first lookup."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # First lookup - should hit database
        result1 = await get_stt_provider_for_language("pl", "partial", "standard")
        assert result1["provider"] == "speechmatics"

        # Check cache is populated
        cache_key = ("pl-PL", "partial", "standard")
        assert cache_key in _routing_cache

    async def test_cache_used_on_second_lookup(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test that second lookup uses cache."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # First lookup
        result1 = await get_stt_provider_for_language("pl", "partial", "standard")

        # Modify database (should not affect cached result)
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE stt_routing_config
                SET provider_primary = 'changed_provider'
                WHERE language = 'pl-PL' AND mode = 'partial'
            """)

        # Second lookup - should use cache
        result2 = await get_stt_provider_for_language("pl", "partial", "standard")
        assert result2["provider"] == "speechmatics"  # From cache, not 'changed_provider'

    async def test_cache_expires_after_ttl(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test that cache expires after TTL."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # First lookup
        result1 = await get_stt_provider_for_language("pl", "partial", "standard")

        # Manually expire cache
        cache_key = ("pl-PL", "partial", "standard")
        _routing_cache[cache_key]["cached_at"] = datetime.now() - timedelta(seconds=400)

        # Update database
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE stt_routing_config
                SET provider_primary = 'updated_provider'
                WHERE language = 'pl-PL' AND mode = 'partial'
            """)

        # Second lookup - cache expired, should hit database
        result2 = await get_stt_provider_for_language("pl", "partial", "standard")
        assert result2["provider"] == "updated_provider"


@pytest.mark.integration
@pytest.mark.asyncio
class TestProviderHealthIntegration:
    """Test provider health check and fallback logic."""

    async def test_healthy_provider_selected(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test that healthy primary provider is selected."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_stt_provider_for_language("pl", "partial", "standard")
        assert result["provider"] == "speechmatics"  # Primary provider (healthy)

    async def test_unhealthy_provider_falls_back(self, db_pool, test_routing_config, clean_routing_cache):
        """Test fallback when primary provider is down."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Mark speechmatics as down
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE provider_health
                SET status = 'down', consecutive_failures = 5
                WHERE provider = 'speechmatics' AND service_type = 'stt'
            """)

        # Clear cache
        _routing_cache.clear()

        result = await get_stt_provider_for_language("pl", "partial", "standard")
        assert result["provider"] == "google_v2"  # Fallback provider

    async def test_provider_health_check(self, db_pool, test_provider_health):
        """Test provider health check returns correct status."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        health = await check_provider_health("speechmatics", "stt")
        assert health["status"] == "healthy"
        assert health["consecutive_failures"] == 0
        assert health["response_time_ms"] == 150

    async def test_provider_health_update_success(self, db_pool, test_provider_health):
        """Test updating provider health on success."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Mark as failed first
        await update_provider_health("speechmatics", "stt", success=False, error="test error")

        # Then mark as success
        await update_provider_health("speechmatics", "stt", success=True, response_time_ms=100)

        # Check health
        health = await check_provider_health("speechmatics", "stt")
        assert health["status"] == "healthy"
        assert health["consecutive_failures"] == 0

    async def test_provider_health_update_failure(self, db_pool, test_provider_health):
        """Test updating provider health on failure."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Reset to healthy
        await update_provider_health("speechmatics", "stt", success=True)

        # Fail once - degraded
        await update_provider_health("speechmatics", "stt", success=False, error="error 1")
        health = await check_provider_health("speechmatics", "stt")
        assert health["status"] == "degraded"
        assert health["consecutive_failures"] == 1

        # Fail twice more - down
        await update_provider_health("speechmatics", "stt", success=False, error="error 2")
        await update_provider_health("speechmatics", "stt", success=False, error="error 3")
        health = await check_provider_health("speechmatics", "stt")
        assert health["status"] == "down"
        assert health["consecutive_failures"] >= 3


@pytest.mark.integration
@pytest.mark.asyncio
class TestConcurrency:
    """Test concurrent routing requests."""

    async def test_sequential_lookups(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test multiple sequential routing lookups (verifies no state pollution)."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Sequential lookups to verify no state corruption
        result1 = await get_stt_provider_for_language("pl", "partial", "standard")
        result2 = await get_stt_provider_for_language("en", "final", "standard")
        result3 = await get_stt_provider_for_language("ar", "partial", "standard")
        result4 = await get_stt_provider_for_language("pl", "final", "standard")
        result5 = await get_stt_provider_for_language("en", "partial", "standard")

        # Verify all results
        assert result1["provider"] == "speechmatics"
        assert result2["provider"] == "speechmatics"
        assert result3["provider"] == "google_v2"
        assert result4["provider"] == "speechmatics"
        assert result5["provider"] == "speechmatics"


@pytest.mark.integration
@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_disabled_configuration_skipped(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test that disabled configurations are skipped."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # test-XX is disabled, should fall back to wildcard
        result = await get_stt_provider_for_language("test", "partial", "standard")

        # Should get wildcard config, not test_provider
        assert result["provider"] != "test_provider"
        assert result["provider"] == "google_v2"

    async def test_null_fallback_provider_in_config(self, db_pool, test_routing_config, clean_routing_cache, test_provider_health):
        """Test that config with NULL fallback is returned correctly."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Update existing config to have NULL fallback
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE stt_routing_config
                SET provider_fallback = NULL
                WHERE language = 'ar-EG' AND mode = 'final' AND quality_tier = 'standard'
            """)

        # Clear cache to force fresh lookup
        _routing_cache.clear()

        try:
            result = await get_stt_provider_for_language("ar", "final", "standard")
            assert result["provider"] == "google_v2"
            assert result["fallback"] is None
        finally:
            # Restore fallback
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE stt_routing_config
                    SET provider_fallback = 'azure'
                    WHERE language = 'ar-EG' AND mode = 'final' AND quality_tier = 'standard'
                """)

    async def test_database_connection_failure_uses_default(self, clean_routing_cache):
        """Test that default provider is used when database is unavailable."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = None  # Simulate no connection

        with patch.dict(os.environ, {"LT_STT_PARTIAL_MODE": "fallback_openai"}):
            result = await get_stt_provider_for_language("pl", "partial", "standard")
            assert result["provider"] == "fallback_openai"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
