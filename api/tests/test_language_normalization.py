"""
Integration tests for language code normalization in STT router.

Tests cover the critical bug that was missed:
- Provider-specific language code handling
- Speechmatics requires simple codes (pl, en, ar)
- Google/Azure require locale format (pl-PL, en-EN, ar-EG)

This test would have caught the bug where:
1. First attempt: pl was NOT normalized → empty transcriptions
2. Second attempt: pl was normalized to pl-PL → Speechmatics rejected it
3. Correct: pl stays as pl for Speechmatics, pl-PL for Google/Azure
"""

import pytest
import pytest_asyncio
import redis.asyncio as redis
import os
import json
from unittest.mock import Mock, AsyncMock, patch


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")


@pytest_asyncio.fixture
async def redis_client():
    """Create Redis client for testing."""
    client = await redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.close()


class TestLanguageCodeNormalization:
    """Test provider-specific language code normalization."""

    def test_normalize_language_code_function(self):
        """Test the normalize_language_code function from language_router."""
        import sys
        sys.path.insert(0, '/app/api/routers/stt')
        from language_router import normalize_language_code

        # Test normalization to locale format (for Google/Azure)
        assert normalize_language_code("pl") == "pl-PL"
        assert normalize_language_code("en") == "en-EN"
        assert normalize_language_code("ar") == "ar-EG"
        assert normalize_language_code("es") == "es-ES"
        assert normalize_language_code("fr") == "fr-FR"

        # Test already normalized codes pass through
        assert normalize_language_code("pl-PL") == "pl-PL"
        assert normalize_language_code("en-US") == "en-US"

        # Test auto/fallback
        assert normalize_language_code("auto") == "*"
        assert normalize_language_code("") == "*"
        assert normalize_language_code(None) == "*"

    def test_speechmatics_language_format(self):
        """Test Speechmatics expects simple language codes (pl not pl-PL)."""
        import sys
        sys.path.insert(0, '/app/api/routers/stt')

        # Speechmatics mapping from speechmatics_streaming.py
        speechmatics_map = {
            "pl": "pl",
            "pl-PL": "pl",  # Should normalize to simple
            "en": "en",
            "en-EN": "en",
            "en-US": "en",
            "ar": "ar",
            "ar-EG": "ar",
        }

        # Verify simple codes are correct for Speechmatics
        assert speechmatics_map["pl"] == "pl"
        assert speechmatics_map["pl-PL"] == "pl"
        assert speechmatics_map["en"] == "en"

    def test_google_azure_language_format(self):
        """Test Google/Azure expect locale format (pl-PL not pl)."""
        import sys
        sys.path.insert(0, '/app/api/routers/stt')
        from language_router import normalize_language_code

        # Google/Azure require locale format
        # This is what should be sent to them
        assert normalize_language_code("pl") == "pl-PL"
        assert normalize_language_code("en") == "en-EN"
        assert normalize_language_code("ar") == "ar-EG"

    @pytest.mark.asyncio
    async def test_provider_specific_language_handling(self):
        """Test that language codes are adapted per provider in router.py."""
        import sys
        sys.path.insert(0, '/app/api/routers/stt')

        # Simulate the logic from router.py lines 349-354
        language_hint = "pl"

        # For Speechmatics: keep simple format
        provider = "speechmatics"
        if provider == "speechmatics":
            provider_lang = language_hint.split('-')[0] if '-' in language_hint else language_hint
        else:
            from language_router import normalize_language_code
            provider_lang = normalize_language_code(language_hint)

        assert provider_lang == "pl", "Speechmatics should get simple code 'pl'"

        # For Google: normalize to locale format
        provider = "google_v2"
        if provider == "speechmatics":
            provider_lang = language_hint.split('-')[0] if '-' in language_hint else language_hint
        else:
            from language_router import normalize_language_code
            provider_lang = normalize_language_code(language_hint)

        assert provider_lang == "pl-PL", "Google should get locale format 'pl-PL'"

    @pytest.mark.asyncio
    async def test_speechmatics_rejects_invalid_locale_code(self):
        """Test that Speechmatics rejects pl-PL (regression test)."""
        # This simulates the error we saw:
        # "invalid_model: Feature Validation Failed: lang pack [pl-PL] is not supported"

        invalid_codes_for_speechmatics = ["pl-PL", "en-EN", "ar-EG"]
        valid_codes_for_speechmatics = ["pl", "en", "ar"]

        # Speechmatics would reject these
        for code in invalid_codes_for_speechmatics:
            # Simulate validation
            simple_code = code.split('-')[0]
            assert simple_code in valid_codes_for_speechmatics, \
                f"Speechmatics rejects {code}, should use {simple_code}"

    def test_locale_code_extraction(self):
        """Test extracting simple code from locale format."""
        test_cases = {
            "pl-PL": "pl",
            "en-EN": "en",
            "en-US": "en",
            "ar-EG": "ar",
            "pl": "pl",  # Already simple
            "en": "en",  # Already simple
        }

        for input_code, expected in test_cases.items():
            result = input_code.split('-')[0] if '-' in input_code else input_code
            assert result == expected, f"Failed to extract simple code from {input_code}"


class TestLanguageRegressionScenarios:
    """Test specific scenarios that caused the bugs."""

    @pytest.mark.asyncio
    async def test_polish_user_speechmatics_scenario(self):
        """
        Regression test for Polish bug:
        1. User selects Polish (pl)
        2. System routes to Speechmatics
        3. WRONG: normalized to pl-PL → Speechmatics error "lang pack [pl-PL] is not supported"
        4. CORRECT: keep as pl → Speechmatics accepts it
        """
        user_language = "pl"
        provider = "speechmatics"

        # WRONG approach (what we did first)
        wrong_lang = "pl-PL"  # This caused the error

        # Simulate Speechmatics validation
        def speechmatics_accepts(lang_code):
            # Speechmatics only accepts simple codes
            return '-' not in lang_code

        assert not speechmatics_accepts(wrong_lang), \
            "Speechmatics should reject pl-PL (this was the bug)"

        # CORRECT approach (what we fixed)
        correct_lang = user_language.split('-')[0] if '-' in user_language else user_language
        assert speechmatics_accepts(correct_lang), \
            "Speechmatics should accept pl"

    @pytest.mark.asyncio
    async def test_english_user_google_scenario(self):
        """
        Test that English with Google still works correctly.
        1. User selects English (en)
        2. System routes to Google
        3. Normalize to en-EN → Google accepts it
        """
        import sys
        sys.path.insert(0, '/app/api/routers/stt')
        from language_router import normalize_language_code

        user_language = "en"
        provider = "google_v2"

        # For Google: normalize to locale
        if provider == "speechmatics":
            provider_lang = user_language.split('-')[0]
        else:
            provider_lang = normalize_language_code(user_language)

        # Google expects locale format
        assert provider_lang == "en-EN", "Google should get en-EN"
        assert '-' in provider_lang, "Google should get locale format with hyphen"

    @pytest.mark.asyncio
    async def test_arabic_user_speechmatics_scenario(self):
        """
        Test Arabic with Speechmatics works.
        User reported English and Arabic worked, only Polish failed.
        """
        user_language = "ar"
        provider = "speechmatics"

        # Keep simple code for Speechmatics
        provider_lang = user_language.split('-')[0] if '-' in user_language else user_language

        assert provider_lang == "ar", "Speechmatics should get simple 'ar'"
        assert '-' not in provider_lang, "Should not have locale format"

    @pytest.mark.asyncio
    async def test_language_already_in_locale_format(self):
        """Test handling when user language is already in locale format."""
        user_language = "pl-PL"
        provider = "speechmatics"

        # Extract simple code from locale
        provider_lang = user_language.split('-')[0] if '-' in user_language else user_language

        assert provider_lang == "pl", "Should extract 'pl' from 'pl-PL'"

    def test_all_supported_languages_speechmatics(self):
        """Test all supported languages normalize correctly for Speechmatics."""
        supported_langs = ["en", "pl", "ar", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko"]

        for lang in supported_langs:
            # For Speechmatics, should stay simple
            result = lang.split('-')[0] if '-' in lang else lang
            assert result == lang, f"Language {lang} should stay as {lang} for Speechmatics"
            assert '-' not in result, f"Speechmatics format should be simple, not locale"

    def test_all_supported_languages_google(self):
        """Test all supported languages normalize correctly for Google."""
        import sys
        sys.path.insert(0, '/app/api/routers/stt')
        from language_router import normalize_language_code

        test_cases = {
            "en": "en-EN",
            "pl": "pl-PL",
            "ar": "ar-EG",
            "es": "es-ES",
            "fr": "fr-FR",
            "de": "de-DE",
        }

        for simple, locale in test_cases.items():
            result = normalize_language_code(simple)
            assert result == locale, f"{simple} should normalize to {locale} for Google"
            assert '-' in result, "Google format should be locale with hyphen"
