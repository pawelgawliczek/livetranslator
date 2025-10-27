"""
Integration tests for MT Language Router.

Tests cover:
- Language pair normalization (pl-PL → pl, en-US → en)
- Routing lookup from database (src_lang + tgt_lang + tier)
- Caching functionality (5-minute TTL)
- Provider health check integration
- Fallback logic (exact match, wildcard matches with priority)
- DeepL vs Google Translate selection
- European language pair optimization
- Edge cases and error handling
"""

import pytest
import pytest_asyncio
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from unittest.mock import patch

# Import the module under test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../routers/stt'))

from api.routers.stt.language_router import (
    get_mt_provider_for_pair,
    check_provider_health,
    update_provider_health,
    _routing_cache,
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
async def test_mt_routing_config(db_pool):
    """Insert test MT routing configurations."""
    async with db_pool.acquire() as conn:
        # Clean existing test configs
        await conn.execute("""
            DELETE FROM mt_routing_config
            WHERE (src_lang = 'test' OR tgt_lang = 'test')
               OR (src_lang = 'pl' AND tgt_lang = 'en')
               OR (src_lang = 'en' AND tgt_lang = 'pl')
               OR (src_lang = 'en' AND tgt_lang = 'ar')
               OR (src_lang = 'ar' AND tgt_lang = 'en')
               OR (src_lang = 'es' AND tgt_lang = 'en')
               OR (src_lang = '*' AND tgt_lang = '*')
        """)

        # Insert test configs
        await conn.execute("""
            INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config, enabled)
            VALUES
                ('pl', 'en', 'standard', 'deepl', 'google_translate', '{"use_context": true}', TRUE),
                ('en', 'pl', 'standard', 'deepl', 'google_translate', '{"use_context": true}', TRUE),
                ('en', 'ar', 'standard', 'google_translate', 'amazon_translate', '{}', TRUE),
                ('ar', 'en', 'standard', 'google_translate', 'amazon_translate', '{}', TRUE),
                ('es', 'en', 'standard', 'deepl', 'google_translate', '{}', TRUE),
                ('*', '*', 'standard', 'google_translate', 'amazon_translate', '{}', TRUE),
                ('*', '*', 'budget', 'amazon_translate', 'google_translate', '{}', TRUE),
                ('test', 'test', 'standard', 'test_provider', 'test_fallback', '{}', FALSE)
            ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE
            SET provider_primary = EXCLUDED.provider_primary,
                provider_fallback = EXCLUDED.provider_fallback,
                config = EXCLUDED.config,
                enabled = EXCLUDED.enabled
        """)

    yield

    # Cleanup
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM mt_routing_config
            WHERE src_lang = 'test' AND tgt_lang = 'test'
        """)


@pytest_asyncio.fixture
async def test_mt_provider_health(db_pool):
    """Insert test MT provider health records."""
    async with db_pool.acquire() as conn:
        # Insert test health records
        await conn.execute("""
            INSERT INTO provider_health (provider, service_type, status, consecutive_failures, last_check, response_time_ms)
            VALUES
                ('deepl', 'mt', 'healthy', 0, NOW(), 120),
                ('google_translate', 'mt', 'healthy', 0, NOW(), 150),
                ('amazon_translate', 'mt', 'healthy', 0, NOW(), 180),
                ('unhealthy_mt', 'mt', 'down', 5, NOW(), NULL)
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
            WHERE provider = 'unhealthy_mt' AND service_type = 'mt'
        """)


class TestLanguagePairNormalization:
    """Test language pair code normalization."""

    @pytest.mark.asyncio
    async def test_normalize_full_to_simple_codes(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that full language codes are normalized to simple codes."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # pl-PL → pl, en-US → en
        result = await get_mt_provider_for_pair("pl-PL", "en-US", "standard")

        assert result["src_lang"] == "pl"
        assert result["tgt_lang"] == "en"
        assert result["provider"] == "deepl"

    @pytest.mark.asyncio
    async def test_simple_codes_unchanged(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that simple language codes remain unchanged."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("pl", "en", "standard")

        assert result["src_lang"] == "pl"
        assert result["tgt_lang"] == "en"


@pytest.mark.integration
@pytest.mark.asyncio
class TestMTRoutingLookup:
    """Test MT routing configuration lookup from database."""

    async def test_lookup_polish_to_english(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test lookup for Polish→English translation."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("pl", "en", "standard")

        assert result["provider"] == "deepl"
        assert result["fallback"] == "google_translate"
        assert result["src_lang"] == "pl"
        assert result["tgt_lang"] == "en"
        # Config might be JSONB dict or JSON string depending on asyncpg version
        assert result["config"] is not None

    async def test_lookup_english_to_arabic(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test lookup for English→Arabic translation."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("en", "ar", "standard")

        assert result["provider"] == "google_translate"
        assert result["fallback"] == "amazon_translate"
        assert result["src_lang"] == "en"
        assert result["tgt_lang"] == "ar"

    async def test_lookup_spanish_to_english(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test lookup for Spanish→English translation (DeepL optimization)."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("es", "en", "standard")

        assert result["provider"] == "deepl"
        assert result["fallback"] == "google_translate"

    async def test_bidirectional_pairs(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that bidirectional pairs are configured correctly."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # pl→en
        result_pl_en = await get_mt_provider_for_pair("pl", "en", "standard")
        assert result_pl_en["provider"] == "deepl"

        # en→pl
        result_en_pl = await get_mt_provider_for_pair("en", "pl", "standard")
        assert result_en_pl["provider"] == "deepl"

    async def test_fallback_to_wildcard(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test fallback to wildcard (*→*) for unknown language pair."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("zh", "ja", "standard")

        assert result["provider"] == "google_translate"
        assert result["fallback"] == "amazon_translate"
        assert result["src_lang"] == "zh"
        assert result["tgt_lang"] == "ja"


@pytest.mark.integration
@pytest.mark.asyncio
class TestWildcardFallbackPriority:
    """Test wildcard fallback priority ordering."""

    async def test_specific_source_wildcard_target(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that (src, *) is prioritized over (*, tgt) and (*, *)."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Insert wildcard configs
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO mt_routing_config (src_lang, tgt_lang, quality_tier, provider_primary, provider_fallback, config, enabled)
                VALUES
                    ('pl', '*', 'standard', 'priority_1', 'fallback1', '{}', TRUE),
                    ('*', 'ja', 'standard', 'priority_2', 'fallback2', '{}', TRUE)
                ON CONFLICT (src_lang, tgt_lang, quality_tier) DO UPDATE
                SET provider_primary = EXCLUDED.provider_primary
            """)

        _routing_cache.clear()

        try:
            # pl→ja should match (pl, *) with priority 1
            result = await get_mt_provider_for_pair("pl", "ja", "standard")
            assert result["provider"] == "priority_1"
        finally:
            # Cleanup
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    DELETE FROM mt_routing_config
                    WHERE (src_lang = 'pl' AND tgt_lang = '*')
                       OR (src_lang = '*' AND tgt_lang = 'ja')
                """)


@pytest.mark.integration
@pytest.mark.asyncio
class TestMTCaching:
    """Test Redis caching functionality for MT routing."""

    async def test_cache_populated_on_first_lookup(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that cache is populated on first lookup."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # First lookup - should hit database
        result1 = await get_mt_provider_for_pair("pl", "en", "standard")
        assert result1["provider"] == "deepl"

        # Check cache is populated
        cache_key = ("pl", "en", "standard", "mt")
        assert cache_key in _routing_cache

    async def test_cache_used_on_second_lookup(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that second lookup uses cache."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # First lookup
        result1 = await get_mt_provider_for_pair("pl", "en", "standard")

        # Modify database (should not affect cached result)
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE mt_routing_config
                SET provider_primary = 'changed_provider'
                WHERE src_lang = 'pl' AND tgt_lang = 'en' AND quality_tier = 'standard'
            """)

        # Second lookup - should use cache
        result2 = await get_mt_provider_for_pair("pl", "en", "standard")
        assert result2["provider"] == "deepl"  # From cache, not 'changed_provider'

    async def test_cache_expires_after_ttl(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that cache expires after TTL."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # First lookup
        result1 = await get_mt_provider_for_pair("pl", "en", "standard")

        # Manually expire cache
        cache_key = ("pl", "en", "standard", "mt")
        _routing_cache[cache_key]["cached_at"] = datetime.now() - timedelta(seconds=400)

        # Update database
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE mt_routing_config
                SET provider_primary = 'updated_provider'
                WHERE src_lang = 'pl' AND tgt_lang = 'en' AND quality_tier = 'standard'
            """)

        # Second lookup - cache expired, should hit database
        result2 = await get_mt_provider_for_pair("pl", "en", "standard")
        assert result2["provider"] == "updated_provider"


@pytest.mark.integration
@pytest.mark.asyncio
class TestMTProviderHealthIntegration:
    """Test MT provider health check and fallback logic."""

    async def test_healthy_provider_selected(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that healthy primary provider is selected."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("pl", "en", "standard")
        assert result["provider"] == "deepl"  # Primary provider (healthy)

    async def test_unhealthy_provider_falls_back(self, db_pool, test_mt_routing_config, clean_routing_cache):
        """Test fallback when primary MT provider is down."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Mark deepl as down
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO provider_health (provider, service_type, status, consecutive_failures, last_check)
                VALUES ('deepl', 'mt', 'down', 5, NOW())
                ON CONFLICT (provider, service_type) DO UPDATE
                SET status = 'down', consecutive_failures = 5
            """)

        # Clear cache
        _routing_cache.clear()

        result = await get_mt_provider_for_pair("pl", "en", "standard")
        assert result["provider"] == "google_translate"  # Fallback provider

    async def test_mt_provider_health_check(self, db_pool, test_mt_provider_health):
        """Test MT provider health check returns correct status."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        health = await check_provider_health("deepl", "mt")
        assert health["status"] == "healthy"
        assert health["consecutive_failures"] == 0
        assert health["response_time_ms"] == 120


@pytest.mark.integration
@pytest.mark.asyncio
class TestQualityTiers:
    """Test quality tier routing (standard vs budget)."""

    async def test_standard_tier_uses_premium_provider(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that standard tier uses DeepL for European languages."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("pl", "en", "standard")
        assert result["provider"] == "deepl"

    async def test_budget_tier_uses_cheaper_provider(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that budget tier uses cheaper providers."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        result = await get_mt_provider_for_pair("zh", "ja", "budget")
        assert result["provider"] == "amazon_translate"


@pytest.mark.integration
@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_disabled_configuration_skipped(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that disabled configurations are skipped."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # test→test is disabled, should fall back to wildcard
        result = await get_mt_provider_for_pair("test", "test", "standard")

        # Should get wildcard config, not test_provider
        assert result["provider"] != "test_provider"
        assert result["provider"] == "google_translate"

    async def test_null_fallback_provider_in_config(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test that config with NULL fallback is returned correctly."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Update existing config to have NULL fallback
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE mt_routing_config
                SET provider_fallback = NULL
                WHERE src_lang = 'ar' AND tgt_lang = 'en' AND quality_tier = 'standard'
            """)

        # Clear cache to force fresh lookup
        _routing_cache.clear()

        try:
            result = await get_mt_provider_for_pair("ar", "en", "standard")
            assert result["provider"] == "google_translate"
            assert result["fallback"] is None
        finally:
            # Restore fallback
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE mt_routing_config
                    SET provider_fallback = 'amazon_translate'
                    WHERE src_lang = 'ar' AND tgt_lang = 'en' AND quality_tier = 'standard'
                """)

    async def test_database_connection_failure_uses_default(self, clean_routing_cache):
        """Test that default provider is used when database is unavailable."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = None  # Simulate no connection

        with patch.dict(os.environ, {"LT_MT_MODE": "fallback_openai"}):
            result = await get_mt_provider_for_pair("pl", "en", "standard")
            assert result["provider"] == "fallback_openai"


@pytest.mark.integration
@pytest.mark.asyncio
class TestSequentialLookups:
    """Test multiple sequential lookups to verify no state pollution."""

    async def test_multiple_language_pairs_sequential(self, db_pool, test_mt_routing_config, clean_routing_cache, test_mt_provider_health):
        """Test multiple sequential MT lookups."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Sequential lookups
        result1 = await get_mt_provider_for_pair("pl", "en", "standard")
        result2 = await get_mt_provider_for_pair("en", "ar", "standard")
        result3 = await get_mt_provider_for_pair("es", "en", "standard")
        result4 = await get_mt_provider_for_pair("ar", "en", "standard")

        # Verify all results
        assert result1["provider"] == "deepl"
        assert result2["provider"] == "google_translate"
        assert result3["provider"] == "deepl"
        assert result4["provider"] == "google_translate"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
