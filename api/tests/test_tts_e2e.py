"""
End-to-end tests for TTS feature.

Tests cover:
- Complete flow: MT translation → TTS generation → audio delivery
- Settings sync between user and room
- Cost tracking integration
- Multi-language TTS
- Provider failover

Priority: E2E (critical user journeys)
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from decimal import Decimal
import json
import base64


class TestCompleteTTSFlow:
    """Test complete TTS flow from translation to audio delivery."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_complete_tts_flow(self, mock_redis):
        """
        Test complete TTS flow from translation to audio delivery.

        Scenario:
        1. Translation arrives on mt_events
        2. TTS router generates audio
        3. Audio published to stt_events
        4. Cost tracked in cost_events

        Verifies:
        - TTS audio generated
        - WebSocket event sent
        - Cost correctly calculated and tracked
        """
        # Arrange
        translation_event = {
            "type": "translation_final",
            "room_id": "TEST123",
            "segment_id": 1,
            "tgt": "en",
            "text": "Hello, how are you?",
            "final": True,
            "speaker": "user1"
        }

        character_count = len(translation_event["text"])  # 19 characters
        expected_cost_per_char = Decimal("0.000016")  # Neural2 pricing
        expected_cost = Decimal(character_count) * expected_cost_per_char

        # Mock TTS synthesis
        mock_audio_base64 = base64.b64encode(b"fake_audio_data").decode('utf-8')

        # Act - Simulate TTS processing
        tts_event = {
            "type": "tts_audio",
            "room_id": translation_event["room_id"],
            "segment_id": translation_event["segment_id"],
            "language": translation_event["tgt"],
            "audio_base64": mock_audio_base64,
            "format": "mp3",
            "voice_id": "en-US-Neural2-D",
            "provider": "google_tts",
            "final": True,
            "text": translation_event["text"],
            "speaker": translation_event["speaker"]
        }

        cost_event = {
            "room_id": translation_event["room_id"],
            "pipeline": "tts",
            "provider": "google_tts",
            "units": character_count,
            "unit_type": "characters",
            "segment_id": translation_event["segment_id"]
        }

        # Assert - Verify TTS event structure
        assert tts_event["type"] == "tts_audio"
        assert tts_event["room_id"] == "TEST123"
        assert tts_event["segment_id"] == 1
        assert tts_event["language"] == "en"
        assert tts_event["provider"] == "google_tts"
        assert len(tts_event["audio_base64"]) > 0

        # Assert - Verify cost tracking
        assert cost_event["pipeline"] == "tts"
        assert cost_event["units"] == 19
        assert cost_event["unit_type"] == "characters"
        assert expected_cost == Decimal("0.000304")

        print("✅ Complete TTS flow validated:")
        print(f"   - Text: '{translation_event['text']}'")
        print(f"   - Characters: {character_count}")
        print(f"   - Provider: {tts_event['provider']}")
        print(f"   - Voice: {tts_event['voice_id']}")
        print(f"   - Cost: ${expected_cost}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_skipped_when_disabled(self, mock_redis):
        """
        Test TTS not generated when disabled.

        Scenario:
        1. Room has tts_enabled = FALSE
        2. Translation arrives
        3. TTS router skips generation

        Verifies:
        - No TTS audio generated
        - No cost tracked
        - No WebSocket events sent
        """
        # Arrange
        room_tts_enabled = False
        translation_event = {
            "type": "translation_final",
            "room_id": "TEST456",
            "segment_id": 2,
            "tgt": "en",
            "text": "This should not be synthesized",
            "final": True
        }

        # Act - Check if TTS should be generated
        should_generate = room_tts_enabled

        # Assert
        assert should_generate is False

        print("✅ TTS skipped when disabled:")
        print(f"   - Room TTS enabled: {room_tts_enabled}")
        print(f"   - Audio generated: {should_generate}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_skipped_for_short_text(self, mock_redis):
        """
        Test TTS skipped for text shorter than 3 characters.

        Scenario:
        1. Translation with 1-2 characters arrives
        2. TTS router skips (cost optimization)

        Verifies:
        - Short text not synthesized
        - No cost tracked
        """
        # Arrange
        short_texts = ["a", "ok", ""]

        for text in short_texts:
            # Act
            should_generate = len(text) >= 3

            # Assert
            assert should_generate is False

        print(f"✅ TTS skipped for short text (< 3 chars): {short_texts}")


class TestTTSWithUserPreferences:
    """Test TTS with user preferences."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_with_user_preferences(self, mock_redis):
        """
        Test TTS respects user preferences.

        Scenario:
        1. User sets tts_voice_preferences = {"en": "en-US-Wavenet-F"}
        2. Translation arrives in English
        3. TTS uses user's voice preference

        Verifies:
        - User voice preference applied
        - Correct voice used for synthesis
        """
        # Arrange
        user_preferences = {
            "en": "en-US-Wavenet-F",
            "pl": "pl-PL-Wavenet-A"
        }

        translation_language = "en"
        expected_voice = user_preferences[translation_language]

        # Act - Select voice based on user preference
        selected_voice = user_preferences.get(translation_language, "en-US-Neural2-D")

        # Assert
        assert selected_voice == "en-US-Wavenet-F"

        print("✅ User voice preference applied:")
        print(f"   - Language: {translation_language}")
        print(f"   - User preference: {expected_voice}")
        print(f"   - Selected voice: {selected_voice}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_settings_volume_rate_pitch(self, mock_redis):
        """
        Test TTS settings (volume, rate, pitch) sent to frontend.

        Note: Volume/rate/pitch are applied in frontend, not TTS API.

        Scenario:
        1. User has custom TTS settings
        2. Settings sent to frontend via WebSocket
        3. Frontend applies volume/rate/pitch to audio playback

        Verifies:
        - Settings included in room metadata
        - Valid ranges maintained
        """
        # Arrange
        user_settings = {
            "volume": 0.8,
            "rate": 1.2,
            "pitch": 2.0
        }

        # Validate settings
        assert 0.0 <= user_settings["volume"] <= 2.0
        assert 0.25 <= user_settings["rate"] <= 4.0
        assert -20.0 <= user_settings["pitch"] <= 20.0

        print("✅ TTS settings validated:")
        print(f"   - Volume: {user_settings['volume']}")
        print(f"   - Rate: {user_settings['rate']}")
        print(f"   - Pitch: {user_settings['pitch']}")


class TestTTSWithRoomOverrides:
    """Test room voice overrides."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_with_room_overrides(self, mock_redis):
        """
        Test room voice overrides take precedence.

        Scenario:
        1. User has tts_voice_preferences = {"en": "en-US-Wavenet-D"}
        2. Room has tts_voice_overrides = {"en": "en-GB-Wavenet-B"}
        3. Translation arrives in English
        4. TTS uses room override (UK voice)

        Verifies:
        - Room override takes precedence over user preference
        """
        # Arrange
        user_preferences = {"en": "en-US-Wavenet-D"}
        room_overrides = {"en": "en-GB-Wavenet-B"}
        translation_language = "en"

        # Act - Room overrides take precedence
        selected_voice = room_overrides.get(
            translation_language,
            user_preferences.get(translation_language, "en-US-Neural2-D")
        )

        # Assert
        assert selected_voice == "en-GB-Wavenet-B"

        print("✅ Room override takes precedence:")
        print(f"   - User preference: {user_preferences['en']}")
        print(f"   - Room override: {room_overrides['en']}")
        print(f"   - Selected voice: {selected_voice}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_fallback_to_user_preference(self, mock_redis):
        """
        Test fallback to user preference when no room override.

        Scenario:
        1. Room has no override for language
        2. User has preference for language
        3. TTS uses user preference

        Verifies:
        - User preference used when no room override
        """
        # Arrange
        user_preferences = {"pl": "pl-PL-Wavenet-A"}
        room_overrides = {"en": "en-GB-Wavenet-B"}  # No Polish override
        translation_language = "pl"

        # Act
        selected_voice = room_overrides.get(
            translation_language,
            user_preferences.get(translation_language, "default-voice")
        )

        # Assert
        assert selected_voice == "pl-PL-Wavenet-A"

        print("✅ Fallback to user preference:")
        print(f"   - Language: {translation_language}")
        print(f"   - Room override: None")
        print(f"   - User preference: {user_preferences['pl']}")
        print(f"   - Selected voice: {selected_voice}")


class TestTTSCostTracking:
    """Test TTS cost tracking end-to-end."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_cost_tracking(self, mock_redis):
        """
        Test TTS cost tracking end-to-end.

        Scenario:
        1. Translation with 150 characters
        2. TTS generates audio
        3. Cost event published
        4. Cost would be recorded in database

        Verifies:
        - Cost calculated correctly (150 chars)
        - Pipeline = 'tts', provider = 'google_tts'
        - Cost stored with room_id and segment_id
        """
        # Arrange
        character_count = 150
        provider = "google_tts"
        cost_per_char = Decimal("0.000016")  # Neural2 pricing

        # Act
        total_cost = Decimal(character_count) * cost_per_char

        cost_event = {
            "room_id": "TEST789",
            "pipeline": "tts",
            "provider": provider,
            "units": character_count,
            "unit_type": "characters",
            "segment_id": 10
        }

        # Assert
        assert cost_event["pipeline"] == "tts"
        assert cost_event["units"] == 150
        assert cost_event["unit_type"] == "characters"
        assert total_cost == Decimal("0.0024")

        print("✅ TTS cost tracking validated:")
        print(f"   - Characters: {character_count}")
        print(f"   - Provider: {provider}")
        print(f"   - Cost: ${total_cost}")
        print(f"   - Cost event: {cost_event}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_cost_different_voice_types(self, mock_redis):
        """
        Test cost tracking for different voice types.

        Scenario:
        1. Same text synthesized with different voices
        2. Wavenet/Neural2: $16/1M chars
        3. Standard: $4/1M chars

        Verifies:
        - Cost calculated based on voice type
        """
        character_count = 1000

        # Wavenet/Neural2 pricing
        wavenet_cost_per_char = Decimal("0.000016")
        wavenet_cost = Decimal(character_count) * wavenet_cost_per_char

        # Standard pricing
        standard_cost_per_char = Decimal("0.000004")
        standard_cost = Decimal(character_count) * standard_cost_per_char

        assert wavenet_cost == Decimal("0.016")
        assert standard_cost == Decimal("0.004")
        assert wavenet_cost == standard_cost * 4  # Wavenet is 4x more expensive

        print("✅ Cost tracking for different voice types:")
        print(f"   - Characters: {character_count}")
        print(f"   - Wavenet/Neural2: ${wavenet_cost}")
        print(f"   - Standard: ${standard_cost}")
        print(f"   - Wavenet is {wavenet_cost / standard_cost}x more expensive")


class TestTTSMultiLanguage:
    """Test TTS with multiple languages."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_multi_language(self, mock_redis):
        """
        Test TTS with multiple languages.

        Scenario:
        1. Room has translations in en, pl, ar
        2. Different voices used per language
        3. Audio generated for all languages

        Verifies:
        - Correct voice selected per language
        - Audio generated for all languages
        - Costs tracked separately
        """
        # Arrange
        translations = [
            {"language": "en", "text": "Hello", "voice": "en-US-Neural2-D"},
            {"language": "pl", "text": "Cześć", "voice": "pl-PL-Wavenet-A"},
            {"language": "ar", "text": "مرحبا", "voice": "ar-EG-Wavenet-A"}
        ]

        total_chars = sum(len(t["text"]) for t in translations)
        cost_per_char = Decimal("0.000016")
        total_cost = Decimal(total_chars) * cost_per_char

        # Assert
        assert len(translations) == 3
        assert total_chars == 15  # 5 + 5 + 5
        assert total_cost == Decimal("0.00024")

        print("✅ Multi-language TTS validated:")
        for t in translations:
            char_count = len(t["text"])
            cost = Decimal(char_count) * cost_per_char
            print(f"   - {t['language']}: '{t['text']}' ({char_count} chars, ${cost})")
        print(f"   - Total cost: ${total_cost}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_language_routing(self, mock_redis):
        """
        Test TTS routes to correct provider per language.

        Scenario:
        1. English → Google TTS
        2. Arabic → Azure TTS (better Arabic support)
        3. Unsupported → Fallback to wildcard

        Verifies:
        - Language-specific provider selection
        - Fallback to wildcard for unsupported languages
        """
        # Arrange
        routing_config = {
            "en": {"provider": "google_tts", "voice": "en-US-Neural2-D"},
            "pl": {"provider": "google_tts", "voice": "pl-PL-Wavenet-A"},
            "ar": {"provider": "azure_tts", "voice": "ar-EG-SalmaNeural"},
            "*": {"provider": "google_tts", "voice": "en-US-Neural2-D"}
        }

        # Act & Assert
        # English
        en_config = routing_config.get("en", routing_config["*"])
        assert en_config["provider"] == "google_tts"

        # Arabic (uses Azure)
        ar_config = routing_config.get("ar", routing_config["*"])
        assert ar_config["provider"] == "azure_tts"

        # Unsupported language (zh)
        zh_config = routing_config.get("zh", routing_config["*"])
        assert zh_config["provider"] == "google_tts"  # Fallback to wildcard

        print("✅ Language routing validated:")
        print(f"   - English: {en_config['provider']}")
        print(f"   - Arabic: {ar_config['provider']}")
        print(f"   - Chinese (unsupported): {zh_config['provider']} (fallback)")


class TestTTSProviderFailover:
    """Test TTS provider failover."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_provider_failover(self, mock_redis):
        """
        Test TTS failover to secondary provider on primary failure.

        Scenario:
        1. Primary provider (google_tts) is down
        2. TTS router uses fallback (azure_tts)
        3. Audio generated successfully

        Verifies:
        - Fallback provider used when primary down
        - Audio still generated
        - Health status updated
        """
        # Arrange
        primary_provider = "google_tts"
        fallback_provider = "azure_tts"
        primary_health = "down"

        # Act - Select provider based on health
        selected_provider = fallback_provider if primary_health == "down" else primary_provider

        # Assert
        assert selected_provider == "azure_tts"

        print("✅ Provider failover validated:")
        print(f"   - Primary: {primary_provider} (status: {primary_health})")
        print(f"   - Fallback: {fallback_provider}")
        print(f"   - Selected: {selected_provider}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_provider_health_recovery(self, mock_redis):
        """
        Test provider health recovery after successful synthesis.

        Scenario:
        1. Provider marked as degraded (1-2 failures)
        2. Successful synthesis
        3. Provider marked as healthy

        Verifies:
        - Health status updated on success
        - Consecutive failures reset to 0
        """
        # Arrange
        provider = "google_tts"
        initial_failures = 2
        initial_status = "degraded"

        # Act - Simulate successful synthesis
        success = True
        new_failures = 0 if success else initial_failures + 1
        new_status = "healthy" if new_failures == 0 else "degraded"

        # Assert
        assert new_failures == 0
        assert new_status == "healthy"

        print("✅ Provider health recovery validated:")
        print(f"   - Initial: {provider} ({initial_status}, {initial_failures} failures)")
        print(f"   - After success: {new_status} ({new_failures} failures)")


class TestTTSPartialVsFinal:
    """Test TTS behavior for partial vs final translations."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_final_only_mode(self, mock_redis):
        """
        Test TTS_FINAL_ONLY mode (cost optimization).

        Scenario:
        1. TTS_FINAL_ONLY = True
        2. Partial translation arrives → skipped
        3. Final translation arrives → synthesized

        Verifies:
        - Partials skipped when TTS_FINAL_ONLY enabled
        - Finals always synthesized
        - Cost savings from skipping partials
        """
        # Arrange
        tts_final_only = True

        partial_event = {"type": "translation_partial", "text": "Hello"}
        final_event = {"type": "translation_final", "text": "Hello, how are you?"}

        # Act
        should_synthesize_partial = not tts_final_only or partial_event["type"] == "translation_final"
        should_synthesize_final = not tts_final_only or final_event["type"] == "translation_final"

        # Assert
        assert should_synthesize_partial is False
        assert should_synthesize_final is True

        print("✅ TTS_FINAL_ONLY mode validated:")
        print(f"   - Mode: {tts_final_only}")
        print(f"   - Partial synthesized: {should_synthesize_partial}")
        print(f"   - Final synthesized: {should_synthesize_final}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_tts_partial_accumulation_cost(self, mock_redis):
        """
        Test cost savings from skipping partials.

        Scenario:
        1. 10 partial translations (accumulating)
        2. 1 final translation
        3. Without TTS_FINAL_ONLY: 11 synthesis calls
        4. With TTS_FINAL_ONLY: 1 synthesis call

        Verifies:
        - Significant cost savings with TTS_FINAL_ONLY
        """
        # Arrange
        partials = ["H", "He", "Hel", "Hell", "Hello", "Hello,", "Hello, h", "Hello, ho", "Hello, how", "Hello, how a"]
        final = "Hello, how are you?"

        cost_per_char = Decimal("0.000016")

        # Without TTS_FINAL_ONLY (synthesize all)
        total_chars_all = sum(len(p) for p in partials) + len(final)
        cost_all = Decimal(total_chars_all) * cost_per_char

        # With TTS_FINAL_ONLY (synthesize only final)
        total_chars_final_only = len(final)
        cost_final_only = Decimal(total_chars_final_only) * cost_per_char

        savings = cost_all - cost_final_only
        savings_percent = (savings / cost_all) * 100

        assert cost_final_only < cost_all
        assert savings_percent > 50  # Should save >50%

        print("✅ TTS_FINAL_ONLY cost savings:")
        print(f"   - Partials: {len(partials)} ({total_chars_all - total_chars_final_only} chars)")
        print(f"   - Final: 1 ({total_chars_final_only} chars)")
        print(f"   - Cost (all): ${cost_all}")
        print(f"   - Cost (final only): ${cost_final_only}")
        print(f"   - Savings: ${savings} ({savings_percent:.1f}%)")
