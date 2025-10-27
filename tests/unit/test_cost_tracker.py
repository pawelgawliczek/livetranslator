"""
Unit tests for api/cost_tracker.py

Tests cost calculation functions:
- calculate_stt_cost() - STT cost calculation (per minute)
- calculate_mt_cost() - MT cost calculation (per token)
- estimate_tokens() - Token estimation from text
- get_pricing() - Pricing configuration
"""

import pytest
from decimal import Decimal
from unittest.mock import patch

# Import the module under test
from api import cost_tracker


@pytest.mark.unit
class TestGetPricing:
    """Tests for get_pricing() function."""

    def test_get_pricing_returns_default_values(self):
        """Test that get_pricing returns default pricing configuration."""
        pricing = cost_tracker.get_pricing()

        assert "whisper-1" in pricing
        assert "gpt-4o-mini" in pricing
        assert "per_minute" in pricing["whisper-1"]
        assert "input_per_1k" in pricing["gpt-4o-mini"]
        assert "output_per_1k" in pricing["gpt-4o-mini"]

    def test_get_pricing_whisper_default(self):
        """Test default Whisper pricing."""
        with patch.dict('os.environ', {}, clear=True):
            pricing = cost_tracker.get_pricing()

            assert pricing["whisper-1"]["per_minute"] == Decimal("0.006")

    def test_get_pricing_gpt4o_mini_defaults(self):
        """Test default GPT-4o-mini pricing."""
        with patch.dict('os.environ', {}, clear=True):
            pricing = cost_tracker.get_pricing()

            assert pricing["gpt-4o-mini"]["input_per_1k"] == Decimal("0.00015")
            assert pricing["gpt-4o-mini"]["output_per_1k"] == Decimal("0.0006")

    def test_get_pricing_custom_whisper_price(self):
        """Test custom Whisper pricing from environment."""
        with patch.dict('os.environ', {'OPENAI_PRICE_WHISPER_PER_MIN': '0.010'}):
            pricing = cost_tracker.get_pricing()

            assert pricing["whisper-1"]["per_minute"] == Decimal("0.010")

    def test_get_pricing_custom_gpt4o_prices(self):
        """Test custom GPT-4o-mini pricing from environment."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.0002',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0008'
        }):
            pricing = cost_tracker.get_pricing()

            assert pricing["gpt-4o-mini"]["input_per_1k"] == Decimal("0.0002")
            assert pricing["gpt-4o-mini"]["output_per_1k"] == Decimal("0.0008")

    def test_get_pricing_returns_decimal_types(self):
        """Test that pricing values are Decimal (for precise calculations)."""
        pricing = cost_tracker.get_pricing()

        assert isinstance(pricing["whisper-1"]["per_minute"], Decimal)
        assert isinstance(pricing["gpt-4o-mini"]["input_per_1k"], Decimal)
        assert isinstance(pricing["gpt-4o-mini"]["output_per_1k"], Decimal)


@pytest.mark.unit
class TestCalculateSTTCost:
    """Tests for calculate_stt_cost() function."""

    def test_calculate_stt_cost_one_minute(self):
        """Test STT cost for exactly 1 minute."""
        with patch.dict('os.environ', {'OPENAI_PRICE_WHISPER_PER_MIN': '0.006'}):
            cost = cost_tracker.calculate_stt_cost(60.0)

            assert cost == Decimal("0.006")

    def test_calculate_stt_cost_30_seconds(self):
        """Test STT cost for 30 seconds (0.5 minutes)."""
        with patch.dict('os.environ', {'OPENAI_PRICE_WHISPER_PER_MIN': '0.006'}):
            cost = cost_tracker.calculate_stt_cost(30.0)

            # 0.5 minutes * $0.006/min = $0.003
            assert cost == Decimal("0.003")

    def test_calculate_stt_cost_zero_duration(self):
        """Test STT cost for zero duration."""
        with patch.dict('os.environ', {'OPENAI_PRICE_WHISPER_PER_MIN': '0.006'}):
            cost = cost_tracker.calculate_stt_cost(0.0)

            assert cost == Decimal("0")

    def test_calculate_stt_cost_fractional_seconds(self):
        """Test STT cost for fractional seconds."""
        with patch.dict('os.environ', {'OPENAI_PRICE_WHISPER_PER_MIN': '0.006'}):
            # 45 seconds = 0.75 minutes
            cost = cost_tracker.calculate_stt_cost(45.0)

            # 0.75 * 0.006 = 0.0045
            assert cost == Decimal("0.0045")

    def test_calculate_stt_cost_long_audio(self):
        """Test STT cost for long audio (10 minutes)."""
        with patch.dict('os.environ', {'OPENAI_PRICE_WHISPER_PER_MIN': '0.006'}):
            cost = cost_tracker.calculate_stt_cost(600.0)  # 10 minutes

            # 10 * 0.006 = 0.06
            assert cost == Decimal("0.06")

    def test_calculate_stt_cost_returns_decimal(self):
        """Test that STT cost returns Decimal for precision."""
        cost = cost_tracker.calculate_stt_cost(60.0)

        assert isinstance(cost, Decimal)

    @pytest.mark.parametrize("duration,expected", [
        (0, Decimal("0")),
        (15, Decimal("0.0015")),  # 0.25 min * 0.006
        (60, Decimal("0.006")),   # 1 min * 0.006
        (120, Decimal("0.012")),  # 2 min * 0.006
        (300, Decimal("0.030")),  # 5 min * 0.006
    ])
    def test_calculate_stt_cost_various_durations(self, duration, expected):
        """Test STT cost calculation with various durations."""
        with patch.dict('os.environ', {'OPENAI_PRICE_WHISPER_PER_MIN': '0.006'}):
            cost = cost_tracker.calculate_stt_cost(float(duration))

            assert cost == expected


@pytest.mark.unit
class TestCalculateMTCost:
    """Tests for calculate_mt_cost() function."""

    def test_calculate_mt_cost_zero_tokens(self):
        """Test MT cost with zero tokens."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            cost = cost_tracker.calculate_mt_cost(0, 0)

            assert cost == Decimal("0")

    def test_calculate_mt_cost_1000_input_tokens(self):
        """Test MT cost for 1000 input tokens."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            cost = cost_tracker.calculate_mt_cost(1000, 0)

            # 1000/1000 * 0.00015 = 0.00015
            assert cost == Decimal("0.00015")

    def test_calculate_mt_cost_1000_output_tokens(self):
        """Test MT cost for 1000 output tokens."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            cost = cost_tracker.calculate_mt_cost(0, 1000)

            # 1000/1000 * 0.0006 = 0.0006
            assert cost == Decimal("0.0006")

    def test_calculate_mt_cost_combined_tokens(self):
        """Test MT cost with both input and output tokens."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            # 1000 input + 500 output
            cost = cost_tracker.calculate_mt_cost(1000, 500)

            # (1000/1000 * 0.00015) + (500/1000 * 0.0006)
            # = 0.00015 + 0.0003 = 0.00045
            assert cost == Decimal("0.00045")

    def test_calculate_mt_cost_fractional_tokens(self):
        """Test MT cost with fractional thousand tokens."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            # 500 input + 250 output
            cost = cost_tracker.calculate_mt_cost(500, 250)

            # (500/1000 * 0.00015) + (250/1000 * 0.0006)
            # = 0.000075 + 0.00015 = 0.000225
            assert cost == Decimal("0.000225")

    def test_calculate_mt_cost_large_token_count(self):
        """Test MT cost with large token counts."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            # 10,000 input + 5,000 output
            cost = cost_tracker.calculate_mt_cost(10000, 5000)

            # (10000/1000 * 0.00015) + (5000/1000 * 0.0006)
            # = 0.0015 + 0.003 = 0.0045
            assert cost == Decimal("0.0045")

    def test_calculate_mt_cost_returns_decimal(self):
        """Test that MT cost returns Decimal for precision."""
        cost = cost_tracker.calculate_mt_cost(1000, 500)

        assert isinstance(cost, Decimal)

    @pytest.mark.parametrize("input_tokens,output_tokens,expected", [
        (0, 0, Decimal("0")),
        (1000, 0, Decimal("0.00015")),
        (0, 1000, Decimal("0.0006")),
        (1000, 1000, Decimal("0.00075")),
        (500, 250, Decimal("0.000225")),
        (2000, 500, Decimal("0.0006")),
    ])
    def test_calculate_mt_cost_various_combinations(self, input_tokens, output_tokens, expected):
        """Test MT cost with various token combinations."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            cost = cost_tracker.calculate_mt_cost(input_tokens, output_tokens)

            assert cost == expected


@pytest.mark.unit
class TestEstimateTokens:
    """Tests for estimate_tokens() function."""

    def test_estimate_tokens_empty_string(self):
        """Test token estimation for empty string."""
        tokens = cost_tracker.estimate_tokens("")

        # Returns at least 1 token
        assert tokens == 1

    def test_estimate_tokens_short_text(self):
        """Test token estimation for short text."""
        text = "Hello"  # 5 chars
        tokens = cost_tracker.estimate_tokens(text)

        # 5 chars / 4 = 1.25 → 1 token
        assert tokens == 1

    def test_estimate_tokens_4_characters(self):
        """Test token estimation for exactly 4 characters (1 token)."""
        text = "test"  # 4 chars
        tokens = cost_tracker.estimate_tokens(text)

        # 4 chars / 4 = 1 token
        assert tokens == 1

    def test_estimate_tokens_8_characters(self):
        """Test token estimation for 8 characters (2 tokens)."""
        text = "testing!"  # 8 chars
        tokens = cost_tracker.estimate_tokens(text)

        # 8 chars / 4 = 2 tokens
        assert tokens == 2

    def test_estimate_tokens_long_text(self):
        """Test token estimation for long text."""
        text = "This is a longer text with multiple words and sentences."  # 58 chars
        tokens = cost_tracker.estimate_tokens(text)

        # 58 chars / 4 = 14.5 → 14 tokens
        assert tokens == 14

    def test_estimate_tokens_single_character(self):
        """Test token estimation for single character."""
        tokens = cost_tracker.estimate_tokens("A")

        # Returns at least 1 token
        assert tokens == 1

    def test_estimate_tokens_whitespace(self):
        """Test token estimation for whitespace."""
        tokens = cost_tracker.estimate_tokens("   ")  # 3 spaces

        # 3 chars / 4 = 0.75 → 1 token (minimum)
        assert tokens == 1

    @pytest.mark.parametrize("text,expected_min", [
        ("", 1),
        ("Hi", 1),
        ("Hello World", 2),  # 11 chars / 4 = 2.75 → 2
        ("This is a test", 3),  # 14 chars / 4 = 3.5 → 3
        ("A" * 100, 25),  # 100 chars / 4 = 25
        ("A" * 1000, 250),  # 1000 chars / 4 = 250
    ])
    def test_estimate_tokens_various_texts(self, text, expected_min):
        """Test token estimation with various texts."""
        tokens = cost_tracker.estimate_tokens(text)

        assert tokens == expected_min

    def test_estimate_tokens_unicode_characters(self):
        """Test token estimation with Unicode characters."""
        text = "Hello 世界"  # 9 characters including space and Chinese
        tokens = cost_tracker.estimate_tokens(text)

        # 9 chars / 4 = 2.25 → 2 tokens
        assert tokens == 2

    def test_estimate_tokens_emojis(self):
        """Test token estimation with emojis."""
        text = "Hello 😀"  # 7 characters (emoji counts as 1 char in Python len())
        tokens = cost_tracker.estimate_tokens(text)

        # len("Hello 😀") in Python returns 7
        # 7 / 4 = 1.75 → 1 token
        assert tokens == 1


@pytest.mark.unit
class TestCostCalculationRealism:
    """Realistic cost calculation tests."""

    def test_typical_conversation_cost(self):
        """Test cost for a typical 5-minute conversation."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_WHISPER_PER_MIN': '0.006',
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            # 5 minutes of audio
            stt_cost = cost_tracker.calculate_stt_cost(300.0)

            # Typical translation: 500 input tokens, 500 output tokens
            mt_cost = cost_tracker.calculate_mt_cost(500, 500)

            total_cost = stt_cost + mt_cost

            # STT: 5 * 0.006 = 0.03
            # MT: (500/1000 * 0.00015) + (500/1000 * 0.0006) = 0.000375
            # Total: 0.030375
            assert stt_cost == Decimal("0.03")
            assert mt_cost == Decimal("0.000375")
            assert total_cost == Decimal("0.030375")

    def test_cost_precision_is_maintained(self):
        """Test that Decimal precision is maintained through calculations."""
        with patch.dict('os.environ', {
            'OPENAI_PRICE_WHISPER_PER_MIN': '0.006',
            'OPENAI_PRICE_GPT4OMINI_INPUT_PER_1K': '0.00015',
            'OPENAI_PRICE_GPT4OMINI_OUTPUT_PER_1K': '0.0006'
        }):
            # Multiple small costs
            cost1 = cost_tracker.calculate_stt_cost(1.5)  # 1.5 seconds
            cost2 = cost_tracker.calculate_mt_cost(10, 10)
            total = cost1 + cost2

            # Should maintain precision
            assert isinstance(total, Decimal)
            # 1.5/60 * 0.006 + (10/1000 * 0.00015) + (10/1000 * 0.0006)
            # = 0.00015 + 0.0000015 + 0.000006 = 0.0001575
            assert total == Decimal("0.0001575")
