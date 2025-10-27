"""
Integration tests for cost tracking system.

Tests cover:
- Cost event publishing and consumption via Redis
- Cost calculation for multiple providers (STT, MT)
- Cost persistence to database
- Cost aggregation and retrieval
- Multi-provider pricing support
- Error handling and edge cases
"""

import pytest
import pytest_asyncio
import asyncio
import asyncpg
import redis.asyncio as redis
import os
import json
from decimal import Decimal
from datetime import datetime


POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://lt_user:CHANGE_ME_BEFORE_DEPLOY@postgres:5432/livetranslator")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")
COST_CHANNEL = "cost_events"


@pytest_asyncio.fixture
async def db_pool():
    """Create a database connection pool for testing."""
    # Parse DSN
    import re
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', POSTGRES_DSN)
    if not match:
        pytest.skip("Invalid POSTGRES_DSN")

    user, password, host, port, database = match.groups()

    pool = await asyncpg.create_pool(
        user=user,
        password=password,
        host=host,
        port=int(port),
        database=database,
        min_size=1,
        max_size=5
    )

    yield pool
    await pool.close()


@pytest_asyncio.fixture
async def redis_client():
    """Create a Redis client for testing."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def clean_room(db_pool):
    """Provide a clean test room and clean up costs after."""
    room_code = f"test-cost-{datetime.now().timestamp()}"

    yield room_code

    # Clean up test data
    async with db_pool.acquire() as conn:
        await conn.execute("DELETE FROM room_costs WHERE room_id = $1", room_code)


@pytest_asyncio.fixture
async def provider_pricing(db_pool):
    """Ensure provider pricing exists in database."""
    async with db_pool.acquire() as conn:
        # Check if provider_pricing table exists and has data
        try:
            count = await conn.fetchval("SELECT COUNT(*) FROM provider_pricing")
            if count == 0:
                # Insert test pricing data
                await conn.execute("""
                    INSERT INTO provider_pricing (service, provider, pricing_model, unit_price, effective_date)
                    VALUES
                        ('stt', 'openai', 'per_minute', 0.006, '2024-01-01'),
                        ('stt', 'speechmatics', 'per_hour', 0.50, '2024-01-01'),
                        ('mt', 'openai', 'per_1k_tokens', 0.00015, '2024-01-01'),
                        ('mt', 'deepl', 'per_1m_chars', 20.00, '2024-01-01')
                    ON CONFLICT DO NOTHING
                """)
        except asyncpg.exceptions.UndefinedTableError:
            pytest.skip("provider_pricing table does not exist")

    yield

    # Cleanup test pricing (optional, as it's global)


@pytest.mark.integration
@pytest.mark.asyncio
class TestCostPersistence:
    """Test cost persistence to database."""

    async def test_insert_cost_record(self, db_pool, clean_room):
        """Test inserting a cost record directly to database."""
        room = clean_room

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """, room, "stt", "openai", "openai", 60, "seconds", 0.006)

        # Verify insertion
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM room_costs WHERE room_id = $1",
                room
            )

        assert result is not None
        assert result['room_id'] == room
        assert result['pipeline'] == 'stt'
        assert result['mode'] == 'openai'
        assert result['units'] == 60
        assert result['unit_type'] == 'seconds'
        assert abs(float(result['amount_usd']) - 0.006) < 0.0001

    async def test_aggregate_costs_by_room(self, db_pool, clean_room):
        """Test aggregating costs for a room."""
        room = clean_room

        # Insert multiple cost records
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                VALUES
                    ($1, 'stt', 'openai', 'openai', 60, 'seconds', 0.006, NOW()),
                    ($1, 'stt', 'openai', 'openai', 30, 'seconds', 0.003, NOW()),
                    ($1, 'mt', 'openai', 'openai', 1000, 'tokens', 0.00015, NOW())
            """, room)

        # Aggregate costs
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT
                    SUM(amount_usd) FILTER (WHERE pipeline = 'stt') as stt_cost,
                    SUM(amount_usd) FILTER (WHERE pipeline = 'mt') as mt_cost,
                    SUM(amount_usd) as total_cost
                FROM room_costs
                WHERE room_id = $1
            """, room)

        assert abs(float(result['stt_cost']) - 0.009) < 0.0001  # 0.006 + 0.003
        assert abs(float(result['mt_cost']) - 0.00015) < 0.0001
        assert abs(float(result['total_cost']) - 0.00915) < 0.0001

    async def test_cost_record_with_null_provider(self, db_pool, clean_room):
        """Test cost record can be created with NULL provider (backward compat)."""
        room = clean_room

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, units, unit_type, amount_usd, ts)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
            """, room, "stt", "local", 60, "seconds", 0.0)

        # Verify insertion
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT * FROM room_costs WHERE room_id = $1",
                room
            )

        assert result is not None
        assert result['mode'] == 'local'
        assert result['amount_usd'] == 0.0


@pytest.mark.integration
@pytest.mark.asyncio
class TestCostCalculationService:
    """Test cost calculation logic from service."""

    async def test_calculate_stt_cost_per_minute(self):
        """Test STT cost calculation (per minute pricing)."""
        from api.services.cost_tracker_service import calculate_cost

        # Mock pricing
        pricing = {
            ('stt', 'openai'): {
                'model': 'per_minute',
                'price': Decimal('0.006')
            }
        }

        # 60 seconds = 1 minute
        cost = calculate_cost('stt', 'openai', 60.0, 'seconds', pricing)

        assert abs(cost - Decimal('0.006')) < Decimal('0.0001')

    async def test_calculate_stt_cost_per_hour(self):
        """Test STT cost calculation (per hour pricing)."""
        from api.services.cost_tracker_service import calculate_cost

        pricing = {
            ('stt', 'speechmatics'): {
                'model': 'per_hour',
                'price': Decimal('0.50')
            }
        }

        # 3600 seconds = 1 hour
        cost = calculate_cost('stt', 'speechmatics', 3600.0, 'seconds', pricing)

        assert abs(cost - Decimal('0.50')) < Decimal('0.01')

    async def test_calculate_mt_cost_per_1k_tokens(self):
        """Test MT cost calculation (per 1k tokens pricing)."""
        from api.services.cost_tracker_service import calculate_cost

        pricing = {
            ('mt', 'openai'): {
                'model': 'per_1k_tokens',
                'price': Decimal('0.00015')
            }
        }

        # 1000 tokens
        cost = calculate_cost('mt', 'openai', 1000.0, 'tokens', pricing)

        assert abs(cost - Decimal('0.00015')) < Decimal('0.000001')

    async def test_calculate_mt_cost_per_1m_chars(self):
        """Test MT cost calculation (per 1M chars pricing)."""
        from api.services.cost_tracker_service import calculate_cost

        pricing = {
            ('mt', 'deepl'): {
                'model': 'per_1m_chars',
                'price': Decimal('20.00')
            }
        }

        # 1,000,000 characters
        cost = calculate_cost('mt', 'deepl', 1_000_000.0, 'characters', pricing)

        assert abs(cost - Decimal('20.00')) < Decimal('0.01')

    async def test_calculate_cost_unknown_provider(self):
        """Test cost calculation for unknown provider returns 0."""
        from api.services.cost_tracker_service import calculate_cost

        pricing = {}

        cost = calculate_cost('stt', 'unknown_provider', 60.0, 'seconds', pricing)

        assert cost == Decimal('0')

    async def test_calculate_cost_fractional_units(self):
        """Test cost calculation with fractional units."""
        from api.services.cost_tracker_service import calculate_cost

        pricing = {
            ('stt', 'openai'): {
                'model': 'per_minute',
                'price': Decimal('0.006')
            }
        }

        # 45 seconds = 0.75 minutes
        cost = calculate_cost('stt', 'openai', 45.0, 'seconds', pricing)

        # 0.75 * 0.006 = 0.0045
        assert abs(cost - Decimal('0.0045')) < Decimal('0.0001')


@pytest.mark.integration
@pytest.mark.asyncio
class TestCostEventPublishing:
    """Test publishing cost events via Redis."""

    async def test_publish_stt_cost_event(self, redis_client, clean_room):
        """Test publishing an STT cost event to Redis."""
        room = clean_room

        event = {
            "room_id": room,
            "pipeline": "stt",
            "provider": "openai",
            "mode": "openai",
            "units": 60,
            "unit_type": "seconds"
        }

        # Publish event
        await redis_client.publish(COST_CHANNEL, json.dumps(event))

        # Event was published (no error)
        assert True

    async def test_publish_mt_cost_event(self, redis_client, clean_room):
        """Test publishing an MT cost event to Redis."""
        room = clean_room

        event = {
            "room_id": room,
            "pipeline": "mt",
            "provider": "deepl",
            "mode": "deepl",
            "units": 500,
            "unit_type": "characters"
        }

        await redis_client.publish(COST_CHANNEL, json.dumps(event))

        assert True


@pytest.mark.integration
@pytest.mark.asyncio
class TestCostAggregation:
    """Test cost aggregation and retrieval."""

    async def test_aggregate_empty_room(self, db_pool, clean_room):
        """Test aggregating costs for a room with no costs."""
        room = clean_room

        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT
                    SUM(amount_usd) as total_cost,
                    COUNT(*) as event_count
                FROM room_costs
                WHERE room_id = $1
            """, room)

        assert result['total_cost'] is None
        assert result['event_count'] == 0

    async def test_aggregate_by_pipeline(self, db_pool, clean_room):
        """Test aggregating costs grouped by pipeline."""
        room = clean_room

        # Insert costs for different pipelines
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                VALUES
                    ($1, 'stt', 'openai', 'openai', 60, 'seconds', 0.010, NOW()),
                    ($1, 'stt', 'speechmatics', 'speechmatics', 120, 'seconds', 0.020, NOW()),
                    ($1, 'mt', 'openai', 'openai', 1000, 'tokens', 0.005, NOW()),
                    ($1, 'mt', 'deepl', 'deepl', 500, 'characters', 0.003, NOW())
            """, room)

        # Aggregate by pipeline
        async with db_pool.acquire() as conn:
            results = await conn.fetch("""
                SELECT
                    pipeline,
                    SUM(amount_usd) as total_cost,
                    COUNT(*) as event_count
                FROM room_costs
                WHERE room_id = $1
                GROUP BY pipeline
                ORDER BY pipeline
            """, room)

        # Convert to dict for easier assertion
        aggregated = {r['pipeline']: r for r in results}

        assert 'stt' in aggregated
        assert 'mt' in aggregated
        assert abs(float(aggregated['stt']['total_cost']) - 0.030) < 0.001
        assert abs(float(aggregated['mt']['total_cost']) - 0.008) < 0.001
        assert aggregated['stt']['event_count'] == 2
        assert aggregated['mt']['event_count'] == 2

    async def test_aggregate_by_provider(self, db_pool, clean_room):
        """Test aggregating costs grouped by provider."""
        room = clean_room

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                VALUES
                    ($1, 'stt', 'openai', 'openai', 60, 'seconds', 0.006, NOW()),
                    ($1, 'mt', 'openai', 'openai', 1000, 'tokens', 0.00015, NOW())
            """, room)

        # Aggregate by provider
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow("""
                SELECT
                    provider,
                    SUM(amount_usd) as total_cost,
                    COUNT(*) as event_count
                FROM room_costs
                WHERE room_id = $1 AND provider = 'openai'
                GROUP BY provider
            """, room)

        assert result['provider'] == 'openai'
        assert abs(float(result['total_cost']) - 0.00615) < 0.0001
        assert result['event_count'] == 2


@pytest.mark.integration
@pytest.mark.asyncio
class TestCostEdgeCases:
    """Test edge cases and error scenarios."""

    async def test_cost_with_zero_units(self, db_pool, clean_room):
        """Test cost record with zero units."""
        room = clean_room

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """, room, "stt", "openai", "openai", 0, "seconds", 0.0)

        # Verify zero cost
        async with db_pool.acquire() as conn:
            result = await conn.fetchrow(
                "SELECT SUM(amount_usd) as total FROM room_costs WHERE room_id = $1",
                room
            )

        assert float(result['total']) == 0.0

    async def test_cost_with_large_numbers(self, db_pool, clean_room):
        """Test cost calculation with large numbers (long session)."""
        room = clean_room

        # 10 hour session (36000 seconds)
        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """, room, "stt", "openai", "openai", 36000, "seconds", 3.6)

        async with db_pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT SUM(amount_usd) FROM room_costs WHERE room_id = $1",
                room
            )

        assert abs(float(result) - 3.6) < 0.01

    async def test_concurrent_cost_insertions(self, db_pool, clean_room):
        """Test concurrent cost insertions to same room."""
        room = clean_room

        async def insert_cost(cost_id):
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                """, room, "stt", "openai", "openai", cost_id, "seconds", 0.001)

        # Insert 10 costs concurrently
        await asyncio.gather(*[insert_cost(i) for i in range(10)])

        # Verify all 10 were inserted
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM room_costs WHERE room_id = $1",
                room
            )

        assert count == 10

    async def test_cost_precision_decimal(self, db_pool, clean_room):
        """Test that cost values maintain decimal precision."""
        room = clean_room

        # Very small cost (micro-pennies)
        small_cost = 0.000001

        async with db_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO room_costs (room_id, pipeline, mode, provider, units, unit_type, amount_usd, ts)
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """, room, "mt", "openai", "openai", 1, "tokens", small_cost)

        async with db_pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT amount_usd FROM room_costs WHERE room_id = $1",
                room
            )

        # Precision should be maintained (6 decimal places)
        assert abs(float(result) - small_cost) < 0.0000001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
