"""
Unit tests for api/services/debug_tracker.py

Tests debug tracking functions:
- calculate_stt_cost() - STT cost calculation for various providers
- calculate_mt_cost() - MT cost calculation for character/token-based providers
- create_stt_debug_info() - Create initial debug info with STT data
- append_mt_debug_info() - Append MT translation data
- get_debug_info() - Retrieve debug info from Redis
"""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from api.services.debug_tracker import (
    calculate_stt_cost,
    calculate_mt_cost,
    create_stt_debug_info,
    append_mt_debug_info,
    get_debug_info,
    STT_PRICING,
    MT_PRICING,
    DEBUG_TTL_SECONDS
)


@pytest.mark.unit
class TestCalculateSTTCost:
    """Tests for calculate_stt_cost() function."""

    def test_speechmatics_cost_calculation(self):
        """Test Speechmatics STT cost ($0.50/hour = $0.00012/sec)."""
        # 3.5 seconds at $0.00012/sec
        cost = calculate_stt_cost("speechmatics", 3.5)

        # 3.5 * 0.00012 = 0.00042
        assert abs(cost - 0.00042) < 0.0000001

    def test_google_v2_cost_calculation(self):
        """Test Google V2 STT cost ($0.006/minute = $0.0001/sec)."""
        # 60 seconds (1 minute)
        cost = calculate_stt_cost("google_v2", 60.0)

        # 60 * 0.0001 = 0.006
        assert abs(cost - 0.006) < 0.0001

    def test_azure_cost_calculation(self):
        """Test Azure STT cost ($1/1000 seconds = $0.001/sec)."""
        # 10 seconds
        cost = calculate_stt_cost("azure", 10.0)

        # 10 * 0.001 = 0.01
        assert abs(cost - 0.01) < 0.001

    def test_soniox_cost_calculation(self):
        """Test Soniox STT cost (budget option: $0.00003/sec)."""
        # 100 seconds
        cost = calculate_stt_cost("soniox", 100.0)

        # 100 * 0.00003 = 0.003
        assert abs(cost - 0.003) < 0.0001

    def test_openai_cost_calculation(self):
        """Test OpenAI STT cost ($0.006/minute)."""
        # 120 seconds (2 minutes)
        cost = calculate_stt_cost("openai", 120.0)

        # 2 * 0.006 = 0.012
        assert abs(cost - 0.012) < 0.001

    def test_local_cost_is_zero(self):
        """Test local STT (Whisper) has zero cost."""
        cost = calculate_stt_cost("local", 60.0)

        assert cost == 0.0

    def test_unknown_provider_returns_zero(self):
        """Test unknown provider returns $0 and prints warning."""
        cost = calculate_stt_cost("unknown_provider", 60.0)

        assert cost == 0.0

    def test_zero_duration(self):
        """Test zero duration returns zero cost."""
        cost = calculate_stt_cost("speechmatics", 0.0)

        assert cost == 0.0

    @pytest.mark.parametrize("provider,duration,expected", [
        ("speechmatics", 3.5, 0.00042),
        ("google_v2", 60.0, 0.006),
        ("azure", 10.0, 0.01),
        ("soniox", 100.0, 0.003),
        ("openai", 120.0, 0.012),
        ("local", 1000.0, 0.0),
    ])
    def test_various_providers_and_durations(self, provider, duration, expected):
        """Test STT cost calculation with various providers and durations."""
        cost = calculate_stt_cost(provider, duration)

        assert abs(cost - expected) < 0.0001


@pytest.mark.unit
class TestCalculateMTCost:
    """Tests for calculate_mt_cost() function."""

    def test_deepl_character_cost(self):
        """Test DeepL MT cost (character-based: $20/1M chars)."""
        # 500 characters
        result = calculate_mt_cost("deepl", 500, "characters")

        # 500 / 1_000_000 * 20 = 0.01
        assert abs(result["cost_usd"] - 0.01) < 0.001
        assert result["cost_breakdown"]["unit_type"] == "characters"
        assert result["cost_breakdown"]["units"] == 500

    def test_azure_translator_cost(self):
        """Test Azure Translator cost ($10/1M chars)."""
        # 1000 characters
        result = calculate_mt_cost("azure_translator", 1000, "characters")

        # 1000 / 1_000_000 * 10 = 0.01
        assert abs(result["cost_usd"] - 0.01) < 0.001

    def test_google_translate_cost(self):
        """Test Google Translate cost ($20/1M chars)."""
        # 250 characters
        result = calculate_mt_cost("google_translate", 250, "characters")

        # 250 / 1_000_000 * 20 = 0.005
        assert abs(result["cost_usd"] - 0.005) < 0.001

    def test_gpt4o_mini_token_cost(self):
        """Test GPT-4o-mini token-based cost."""
        # 28 input tokens, 15 output tokens
        result = calculate_mt_cost(
            "gpt-4o-mini", 43, "tokens",
            input_tokens=28, output_tokens=15
        )

        # (28/1000 * 0.00015) + (15/1000 * 0.0006)
        # = 0.0000042 + 0.000009 = 0.0000132
        assert abs(result["cost_usd"] - 0.0000132) < 0.0000001
        assert result["cost_breakdown"]["unit_type"] == "tokens"
        assert result["cost_breakdown"]["input_tokens"] == 28
        assert result["cost_breakdown"]["output_tokens"] == 15

    def test_gpt4o_token_cost(self):
        """Test GPT-4o token-based cost (more expensive)."""
        # 100 input tokens, 50 output tokens
        result = calculate_mt_cost(
            "gpt-4o", 150, "tokens",
            input_tokens=100, output_tokens=50
        )

        # (100/1000 * 0.005) + (50/1000 * 0.015)
        # = 0.0005 + 0.00075 = 0.00125
        assert abs(result["cost_usd"] - 0.00125) < 0.00001

    def test_unknown_provider_returns_zero(self):
        """Test unknown provider returns $0."""
        result = calculate_mt_cost("unknown_provider", 100, "characters")

        assert result["cost_usd"] == 0.0

    def test_zero_characters(self):
        """Test zero characters returns zero cost."""
        result = calculate_mt_cost("deepl", 0, "characters")

        assert result["cost_usd"] == 0.0

    def test_zero_tokens(self):
        """Test zero tokens returns zero cost."""
        result = calculate_mt_cost(
            "gpt-4o-mini", 0, "tokens",
            input_tokens=0, output_tokens=0
        )

        assert result["cost_usd"] == 0.0

    @pytest.mark.parametrize("provider,units,unit_type,input_tok,output_tok,expected", [
        ("deepl", 500, "characters", 0, 0, 0.01),
        ("azure_translator", 1000, "characters", 0, 0, 0.01),
        ("gpt-4o-mini", 43, "tokens", 28, 15, 0.0000132),
        ("gpt-4o", 150, "tokens", 100, 50, 0.00125),
    ])
    def test_various_providers_and_units(self, provider, units, unit_type, input_tok, output_tok, expected):
        """Test MT cost calculation with various providers."""
        result = calculate_mt_cost(provider, units, unit_type, input_tok, output_tok)

        assert abs(result["cost_usd"] - expected) < 0.0001


@pytest.mark.unit
class TestCreateSTTDebugInfo:
    """Tests for create_stt_debug_info() function."""

    @pytest.mark.asyncio
    async def test_creates_debug_info_structure(self):
        """Test creating complete debug info structure."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        stt_data = {
            "provider": "speechmatics",
            "language": "pl-PL",
            "mode": "final",
            "latency_ms": 234,
            "audio_duration_sec": 3.5,
            "text": "Dzień dobry wszystkim"
        }

        routing_info = {
            "routing_reason": "pl-PL/final/standard → speechmatics (primary)",
            "fallback_triggered": False
        }

        await create_stt_debug_info(
            mock_redis, 123, "abc123", stt_data, routing_info
        )

        # Verify Redis set was called
        mock_redis.set.assert_called_once()

        # Extract the call arguments
        call_args = mock_redis.set.call_args
        key = call_args[0][0]
        data_json = call_args[0][1]
        ttl = call_args[1]["ex"]

        # Verify key format (includes room_code to prevent collisions)
        assert key == "debug:abc123:segment:123"

        # Verify TTL
        assert ttl == DEBUG_TTL_SECONDS

        # Parse and verify data structure
        data = json.loads(data_json)
        assert data["segment_id"] == 123
        assert data["room_code"] == "abc123"
        assert "timestamp" in data

        # Verify STT section
        assert data["stt"]["provider"] == "speechmatics"
        assert data["stt"]["language"] == "pl-PL"
        assert data["stt"]["mode"] == "final"
        assert data["stt"]["latency_ms"] == 234
        assert data["stt"]["audio_duration_sec"] == 3.5
        assert abs(data["stt"]["cost_usd"] - 0.00042) < 0.0000001
        assert data["stt"]["routing_reason"] == "pl-PL/final/standard → speechmatics (primary)"
        assert data["stt"]["fallback_triggered"] is False
        assert data["stt"]["text"] == "Dzień dobry wszystkim"

        # Verify empty MT array
        assert data["mt"] == []

        # Verify totals
        assert abs(data["totals"]["stt_cost_usd"] - 0.00042) < 0.0000001
        assert data["totals"]["mt_cost_usd"] == 0.0
        assert abs(data["totals"]["total_cost_usd"] - 0.00042) < 0.0000001
        assert data["totals"]["mt_translations"] == 0

    @pytest.mark.asyncio
    async def test_handles_redis_failure_gracefully(self):
        """Test that Redis failures don't raise exceptions."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(side_effect=Exception("Redis connection failed"))

        stt_data = {
            "provider": "speechmatics",
            "language": "pl-PL",
            "mode": "final",
            "latency_ms": 234,
            "audio_duration_sec": 3.5,
            "text": "Test"
        }

        routing_info = {
            "routing_reason": "test",
            "fallback_triggered": False
        }

        # Should not raise exception
        await create_stt_debug_info(
            mock_redis, 123, "abc123", stt_data, routing_info
        )

    @pytest.mark.asyncio
    async def test_cost_breakdown_calculation(self):
        """Test STT cost breakdown is calculated correctly."""
        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock()

        stt_data = {
            "provider": "google_v2",
            "language": "en-US",
            "mode": "final",
            "latency_ms": 150,
            "audio_duration_sec": 60.0,
            "text": "Hello world"
        }

        routing_info = {
            "routing_reason": "en-US/final/standard → google_v2 (primary)",
            "fallback_triggered": False
        }

        await create_stt_debug_info(
            mock_redis, 456, "test123", stt_data, routing_info
        )

        # Extract data
        call_args = mock_redis.set.call_args
        data = json.loads(call_args[0][1])

        # Verify cost breakdown
        breakdown = data["stt"]["cost_breakdown"]
        assert breakdown["unit_type"] == "seconds"
        assert breakdown["units"] == 60.0
        assert abs(breakdown["rate_per_unit"] - 0.0001) < 0.00001


@pytest.mark.unit
class TestAppendMTDebugInfo:
    """Tests for append_mt_debug_info() function."""

    @pytest.mark.asyncio
    async def test_appends_mt_translation_to_existing_data(self):
        """Test appending MT data to existing STT debug info."""
        # Prepare existing debug info
        existing_data = {
            "segment_id": 123,
            "room_code": "abc123",
            "timestamp": "2025-10-28T14:00:00.000Z",
            "stt": {
                "provider": "speechmatics",
                "cost_usd": 0.00042
            },
            "mt": [],
            "totals": {
                "stt_cost_usd": 0.00042,
                "mt_cost_usd": 0.0,
                "total_cost_usd": 0.00042,
                "mt_translations": 0
            }
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_data))
        mock_redis.set = AsyncMock()

        mt_data = {
            "src_lang": "pl",
            "tgt_lang": "en",
            "provider": "deepl",
            "latency_ms": 89,
            "text": "Good morning everyone",
            "char_count": 22,
            "input_tokens": None,
            "output_tokens": None
        }

        routing_info = {
            "routing_reason": "pl→en/standard → deepl (primary)",
            "fallback_triggered": False,
            "throttled": False
        }

        await append_mt_debug_info(
            mock_redis, "abc123", 123, mt_data, routing_info
        )

        # Verify Redis get was called (includes room_code to prevent collisions)
        mock_redis.get.assert_called_once_with("debug:abc123:segment:123")

        # Verify Redis set was called
        mock_redis.set.assert_called_once()

        # Extract updated data
        call_args = mock_redis.set.call_args
        updated_data = json.loads(call_args[0][1])

        # Verify MT array has one entry
        assert len(updated_data["mt"]) == 1

        # Verify MT entry
        mt_entry = updated_data["mt"][0]
        assert mt_entry["src_lang"] == "pl"
        assert mt_entry["tgt_lang"] == "en"
        assert mt_entry["provider"] == "deepl"
        assert mt_entry["latency_ms"] == 89
        assert mt_entry["text"] == "Good morning everyone"
        assert mt_entry["throttled"] is False

        # Verify cost calculation (22 chars at $20/1M = 0.00044)
        assert abs(mt_entry["cost_usd"] - 0.00044) < 0.00001

        # Verify totals updated
        assert updated_data["totals"]["mt_translations"] == 1
        assert abs(updated_data["totals"]["mt_cost_usd"] - 0.00044) < 0.00001
        assert abs(updated_data["totals"]["total_cost_usd"] - 0.00086) < 0.00001

    @pytest.mark.asyncio
    async def test_appends_multiple_translations(self):
        """Test appending multiple MT translations."""
        # First translation already exists
        existing_data = {
            "segment_id": 123,
            "room_code": "abc123",
            "timestamp": "2025-10-28T14:00:00.000Z",
            "stt": {"provider": "speechmatics", "cost_usd": 0.00042},
            "mt": [
                {
                    "src_lang": "pl",
                    "tgt_lang": "en",
                    "provider": "deepl",
                    "cost_usd": 0.00044
                }
            ],
            "totals": {
                "stt_cost_usd": 0.00042,
                "mt_cost_usd": 0.00044,
                "total_cost_usd": 0.00086,
                "mt_translations": 1
            }
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_data))
        mock_redis.set = AsyncMock()

        # Second translation (pl→ar with GPT-4o-mini)
        mt_data = {
            "src_lang": "pl",
            "tgt_lang": "ar",
            "provider": "gpt-4o-mini",
            "latency_ms": 2756,
            "text": "صباح الخير للجميع",
            "char_count": None,
            "input_tokens": 28,
            "output_tokens": 15
        }

        routing_info = {
            "routing_reason": "pl→ar/standard → gpt-4o-mini (primary)",
            "fallback_triggered": False,
            "throttled": True,
            "throttle_delay_ms": 2300,
            "throttle_reason": "Arabic partial throttling (max 1 req/2.5s)"
        }

        await append_mt_debug_info(
            mock_redis, "abc123", 123, mt_data, routing_info
        )

        # Extract updated data
        call_args = mock_redis.set.call_args
        updated_data = json.loads(call_args[0][1])

        # Verify MT array has two entries
        assert len(updated_data["mt"]) == 2

        # Verify second entry
        mt_entry = updated_data["mt"][1]
        assert mt_entry["src_lang"] == "pl"
        assert mt_entry["tgt_lang"] == "ar"
        assert mt_entry["provider"] == "gpt-4o-mini"
        assert mt_entry["throttled"] is True
        assert mt_entry["throttle_delay_ms"] == 2300
        assert mt_entry["throttle_reason"] == "Arabic partial throttling (max 1 req/2.5s)"

        # Verify totals updated
        assert updated_data["totals"]["mt_translations"] == 2

    @pytest.mark.asyncio
    async def test_handles_missing_segment_gracefully(self):
        """Test that missing segment doesn't raise exception."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        mt_data = {
            "src_lang": "pl",
            "tgt_lang": "en",
            "provider": "deepl",
            "latency_ms": 89,
            "text": "Test",
            "char_count": 4
        }

        routing_info = {
            "routing_reason": "test",
            "fallback_triggered": False,
            "throttled": False
        }

        # Should not raise exception
        await append_mt_debug_info(
            mock_redis, "test999", 999, mt_data, routing_info
        )

    @pytest.mark.asyncio
    async def test_token_based_cost_breakdown(self):
        """Test token-based MT cost breakdown."""
        existing_data = {
            "segment_id": 123,
            "room_code": "abc123",
            "timestamp": "2025-10-28T14:00:00.000Z",
            "stt": {"provider": "speechmatics", "cost_usd": 0.00042},
            "mt": [],
            "totals": {
                "stt_cost_usd": 0.00042,
                "mt_cost_usd": 0.0,
                "total_cost_usd": 0.00042,
                "mt_translations": 0
            }
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(existing_data))
        mock_redis.set = AsyncMock()

        mt_data = {
            "src_lang": "en",
            "tgt_lang": "fr",
            "provider": "gpt-4o-mini",
            "latency_ms": 450,
            "text": "Bonjour",
            "char_count": None,
            "input_tokens": 10,
            "output_tokens": 5
        }

        routing_info = {
            "routing_reason": "en→fr/standard → gpt-4o-mini (primary)",
            "fallback_triggered": False,
            "throttled": False
        }

        await append_mt_debug_info(
            mock_redis, "abc123", 123, mt_data, routing_info
        )

        # Extract updated data
        call_args = mock_redis.set.call_args
        updated_data = json.loads(call_args[0][1])

        # Verify cost breakdown
        breakdown = updated_data["mt"][0]["cost_breakdown"]
        assert breakdown["unit_type"] == "tokens"
        assert breakdown["input_tokens"] == 10
        assert breakdown["output_tokens"] == 5


@pytest.mark.unit
class TestGetDebugInfo:
    """Tests for get_debug_info() function."""

    @pytest.mark.asyncio
    async def test_retrieves_existing_debug_info(self):
        """Test retrieving existing debug info from Redis."""
        debug_data = {
            "segment_id": 123,
            "room_code": "abc123",
            "stt": {"provider": "speechmatics"},
            "mt": []
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(debug_data))

        result = await get_debug_info(mock_redis, "abc123", 123)

        # Verify Redis get was called (includes room_code to prevent collisions)
        mock_redis.get.assert_called_once_with("debug:abc123:segment:123")

        # Verify returned data
        assert result is not None
        assert result["segment_id"] == 123
        assert result["room_code"] == "abc123"

    @pytest.mark.asyncio
    async def test_returns_none_for_missing_segment(self):
        """Test returns None when segment not found."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)

        result = await get_debug_info(mock_redis, "test999", 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_redis_failure_gracefully(self):
        """Test that Redis failures return None."""
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(side_effect=Exception("Redis connection failed"))

        result = await get_debug_info(mock_redis, "abc123", 123)

        assert result is None

    @pytest.mark.asyncio
    async def test_parses_json_correctly(self):
        """Test JSON parsing of complex debug info."""
        debug_data = {
            "segment_id": 789,
            "room_code": "test456",
            "timestamp": "2025-10-28T14:32:18.456Z",
            "stt": {
                "provider": "google_v2",
                "language": "en-US",
                "cost_usd": 0.006
            },
            "mt": [
                {
                    "src_lang": "en",
                    "tgt_lang": "es",
                    "provider": "deepl",
                    "cost_usd": 0.0005
                }
            ],
            "totals": {
                "stt_cost_usd": 0.006,
                "mt_cost_usd": 0.0005,
                "total_cost_usd": 0.0065,
                "mt_translations": 1
            }
        }

        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=json.dumps(debug_data))

        result = await get_debug_info(mock_redis, "test456", 789)

        # Verify complete structure
        assert result["segment_id"] == 789
        assert result["stt"]["provider"] == "google_v2"
        assert len(result["mt"]) == 1
        assert result["totals"]["mt_translations"] == 1


@pytest.mark.unit
class TestPricingConstants:
    """Tests to verify pricing constants are defined correctly."""

    def test_stt_pricing_has_all_providers(self):
        """Test STT_PRICING includes all expected providers."""
        expected_providers = [
            "speechmatics", "google_v2", "azure",
            "soniox", "openai", "local"
        ]

        for provider in expected_providers:
            assert provider in STT_PRICING

    def test_mt_pricing_has_all_providers(self):
        """Test MT_PRICING includes all expected providers."""
        expected_providers = [
            "deepl", "azure_translator", "google_translate",
            "gpt-4o-mini", "gpt-4o"
        ]

        for provider in expected_providers:
            assert provider in MT_PRICING

    def test_ttl_is_24_hours(self):
        """Test DEBUG_TTL_SECONDS is 24 hours."""
        assert DEBUG_TTL_SECONDS == 86400
