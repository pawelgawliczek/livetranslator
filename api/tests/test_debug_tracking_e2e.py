"""
End-to-end tests for admin debug tracking feature.

Tests the complete message lifecycle:
- Audio input → STT processing → MT translation → Debug API retrieval
"""

import pytest
import pytest_asyncio
import json
import os
import asyncio
import redis.asyncio as redis
from unittest.mock import AsyncMock, patch

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")


@pytest_asyncio.fixture
async def async_redis():
    """Create a Redis client for testing."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest.mark.e2e
class TestDebugTrackingE2E:
    """End-to-end tests for debug tracking through complete pipeline"""

    @pytest.mark.asyncio
    async def test_complete_message_debug_flow_polish_to_english(self, async_redis):
        """
        Test full pipeline: Polish audio → STT → MT (pl→en) → Debug API

        Flow:
        1. Send Polish audio (simulated)
        2. STT processes and creates debug info
        3. MT translates pl→en and appends to debug info
        4. Admin retrieves complete debug info via API
        """
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info, get_debug_info

        segment_id = 20001
        room_code = "test-e2e-room-1"

        # Step 1: Simulate STT processing (Speechmatics)
        stt_data = {
            "provider": "speechmatics",
            "language": "pl",
            "mode": "final",
            "latency_ms": 420,
            "audio_duration_sec": 3.8,
            "text": "Dzień dobry, jak się masz?"
        }
        stt_routing = {
            "routing_reason": "pl/final/standard → speechmatics (primary)",
            "fallback_triggered": False
        }

        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, stt_routing)

        # Step 2: Simulate MT processing (DeepL pl→en)
        mt_data = {
            "src_lang": "pl",
            "tgt_lang": "en",
            "provider": "deepl",
            "latency_ms": 180,
            "text": "Good morning, how are you?",
            "char_count": 27,
            "input_tokens": None,
            "output_tokens": None
        }
        mt_routing = {
            "routing_reason": "pl→en/standard → deepl (primary)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }

        await append_mt_debug_info(async_redis, room_code, segment_id, mt_data, mt_routing)

        # Step 3: Retrieve complete debug info
        debug_info = await get_debug_info(async_redis, room_code, segment_id)

        # Verify complete structure
        assert debug_info is not None
        assert debug_info["segment_id"] == segment_id
        assert debug_info["room_code"] == room_code

        # Verify STT data
        assert debug_info["stt"]["provider"] == "speechmatics"
        assert debug_info["stt"]["language"] == "pl"
        assert debug_info["stt"]["latency_ms"] == 420
        assert debug_info["stt"]["audio_duration_sec"] == 3.8
        assert debug_info["stt"]["text"] == "Dzień dobry, jak się masz?"
        assert debug_info["stt"]["cost_usd"] > 0

        # Verify MT data
        assert len(debug_info["mt"]) == 1
        assert debug_info["mt"][0]["provider"] == "deepl"
        assert debug_info["mt"][0]["src_lang"] == "pl"
        assert debug_info["mt"][0]["tgt_lang"] == "en"
        assert debug_info["mt"][0]["latency_ms"] == 180
        assert debug_info["mt"][0]["text"] == "Good morning, how are you?"
        assert debug_info["mt"][0]["cost_usd"] > 0

        # Verify totals
        assert debug_info["totals"]["stt_cost_usd"] > 0
        assert debug_info["totals"]["mt_cost_usd"] > 0
        assert debug_info["totals"]["total_cost_usd"] == \
               debug_info["totals"]["stt_cost_usd"] + debug_info["totals"]["mt_cost_usd"]
        assert debug_info["totals"]["mt_translations"] == 1


    @pytest.mark.asyncio
    async def test_multi_language_room_debug_tracking(self, async_redis):
        """
        Test debug tracking in room with multiple participants

        Scenario:
        - Room has 3 participants: Polish, English, Arabic speakers
        - Polish speaker says something
        - System translates to en and ar
        - Debug info should show 2 MT entries
        """
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info, get_debug_info

        segment_id = 20002
        room_code = "multi-lang-room"

        # STT: Polish input
        stt_data = {
            "provider": "google_v2",
            "language": "pl",
            "mode": "final",
            "latency_ms": 290,
            "audio_duration_sec": 2.5,
            "text": "Witam wszystkich"
        }
        stt_routing = {
            "routing_reason": "pl/final/standard → google_v2 (primary)",
            "fallback_triggered": False
        }
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, stt_routing)

        # MT 1: pl→en (Google Translate)
        mt_en_data = {
            "src_lang": "pl",
            "tgt_lang": "en",
            "provider": "google_translate",
            "latency_ms": 140,
            "text": "Welcome everyone",
            "char_count": 16,
            "input_tokens": None,
            "output_tokens": None
        }
        mt_en_routing = {
            "routing_reason": "pl→en/standard → google_translate (primary)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_en_data, mt_en_routing)

        # MT 2: pl→ar (GPT-4o-mini, throttled)
        mt_ar_data = {
            "src_lang": "pl",
            "tgt_lang": "ar",
            "provider": "gpt-4o-mini",
            "latency_ms": 1200,
            "text": "مرحبا بالجميع",
            "char_count": None,
            "input_tokens": 15,
            "output_tokens": 10
        }
        mt_ar_routing = {
            "routing_reason": "pl→ar/standard → gpt-4o-mini (primary)",
            "fallback_triggered": False,
            "throttled": True,
            "throttle_delay_ms": 2500,
            "throttle_reason": "Arabic partial throttling (max 1 req/2.5s)"
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_ar_data, mt_ar_routing)

        # Retrieve and verify
        debug_info = await get_debug_info(async_redis, room_code, segment_id)

        assert len(debug_info["mt"]) == 2
        assert debug_info["totals"]["mt_translations"] == 2

        # Verify first translation (en)
        assert debug_info["mt"][0]["tgt_lang"] == "en"
        assert debug_info["mt"][0]["provider"] == "google_translate"
        assert debug_info["mt"][0]["throttled"] is False

        # Verify second translation (ar)
        assert debug_info["mt"][1]["tgt_lang"] == "ar"
        assert debug_info["mt"][1]["provider"] == "gpt-4o-mini"
        assert debug_info["mt"][1]["throttled"] is True
        assert debug_info["mt"][1]["throttle_delay_ms"] == 2500


    @pytest.mark.asyncio
    async def test_streaming_mode_with_zero_latency(self, async_redis):
        """
        Test streaming STT mode shows zero latency

        Streaming STT is real-time, so latency_ms should be 0
        """
        from api.services.debug_tracker import create_stt_debug_info, get_debug_info

        segment_id = 20003
        room_code = "streaming-test-room"

        # Streaming STT (real-time, no discrete latency)
        stt_data = {
            "provider": "speechmatics",
            "language": "en",
            "mode": "streaming",
            "latency_ms": 0,  # Real-time streaming
            "audio_duration_sec": 5.2,
            "text": "This is a streaming transcription"
        }
        stt_routing = {
            "routing_reason": "en/streaming/standard → speechmatics (streaming)",
            "fallback_triggered": False
        }
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, stt_routing)

        # Verify
        debug_info = await get_debug_info(async_redis, room_code, segment_id)
        assert debug_info["stt"]["mode"] == "streaming"
        assert debug_info["stt"]["latency_ms"] == 0
        assert "streaming" in debug_info["stt"]["routing_reason"].lower()


    @pytest.mark.asyncio
    async def test_provider_fallback_captured_in_debug(self, async_redis):
        """
        Test that fallback scenario is captured correctly

        Scenario: Primary provider fails, fallback succeeds
        """
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info, get_debug_info

        segment_id = 20004
        room_code = "fallback-test-room"

        # STT with fallback triggered
        stt_data = {
            "provider": "azure",  # Fallback provider (primary was google_v2)
            "language": "en",
            "mode": "final",
            "latency_ms": 520,
            "audio_duration_sec": 3.0,
            "text": "Testing fallback scenario"
        }
        stt_routing = {
            "routing_reason": "en/final/standard → azure (fallback: google_v2 failed)",
            "fallback_triggered": True
        }
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, stt_routing)

        # MT with fallback triggered
        mt_data = {
            "src_lang": "en",
            "tgt_lang": "pl",
            "provider": "google_translate",  # Fallback (primary was deepl)
            "latency_ms": 210,
            "text": "Testowanie scenariusza powrotu",
            "char_count": 30,
            "input_tokens": None,
            "output_tokens": None
        }
        mt_routing = {
            "routing_reason": "en→pl/standard → google_translate (fallback: deepl failed)",
            "fallback_triggered": True,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_data, mt_routing)

        # Verify fallback flags
        debug_info = await get_debug_info(async_redis, room_code, segment_id)

        assert debug_info["stt"]["fallback_triggered"] is True
        assert "fallback" in debug_info["stt"]["routing_reason"].lower()

        assert debug_info["mt"][0]["fallback_triggered"] is True
        assert "fallback" in debug_info["mt"][0]["routing_reason"].lower()


    @pytest.mark.asyncio
    async def test_cached_translation_shows_zero_latency(self, async_redis):
        """
        Test that cached MT translations show 0ms latency

        Cached translations don't hit the API, so latency should be 0
        """
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info, get_debug_info

        segment_id = 20005
        room_code = "cache-test-room"

        # STT
        stt_data = {
            "provider": "speechmatics",
            "language": "pl",
            "mode": "final",
            "latency_ms": 350,
            "audio_duration_sec": 2.0,
            "text": "Test"
        }
        stt_routing = {
            "routing_reason": "pl/final/standard → speechmatics (primary)",
            "fallback_triggered": False
        }
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, stt_routing)

        # MT from cache
        mt_data = {
            "src_lang": "pl",
            "tgt_lang": "en",
            "provider": "deepl",
            "latency_ms": 0,  # Cache hit - no API call
            "text": "Test",
            "char_count": 4,
            "input_tokens": None,
            "output_tokens": None
        }
        mt_routing = {
            "routing_reason": "pl→en/standard → deepl (cached)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_data, mt_routing)

        # Verify
        debug_info = await get_debug_info(async_redis, room_code, segment_id)
        assert debug_info["mt"][0]["latency_ms"] == 0
        assert "cached" in debug_info["mt"][0]["routing_reason"]


    @pytest.mark.asyncio
    async def test_skip_reasons_appear_for_same_language(self, async_redis):
        """
        Test that skip reasons are shown when no translation is needed

        Scenario: User speaking Polish with language set to Polish
        """
        from api.services.debug_tracker import create_stt_debug_info, append_mt_skip_reason, get_debug_info

        segment_id = 20006
        room_code = "skip-reason-room"

        # STT
        stt_data = {
            "provider": "speechmatics",
            "language": "pl",
            "mode": "streaming",
            "latency_ms": 0,
            "audio_duration_sec": 1.8,
            "text": "Cześć"
        }
        stt_routing = {
            "routing_reason": "pl/streaming/standard → speechmatics (streaming)",
            "fallback_triggered": False
        }
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, stt_routing)

        # Skip reason: pl→pl (same language)
        await append_mt_skip_reason(
            redis=async_redis,
            room_code=room_code,
            segment_id=segment_id,
            src_lang="pl",
            tgt_lang="pl",
            reason="No translation needed - source and target are both 'pl'"
        )

        # Verify
        debug_info = await get_debug_info(async_redis, room_code, segment_id)
        assert len(debug_info["mt"]) == 0  # No translations
        assert len(debug_info["mt_skip_reasons"]) == 1
        assert debug_info["mt_skip_reasons"][0]["src_lang"] == "pl"
        assert debug_info["mt_skip_reasons"][0]["tgt_lang"] == "pl"
        assert "No translation needed" in debug_info["mt_skip_reasons"][0]["reason"]


    @pytest.mark.asyncio
    async def test_cost_calculations_accurate_across_providers(self, async_redis):
        """
        Test that cost calculations are accurate for different provider types

        Tests:
        - Character-based pricing (DeepL, Google)
        - Token-based pricing (GPT-4o-mini)
        - Per-second pricing (Speechmatics STT)
        """
        from api.services.debug_tracker import create_stt_debug_info, append_mt_debug_info, get_debug_info

        segment_id = 20007
        room_code = "cost-test-room"

        # STT: Speechmatics (per-second pricing: $0.00012/sec)
        stt_data = {
            "provider": "speechmatics",
            "language": "en",
            "mode": "final",
            "latency_ms": 400,
            "audio_duration_sec": 10.0,  # 10 seconds
            "text": "Testing cost calculations"
        }
        stt_routing = {"routing_reason": "en/final/standard → speechmatics (primary)", "fallback_triggered": False}
        await create_stt_debug_info(async_redis, segment_id, room_code, stt_data, stt_routing)

        # MT 1: DeepL (character-based: $20/1M chars)
        mt_deepl_data = {
            "src_lang": "en",
            "tgt_lang": "pl",
            "provider": "deepl",
            "latency_ms": 180,
            "text": "Testowanie obliczeń kosztów",
            "char_count": 1000,  # 1000 chars
            "input_tokens": None,
            "output_tokens": None
        }
        mt_deepl_routing = {
            "routing_reason": "en→pl/standard → deepl (primary)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_deepl_data, mt_deepl_routing)

        # MT 2: GPT-4o-mini (token-based)
        mt_gpt_data = {
            "src_lang": "en",
            "tgt_lang": "ar",
            "provider": "gpt-4o-mini",
            "latency_ms": 950,
            "text": "اختبار حسابات التكلفة",
            "char_count": None,
            "input_tokens": 25,  # $0.00015/1k input
            "output_tokens": 15   # $0.0006/1k output
        }
        mt_gpt_routing = {
            "routing_reason": "en→ar/standard → gpt-4o-mini (primary)",
            "fallback_triggered": False,
            "throttled": False,
            "throttle_delay_ms": 0,
            "throttle_reason": None
        }
        await append_mt_debug_info(async_redis, room_code, segment_id, mt_gpt_data, mt_gpt_routing)

        # Verify costs
        debug_info = await get_debug_info(async_redis, room_code, segment_id)

        # STT cost: 10 sec * $0.00012/sec = $0.0012
        expected_stt_cost = 10.0 * 0.00012
        assert abs(debug_info["stt"]["cost_usd"] - expected_stt_cost) < 0.0000001

        # DeepL cost: 1000 chars * $20/1M = $0.00002
        expected_deepl_cost = 1000 * (20.0 / 1_000_000)
        assert abs(debug_info["mt"][0]["cost_usd"] - expected_deepl_cost) < 0.0000001

        # GPT-4o-mini cost: (25 * 0.00015 / 1000) + (15 * 0.0006 / 1000)
        expected_gpt_cost = (25 * 0.00015 / 1000) + (15 * 0.0006 / 1000)
        assert abs(debug_info["mt"][1]["cost_usd"] - expected_gpt_cost) < 0.00000001

        # Total cost
        total_expected = expected_stt_cost + expected_deepl_cost + expected_gpt_cost
        assert abs(debug_info["totals"]["total_cost_usd"] - total_expected) < 0.00000001
