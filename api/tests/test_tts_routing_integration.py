"""
Integration tests for TTS language routing database configuration.

Tests cover:
- TTS routing configuration table
- Provider health tracking
- Provider pricing
- Language-based routing
- Quality tier selection

Priority: Integration (real database)
"""

import pytest
import pytest_asyncio
from sqlalchemy import text
import json


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_routing_config_exists(test_db_session):
    """Test tts_routing_config table exists and has data."""
    result = await test_db_session.execute(
        text("SELECT COUNT(*) FROM tts_routing_config WHERE enabled = TRUE")
    )
    count = result.scalar()

    assert count > 0

    print(f"✅ TTS routing configs found: {count}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_tts_provider_for_language(test_db_session):
    """Test TTS provider selection for specific language."""
    # Query for English
    result = await test_db_session.execute(
        text("""
            SELECT provider_primary, provider_fallback, config
            FROM tts_routing_config
            WHERE language = :lang AND quality_tier = :tier AND enabled = TRUE
            LIMIT 1
        """),
        {"lang": "en", "tier": "standard"}
    )
    row = result.fetchone()

    if row:
        assert row[0] in ["google_tts", "azure_tts", "amazon_tts"]  # Valid provider
        config = row[2]
        assert "voice_id" in config
        print(f"✅ Provider for English: {row[0]} ({config['voice_id']})")
    else:
        print("⚠️ No routing config for English (fallback to wildcard)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_wildcard_fallback(test_db_session):
    """Test wildcard (*) fallback for unsupported languages."""
    # Query for wildcard
    result = await test_db_session.execute(
        text("""
            SELECT provider_primary, provider_fallback, config
            FROM tts_routing_config
            WHERE language = '*' AND quality_tier = :tier AND enabled = TRUE
            LIMIT 1
        """),
        {"tier": "standard"}
    )
    row = result.fetchone()

    assert row is not None  # Wildcard should always exist
    assert row[0] is not None  # Must have primary provider

    print(f"✅ Wildcard fallback provider: {row[0]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_routing_multiple_languages(test_db_session):
    """Test routing configuration for multiple languages."""
    languages = ["en", "pl", "ar", "es"]
    configs = {}

    for lang in languages:
        result = await test_db_session.execute(
            text("""
                SELECT provider_primary, config
                FROM tts_routing_config
                WHERE language = :lang AND quality_tier = 'standard' AND enabled = TRUE
                LIMIT 1
            """),
            {"lang": lang}
        )
        row = result.fetchone()
        if row:
            configs[lang] = {"provider": row[0], "config": row[1]}

    print(f"✅ Multi-language routing ({len(configs)} languages configured):")
    for lang, conf in configs.items():
        print(f"   - {lang}: {conf['provider']} ({conf['config'].get('voice_id', 'N/A')})")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_quality_tier_selection(test_db_session):
    """Test routing based on quality tier."""
    # Standard tier
    result = await test_db_session.execute(
        text("""
            SELECT provider_primary FROM tts_routing_config
            WHERE language = '*' AND quality_tier = 'standard' AND enabled = TRUE
        """)
    )
    standard_row = result.fetchone()

    # Budget tier
    result = await test_db_session.execute(
        text("""
            SELECT provider_primary FROM tts_routing_config
            WHERE language = '*' AND quality_tier = 'budget' AND enabled = TRUE
        """)
    )
    budget_row = result.fetchone()

    if standard_row and budget_row:
        print(f"✅ Quality tier routing:")
        print(f"   - Standard: {standard_row[0]}")
        print(f"   - Budget: {budget_row[0]}")
    else:
        print("⚠️ Not all quality tiers configured")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_provider_health_tracking(test_db_session):
    """Test provider health status tracking."""
    result = await test_db_session.execute(
        text("""
            SELECT provider, status, consecutive_failures
            FROM provider_health
            WHERE service_type = 'tts'
        """)
    )
    rows = result.fetchall()

    assert len(rows) > 0

    print(f"✅ Provider health tracking ({len(rows)} TTS providers):")
    for row in rows:
        print(f"   - {row[0]}: {row[1]} ({row[2]} failures)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_provider_health_success(test_db_session):
    """Test updating provider health on success."""
    # Update google_tts to healthy
    await test_db_session.execute(
        text("""
            UPDATE provider_health
            SET status = 'healthy',
                consecutive_failures = 0,
                last_check = NOW(),
                last_success = NOW()
            WHERE provider = 'google_tts' AND service_type = 'tts'
        """)
    )
    await test_db_session.commit()

    # Verify update
    result = await test_db_session.execute(
        text("""
            SELECT status, consecutive_failures
            FROM provider_health
            WHERE provider = 'google_tts' AND service_type = 'tts'
        """)
    )
    row = result.fetchone()

    if row:
        assert row[0] == "healthy"
        assert row[1] == 0
        print(f"✅ Provider health updated (success): google_tts - {row[0]}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_update_provider_health_failure(test_db_session):
    """Test updating provider health on failure."""
    # Simulate 3 failures
    for i in range(3):
        await test_db_session.execute(
            text("""
                UPDATE provider_health
                SET consecutive_failures = consecutive_failures + 1,
                    last_check = NOW(),
                    status = CASE
                        WHEN consecutive_failures + 1 >= 3 THEN 'down'
                        WHEN consecutive_failures + 1 >= 1 THEN 'degraded'
                        ELSE 'healthy'
                    END
                WHERE provider = 'google_tts' AND service_type = 'tts'
            """)
        )
        await test_db_session.commit()

    # Check status
    result = await test_db_session.execute(
        text("""
            SELECT status, consecutive_failures
            FROM provider_health
            WHERE provider = 'google_tts' AND service_type = 'tts'
        """)
    )
    row = result.fetchone()

    if row:
        assert row[1] >= 3
        print(f"✅ Provider health updated (failure): google_tts - {row[0]} ({row[1]} failures)")

    # Reset to healthy
    await test_db_session.execute(
        text("""
            UPDATE provider_health
            SET status = 'healthy', consecutive_failures = 0
            WHERE provider = 'google_tts' AND service_type = 'tts'
        """)
    )
    await test_db_session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_provider_pricing(test_db_session):
    """Test TTS provider pricing exists."""
    result = await test_db_session.execute(
        text("""
            SELECT provider, unit_price
            FROM provider_pricing
            WHERE service = 'tts'
        """)
    )
    rows = result.fetchall()

    assert len(rows) > 0

    print(f"✅ TTS provider pricing ({len(rows)} providers):")
    for row in rows:
        print(f"   - {row[0]}: ${row[1]:.6f} per character")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_routing_config_unique_constraint(test_db_session):
    """Test unique constraint on (language, quality_tier)."""
    # Try to insert duplicate (should be prevented by ON CONFLICT)
    result = await test_db_session.execute(
        text("""
            INSERT INTO tts_routing_config (language, quality_tier, provider_primary, config)
            VALUES ('test-unique', 'standard', 'google_tts', '{"voice_id": "test"}')
            ON CONFLICT (language, quality_tier) DO UPDATE
                SET provider_primary = EXCLUDED.provider_primary
            RETURNING id
        """)
    )
    await test_db_session.commit()
    first_id = result.scalar()

    # Insert again (should update, not create duplicate)
    result = await test_db_session.execute(
        text("""
            INSERT INTO tts_routing_config (language, quality_tier, provider_primary, config)
            VALUES ('test-unique', 'standard', 'azure_tts', '{"voice_id": "test2"}')
            ON CONFLICT (language, quality_tier) DO UPDATE
                SET provider_primary = EXCLUDED.provider_primary
            RETURNING id
        """)
    )
    await test_db_session.commit()
    second_id = result.scalar()

    # IDs should be the same (updated, not created new)
    assert first_id == second_id

    # Cleanup
    await test_db_session.execute(
        text("DELETE FROM tts_routing_config WHERE language = 'test-unique'")
    )
    await test_db_session.commit()

    print(f"✅ Unique constraint validated (updated same row)")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_disabled_routing_config(test_db_session):
    """Test disabled routing configurations are not returned."""
    # Insert disabled config
    await test_db_session.execute(
        text("""
            INSERT INTO tts_routing_config (language, quality_tier, provider_primary, config, enabled)
            VALUES ('test-disabled', 'standard', 'google_tts', '{"voice_id": "test"}', FALSE)
            ON CONFLICT (language, quality_tier) DO UPDATE
                SET enabled = FALSE
        """)
    )
    await test_db_session.commit()

    # Query with enabled filter
    result = await test_db_session.execute(
        text("""
            SELECT provider_primary
            FROM tts_routing_config
            WHERE language = 'test-disabled' AND quality_tier = 'standard' AND enabled = TRUE
        """)
    )
    row = result.fetchone()

    # Should not find disabled config
    assert row is None

    # Cleanup
    await test_db_session.execute(
        text("DELETE FROM tts_routing_config WHERE language = 'test-disabled'")
    )
    await test_db_session.commit()

    print("✅ Disabled routing configs not returned")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tts_config_json_structure(test_db_session):
    """Test TTS config JSON structure validation."""
    # Get a sample config
    result = await test_db_session.execute(
        text("""
            SELECT config
            FROM tts_routing_config
            WHERE enabled = TRUE
            LIMIT 1
        """)
    )
    row = result.fetchone()

    if row:
        config = row[0]
        # Validate expected fields
        expected_fields = ["voice_id", "pitch", "speaking_rate"]
        for field in expected_fields:
            assert field in config, f"Missing field: {field}"

        print(f"✅ TTS config JSON validated: {list(config.keys())}")
