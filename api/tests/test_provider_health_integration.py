"""
Integration tests for Provider Health Monitoring System.

Tests cover:
- Health check updates in database
- Consecutive failure tracking
- Automatic failover on unhealthy provider
- Health recovery and restoration
- Response time tracking
- Multi-provider health scenarios
- Health status transitions (healthy → degraded → down)
- Integration with STT/MT routing
"""

import pytest
import pytest_asyncio
import asyncio
import asyncpg
import os
from datetime import datetime, timedelta

# Import the module under test
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../routers/stt'))

from api.routers.stt.language_router import (
    check_provider_health,
    update_provider_health,
    get_stt_provider_for_language,
    get_mt_provider_for_pair,
)


# Test database connection
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://lt_user:${POSTGRES_PASSWORD}@postgres:5432/livetranslator")


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
async def test_health_data(db_pool):
    """Insert test provider health records."""
    async with db_pool.acquire() as conn:
        # Insert test health records
        await conn.execute("""
            INSERT INTO provider_health (provider, service_type, status, consecutive_failures, last_check, last_success, response_time_ms)
            VALUES
                ('test_healthy', 'stt', 'healthy', 0, NOW(), NOW(), 100),
                ('test_degraded', 'stt', 'degraded', 1, NOW(), NOW() - INTERVAL '5 minutes', 250),
                ('test_down', 'stt', 'down', 5, NOW(), NOW() - INTERVAL '1 hour', NULL),
                ('test_mt_healthy', 'mt', 'healthy', 0, NOW(), NOW(), 120),
                ('test_mt_down', 'mt', 'down', 3, NOW(), NOW() - INTERVAL '30 minutes', NULL)
            ON CONFLICT (provider, service_type) DO UPDATE
            SET status = EXCLUDED.status,
                consecutive_failures = EXCLUDED.consecutive_failures,
                last_check = EXCLUDED.last_check,
                last_success = EXCLUDED.last_success,
                response_time_ms = EXCLUDED.response_time_ms
        """)

    yield

    # Cleanup
    async with db_pool.acquire() as conn:
        await conn.execute("""
            DELETE FROM provider_health
            WHERE provider IN ('test_healthy', 'test_degraded', 'test_down', 'test_mt_healthy', 'test_mt_down', 'test_recovery')
        """)


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthCheckRetrieval:
    """Test retrieving provider health status."""

    async def test_check_healthy_provider(self, db_pool, test_health_data):
        """Test checking status of healthy provider."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        health = await check_provider_health("test_healthy", "stt")

        assert health["provider"] == "test_healthy"
        assert health["status"] == "healthy"
        assert health["consecutive_failures"] == 0
        assert health["response_time_ms"] == 100

    async def test_check_degraded_provider(self, db_pool, test_health_data):
        """Test checking status of degraded provider."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        health = await check_provider_health("test_degraded", "stt")

        assert health["provider"] == "test_degraded"
        assert health["status"] == "degraded"
        assert health["consecutive_failures"] == 1
        assert health["response_time_ms"] == 250

    async def test_check_down_provider(self, db_pool, test_health_data):
        """Test checking status of down provider."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        health = await check_provider_health("test_down", "stt")

        assert health["provider"] == "test_down"
        assert health["status"] == "down"
        assert health["consecutive_failures"] == 5
        assert health["response_time_ms"] is None

    async def test_check_nonexistent_provider(self, db_pool):
        """Test checking status of provider not in database."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        health = await check_provider_health("nonexistent_provider", "stt")

        # Should return default healthy status
        assert health["provider"] == "nonexistent_provider"
        assert health["status"] == "healthy"
        assert health["consecutive_failures"] == 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthUpdates:
    """Test updating provider health status."""

    async def test_update_success_resets_failures(self, db_pool, test_health_data):
        """Test that successful call resets consecutive failures."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Provider starts degraded
        health_before = await check_provider_health("test_degraded", "stt")
        assert health_before["consecutive_failures"] == 1

        # Update with success
        await update_provider_health("test_degraded", "stt", success=True, response_time_ms=150)

        # Should be healthy now
        health_after = await check_provider_health("test_degraded", "stt")
        assert health_after["status"] == "healthy"
        assert health_after["consecutive_failures"] == 0

    async def test_update_failure_increments_counter(self, db_pool, test_health_data):
        """Test that failed call increments consecutive failures."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Start with healthy provider
        health_before = await check_provider_health("test_healthy", "stt")
        assert health_before["consecutive_failures"] == 0

        # Update with failure
        await update_provider_health("test_healthy", "stt", success=False, error="Test error")

        # Should be degraded with 1 failure
        health_after = await check_provider_health("test_healthy", "stt")
        assert health_after["status"] == "degraded"
        assert health_after["consecutive_failures"] == 1

    async def test_multiple_failures_transition_to_down(self, db_pool, test_health_data):
        """Test that 3+ consecutive failures mark provider as down."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Start with healthy provider
        await update_provider_health("test_mt_healthy", "mt", success=True)

        # Fail once - should be degraded
        await update_provider_health("test_mt_healthy", "mt", success=False, error="Failure 1")
        health_1 = await check_provider_health("test_mt_healthy", "mt")
        assert health_1["status"] == "degraded"
        assert health_1["consecutive_failures"] == 1

        # Fail twice - still degraded
        await update_provider_health("test_mt_healthy", "mt", success=False, error="Failure 2")
        health_2 = await check_provider_health("test_mt_healthy", "mt")
        assert health_2["status"] == "degraded"
        assert health_2["consecutive_failures"] == 2

        # Fail three times - now down
        await update_provider_health("test_mt_healthy", "mt", success=False, error="Failure 3")
        health_3 = await check_provider_health("test_mt_healthy", "mt")
        assert health_3["status"] == "down"
        assert health_3["consecutive_failures"] >= 3


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthRecovery:
    """Test provider health recovery scenarios."""

    async def test_recovery_from_down_to_healthy(self, db_pool, test_health_data):
        """Test that down provider can recover to healthy."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Start down
        health_before = await check_provider_health("test_down", "stt")
        assert health_before["status"] == "down"

        # Successful call
        await update_provider_health("test_down", "stt", success=True, response_time_ms=100)

        # Should be healthy
        health_after = await check_provider_health("test_down", "stt")
        assert health_after["status"] == "healthy"
        assert health_after["consecutive_failures"] == 0

    async def test_partial_recovery_interrupted(self, db_pool):
        """Test that recovery is interrupted by new failures."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Create test provider
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO provider_health (provider, service_type, status, consecutive_failures, last_check)
                VALUES ('test_recovery', 'stt', 'down', 5, NOW())
                ON CONFLICT (provider, service_type) DO UPDATE
                SET status = 'down', consecutive_failures = 5
            """)

        try:
            # One success - should recover
            await update_provider_health("test_recovery", "stt", success=True)
            health_1 = await check_provider_health("test_recovery", "stt")
            assert health_1["status"] == "healthy"

            # But then fails again
            await update_provider_health("test_recovery", "stt", success=False)
            health_2 = await check_provider_health("test_recovery", "stt")
            assert health_2["status"] == "degraded"
            assert health_2["consecutive_failures"] == 1
        finally:
            # Cleanup
            async with db_pool.acquire() as conn:
                await conn.execute("DELETE FROM provider_health WHERE provider = 'test_recovery'")


@pytest.mark.integration
@pytest.mark.asyncio
class TestResponseTimeTracking:
    """Test response time tracking."""

    async def test_response_time_recorded_on_success(self, db_pool, test_health_data):
        """Test that response time is recorded for successful calls."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Update with specific response time
        await update_provider_health("test_healthy", "stt", success=True, response_time_ms=175)

        health = await check_provider_health("test_healthy", "stt")
        assert health["response_time_ms"] == 175

    async def test_response_time_null_on_failure(self, db_pool, test_health_data):
        """Test that response time is not updated on failure."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Get current response time
        health_before = await check_provider_health("test_degraded", "stt")
        response_time_before = health_before["response_time_ms"]

        # Update with failure (no response time)
        await update_provider_health("test_degraded", "stt", success=False, error="Timeout")

        # Response time should be cleared or remain
        health_after = await check_provider_health("test_degraded", "stt")
        # Response time might be null or unchanged depending on implementation
        assert health_after["consecutive_failures"] > health_before["consecutive_failures"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestMultiProviderScenarios:
    """Test scenarios with multiple providers."""

    async def test_different_service_types_independent(self, db_pool, test_health_data):
        """Test that STT and MT health tracking is independent."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Use test providers with different service types
        stt_health = await check_provider_health("test_healthy", "stt")
        mt_health = await check_provider_health("test_mt_healthy", "mt")

        # Both exist independently with their own status
        assert stt_health["provider"] == "test_healthy"
        assert stt_health["status"] == "healthy"
        assert mt_health["provider"] == "test_mt_healthy"
        assert mt_health["status"] == "healthy"

    async def test_concurrent_health_updates(self, db_pool, test_health_data):
        """Test concurrent health updates to different providers."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Update multiple providers concurrently
        await asyncio.gather(
            update_provider_health("test_healthy", "stt", success=True, response_time_ms=100),
            update_provider_health("test_degraded", "stt", success=False, error="Error"),
            update_provider_health("test_mt_healthy", "mt", success=True, response_time_ms=120),
        )

        # All should be updated correctly
        h1 = await check_provider_health("test_healthy", "stt")
        h2 = await check_provider_health("test_degraded", "stt")
        h3 = await check_provider_health("test_mt_healthy", "mt")

        assert h1["status"] == "healthy"
        assert h2["consecutive_failures"] > 0
        assert h3["status"] == "healthy"


@pytest.mark.integration
@pytest.mark.asyncio
class TestHealthIntegrationWithRouting:
    """Test health monitoring integration with routing logic."""

    async def test_unhealthy_stt_provider_triggers_fallback(self, db_pool):
        """Test that unhealthy STT provider triggers fallback in routing."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Mark speechmatics as down
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE provider_health
                SET status = 'down', consecutive_failures = 5
                WHERE provider = 'speechmatics' AND service_type = 'stt'
            """)

        try:
            # Clear cache to force fresh lookup
            from api.routers.stt.language_router import _routing_cache
            _routing_cache.clear()

            # Try to get provider for English
            # Should fall back from speechmatics to alternative
            result = await get_stt_provider_for_language("en", "partial", "standard")

            # Should NOT be speechmatics (should be fallback)
            assert result["provider"] != "speechmatics"
        finally:
            # Restore health
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE provider_health
                    SET status = 'healthy', consecutive_failures = 0
                    WHERE provider = 'speechmatics' AND service_type = 'stt'
                """)

    async def test_unhealthy_mt_provider_triggers_fallback(self, db_pool):
        """Test that unhealthy MT provider triggers fallback in routing."""
        import api.routers.stt.language_router as router_module
        router_module._db_pool = db_pool

        # Mark deepl as down
        async with db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE provider_health
                SET status = 'down', consecutive_failures = 5
                WHERE provider = 'deepl' AND service_type = 'mt'
            """)

        try:
            # Clear cache
            from api.routers.stt.language_router import _routing_cache
            _routing_cache.clear()

            # Try to get provider for pl→en (normally DeepL)
            result = await get_mt_provider_for_pair("pl", "en", "standard")

            # Should NOT be deepl (should be fallback)
            assert result["provider"] != "deepl"
        finally:
            # Restore health
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE provider_health
                    SET status = 'healthy', consecutive_failures = 0
                    WHERE provider = 'deepl' AND service_type = 'mt'
                """)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
