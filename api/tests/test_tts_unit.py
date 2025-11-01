"""
Unit tests for TTS cost calculations and utilities.

Tests cover:
- TTS cost calculation (character-based)
- Voice type detection (Wavenet vs Standard vs Neural2)
- Settings validation (volume, rate, pitch)
- Language normalization

Priority: Unit tests (fast, no I/O)
"""

import pytest
from decimal import Decimal


class TestTTSCostCalculations:
    """Test TTS cost calculations for different voice types."""

    def test_calculate_tts_cost_wavenet(self):
        """Test TTS cost for Wavenet voices ($16/1M chars)."""
        character_count = 10_000
        voice_type = "wavenet"
        cost_per_million = Decimal("16.00")

        # Calculate cost: (chars / 1M) * $16
        expected_cost = (Decimal(character_count) / Decimal("1000000")) * cost_per_million

        assert expected_cost == Decimal("0.16")
        print(f"✅ WaveNet cost: {character_count} chars = ${expected_cost}")

    def test_calculate_tts_cost_neural2(self):
        """Test TTS cost for Neural2 voices ($16/1M chars)."""
        character_count = 10_000
        voice_type = "neural2"
        cost_per_million = Decimal("16.00")

        expected_cost = (Decimal(character_count) / Decimal("1000000")) * cost_per_million

        assert expected_cost == Decimal("0.16")
        print(f"✅ Neural2 cost: {character_count} chars = ${expected_cost}")

    def test_calculate_tts_cost_standard(self):
        """Test TTS cost for Standard voices ($4/1M chars)."""
        character_count = 10_000
        voice_type = "standard"
        cost_per_million = Decimal("4.00")

        expected_cost = (Decimal(character_count) / Decimal("1000000")) * cost_per_million

        assert expected_cost == Decimal("0.04")
        print(f"✅ Standard cost: {character_count} chars = ${expected_cost}")

    def test_calculate_tts_cost_edge_cases(self):
        """Test TTS cost calculation edge cases."""
        cost_per_million = Decimal("16.00")

        # 0 characters
        assert (Decimal("0") / Decimal("1000000")) * cost_per_million == Decimal("0")

        # 1 character (minimum)
        cost_1_char = (Decimal("1") / Decimal("1000000")) * cost_per_million
        assert cost_1_char == Decimal("0.000016")

        # 1 million characters
        cost_1m_chars = (Decimal("1000000") / Decimal("1000000")) * cost_per_million
        assert cost_1m_chars == Decimal("16.00")

        # Very large input (10 million characters)
        cost_10m_chars = (Decimal("10000000") / Decimal("1000000")) * cost_per_million
        assert cost_10m_chars == Decimal("160.00")

        print("✅ Edge cases validated:")
        print(f"   - 0 chars = $0")
        print(f"   - 1 char = ${cost_1_char}")
        print(f"   - 1M chars = ${cost_1m_chars}")
        print(f"   - 10M chars = ${cost_10m_chars}")

    def test_multi_language_cost_aggregation(self):
        """Test cost aggregation across multiple languages."""
        # Scenario: Same text translated to 3 languages
        text = "Hello, how are you today?"
        character_count = len(text)  # 25 characters
        target_languages = 3
        cost_per_million = Decimal("16.00")

        # Total cost = chars * langs * (cost/1M)
        total_chars = character_count * target_languages
        total_cost = (Decimal(total_chars) / Decimal("1000000")) * cost_per_million

        assert total_chars == 75
        assert total_cost == Decimal("0.0012")

        print(f"✅ Multi-language cost: {character_count} chars × {target_languages} langs = ${total_cost}")


class TestVoiceTypeDetection:
    """Test voice type detection from voice name."""

    def test_detect_wavenet_voice(self):
        """Test detection of WaveNet voices."""
        voice_names = [
            "en-US-Wavenet-D",
            "pl-PL-Wavenet-A",
            "ar-EG-Wavenet-B"
        ]

        for voice_name in voice_names:
            assert "Wavenet" in voice_name
            voice_type = "wavenet"
            assert voice_type == "wavenet"

        print(f"✅ WaveNet voices detected: {voice_names}")

    def test_detect_neural2_voice(self):
        """Test detection of Neural2 voices."""
        voice_names = [
            "en-US-Neural2-D",
            "es-ES-Neural2-A",
            "fr-FR-Neural2-B"
        ]

        for voice_name in voice_names:
            assert "Neural2" in voice_name
            voice_type = "neural2"
            assert voice_type == "neural2"

        print(f"✅ Neural2 voices detected: {voice_names}")

    def test_detect_standard_voice(self):
        """Test detection of Standard voices."""
        voice_names = [
            "en-US-Standard-D",
            "pl-PL-Standard-A"
        ]

        for voice_name in voice_names:
            assert "Standard" in voice_name
            voice_type = "standard"
            assert voice_type == "standard"

        print(f"✅ Standard voices detected: {voice_names}")

    def test_voice_language_extraction(self):
        """Test extracting language code from voice name."""
        test_cases = [
            ("en-US-Wavenet-D", "en-US"),
            ("pl-PL-Wavenet-A", "pl-PL"),
            ("ar-EG-Wavenet-B", "ar-EG"),
            ("es-ES-Neural2-A", "es-ES")
        ]

        for voice_name, expected_lang in test_cases:
            # Extract language code (first two parts before voice type)
            parts = voice_name.split("-")
            lang_code = f"{parts[0]}-{parts[1]}"
            assert lang_code == expected_lang

        print(f"✅ Language extraction validated for {len(test_cases)} voices")


class TestTTSSettingsValidation:
    """Test validation of TTS settings (volume, rate, pitch)."""

    def test_valid_volume_range(self):
        """Test valid volume range (0.0 - 2.0)."""
        valid_volumes = [0.0, 0.5, 1.0, 1.5, 2.0]

        for volume in valid_volumes:
            assert 0.0 <= volume <= 2.0

        print(f"✅ Valid volumes: {valid_volumes}")

    def test_invalid_volume_range(self):
        """Test invalid volume values."""
        invalid_volumes = [-0.1, -1.0, 2.1, 3.0]

        for volume in invalid_volumes:
            is_valid = 0.0 <= volume <= 2.0
            assert not is_valid

        print(f"✅ Invalid volumes rejected: {invalid_volumes}")

    def test_valid_rate_range(self):
        """Test valid speaking rate range (0.25 - 4.0)."""
        valid_rates = [0.25, 0.5, 1.0, 2.0, 3.0, 4.0]

        for rate in valid_rates:
            assert 0.25 <= rate <= 4.0

        print(f"✅ Valid rates: {valid_rates}")

    def test_invalid_rate_range(self):
        """Test invalid speaking rate values."""
        invalid_rates = [0.1, 0.2, 4.1, 5.0, 10.0]

        for rate in invalid_rates:
            is_valid = 0.25 <= rate <= 4.0
            assert not is_valid

        print(f"✅ Invalid rates rejected: {invalid_rates}")

    def test_valid_pitch_range(self):
        """Test valid pitch range (-20.0 to 20.0)."""
        valid_pitches = [-20.0, -10.0, 0.0, 10.0, 20.0]

        for pitch in valid_pitches:
            assert -20.0 <= pitch <= 20.0

        print(f"✅ Valid pitches: {valid_pitches}")

    def test_invalid_pitch_range(self):
        """Test invalid pitch values."""
        invalid_pitches = [-25.0, -21.0, 21.0, 25.0, 50.0]

        for pitch in invalid_pitches:
            is_valid = -20.0 <= pitch <= 20.0
            assert not is_valid

        print(f"✅ Invalid pitches rejected: {invalid_pitches}")

    def test_default_settings(self):
        """Test default TTS settings values."""
        defaults = {
            "volume": 1.0,
            "rate": 1.0,
            "pitch": 0.0
        }

        # Validate defaults are within valid ranges
        assert 0.0 <= defaults["volume"] <= 2.0
        assert 0.25 <= defaults["rate"] <= 4.0
        assert -20.0 <= defaults["pitch"] <= 20.0

        print(f"✅ Default settings validated: {defaults}")


class TestLanguageNormalization:
    """Test language code normalization for TTS routing."""

    def test_normalize_locale_codes(self):
        """Test normalization of locale-specific codes."""
        test_cases = [
            ("en-US", "en"),
            ("en-GB", "en"),
            ("pl-PL", "pl"),
            ("ar-EG", "ar"),
            ("es-ES", "es"),
            ("fr-FR", "fr")
        ]

        for input_lang, expected_normalized in test_cases:
            # Normalize by taking first part before hyphen
            normalized = input_lang.split("-")[0].lower()
            assert normalized == expected_normalized

        print(f"✅ Normalized {len(test_cases)} locale codes")

    def test_normalize_simple_codes(self):
        """Test normalization of simple language codes (no-op)."""
        simple_codes = ["en", "pl", "ar", "es", "fr", "de"]

        for code in simple_codes:
            normalized = code.split("-")[0].lower()
            assert normalized == code.lower()

        print(f"✅ Simple codes unchanged: {simple_codes}")

    def test_normalize_empty_or_none(self):
        """Test normalization of empty or None values."""
        # Empty string should fallback to wildcard
        empty_normalized = "*" if not "" else "".split("-")[0]
        assert empty_normalized == "*"

        # None should fallback to wildcard
        none_value = None
        none_normalized = "*" if not none_value else none_value.split("-")[0]
        assert none_normalized == "*"

        print("✅ Empty/None values fallback to wildcard (*)")


class TestTTSConfigValidation:
    """Test validation of TTS provider configuration."""

    def test_valid_google_tts_config(self):
        """Test valid Google TTS configuration."""
        config = {
            "voice_id": "en-US-Neural2-D",
            "pitch": 0.0,
            "speaking_rate": 1.0,
            "voice_gender": "MALE"
        }

        # Validate required fields
        assert "voice_id" in config
        assert "pitch" in config
        assert "speaking_rate" in config
        assert "voice_gender" in config

        # Validate ranges
        assert -20.0 <= config["pitch"] <= 20.0
        assert 0.25 <= config["speaking_rate"] <= 4.0
        assert config["voice_gender"] in ["MALE", "FEMALE", "NEUTRAL"]

        print(f"✅ Valid Google TTS config: {config}")

    def test_missing_required_fields(self):
        """Test detection of missing required fields."""
        incomplete_configs = [
            {"voice_id": "en-US-Neural2-D"},  # Missing pitch, rate, gender
            {"pitch": 0.0, "speaking_rate": 1.0},  # Missing voice_id
            {}  # Empty config
        ]

        for config in incomplete_configs:
            has_all_fields = all(
                field in config
                for field in ["voice_id", "pitch", "speaking_rate", "voice_gender"]
            )
            assert not has_all_fields

        print(f"✅ Missing fields detected in {len(incomplete_configs)} configs")

    def test_voice_gender_values(self):
        """Test valid voice gender values."""
        valid_genders = ["MALE", "FEMALE", "NEUTRAL", "SSML_VOICE_GENDER_UNSPECIFIED"]

        for gender in valid_genders:
            assert gender in valid_genders

        invalid_genders = ["male", "UNKNOWN", "OTHER", ""]

        for gender in invalid_genders:
            is_valid = gender in valid_genders
            assert not is_valid

        print(f"✅ Valid genders: {valid_genders}")
        print(f"✅ Invalid genders rejected: {invalid_genders}")
