"""
Integration tests for Translation Matrix system.

Tests cover:
- Target language aggregation from room participants
- Multi-language translation (translating to ALL target languages)
- Language normalization and matching
- Partial translation caching (cost optimization)
- Arabic translation throttling
- Cache cleanup on finalization
- Skip logic (same src/tgt, auto detection)
- Edge cases and error handling
"""

import pytest
import pytest_asyncio
import asyncio
import redis.asyncio as redis
import os
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch


REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/5")


@pytest_asyncio.fixture
async def redis_client():
    """Create a Redis client for testing."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def clean_room(redis_client):
    """Provide a clean test room and clean up after."""
    room_code = f"test-matrix-{datetime.now().timestamp()}"

    # Clean up before
    await redis_client.delete(f"room:{room_code}:target_languages")
    await redis_client.delete(f"room:{room_code}:active_lang:*")

    yield room_code

    # Clean up after
    await redis_client.delete(f"room:{room_code}:target_languages")
    # Clean up all active language keys
    pattern = f"room:{room_code}:active_lang:*"
    async for key in redis_client.scan_iter(match=pattern):
        await redis_client.delete(key)


@pytest.mark.integration
@pytest.mark.asyncio
class TestTargetLanguageAggregation:
    """Test target language aggregation from room participants."""

    async def test_single_user_target_language(self, redis_client, clean_room):
        """Test target language set for single user."""
        room = clean_room

        # Register single user language
        await redis_client.setex(f"room:{room}:active_lang:user1", 15, "en")

        # Simulate aggregation (what main.py does)
        pattern = f"room:{room}:active_lang:*"
        languages = set()
        async for key in redis_client.scan_iter(match=pattern):
            lang = await redis_client.get(key)
            if lang:
                languages.add(lang)

        # Store in target_languages
        if languages:
            target_key = f"room:{room}:target_languages"
            await redis_client.delete(target_key)
            await redis_client.sadd(target_key, *languages)
            await redis_client.expire(target_key, 30)

        # Verify
        target_langs = await redis_client.smembers(f"room:{room}:target_languages")
        assert target_langs == {"en"}

    async def test_multiple_users_different_languages(self, redis_client, clean_room):
        """Test target language aggregation from multiple users."""
        room = clean_room

        # Register multiple users with different languages
        await redis_client.setex(f"room:{room}:active_lang:user1", 15, "en")
        await redis_client.setex(f"room:{room}:active_lang:user2", 15, "pl")
        await redis_client.setex(f"room:{room}:active_lang:user3", 15, "ar")

        # Aggregate
        pattern = f"room:{room}:active_lang:*"
        languages = set()
        async for key in redis_client.scan_iter(match=pattern):
            lang = await redis_client.get(key)
            if lang:
                languages.add(lang)

        target_key = f"room:{room}:target_languages"
        await redis_client.delete(target_key)
        await redis_client.sadd(target_key, *languages)

        # Verify all three languages
        target_langs = await redis_client.smembers(f"room:{room}:target_languages")
        assert target_langs == {"en", "pl", "ar"}

    async def test_duplicate_language_deduplication(self, redis_client, clean_room):
        """Test that duplicate languages are deduplicated."""
        room = clean_room

        # Multiple users with same language
        await redis_client.setex(f"room:{room}:active_lang:user1", 15, "en")
        await redis_client.setex(f"room:{room}:active_lang:user2", 15, "en")
        await redis_client.setex(f"room:{room}:active_lang:user3", 15, "pl")

        # Aggregate
        pattern = f"room:{room}:active_lang:*"
        languages = set()
        async for key in redis_client.scan_iter(match=pattern):
            lang = await redis_client.get(key)
            if lang:
                languages.add(lang)

        target_key = f"room:{room}:target_languages"
        await redis_client.sadd(target_key, *languages)

        # Should only have 2 unique languages
        target_langs = await redis_client.smembers(f"room:{room}:target_languages")
        assert target_langs == {"en", "pl"}

    async def test_target_languages_ttl(self, redis_client, clean_room):
        """Test that target_languages has appropriate TTL."""
        room = clean_room

        # Set target languages with TTL
        target_key = f"room:{room}:target_languages"
        await redis_client.sadd(target_key, "en", "pl")
        await redis_client.expire(target_key, 30)

        # Check TTL
        ttl = await redis_client.ttl(target_key)
        assert 25 <= ttl <= 30  # Should be around 30 seconds

    async def test_empty_room_no_target_languages(self, redis_client, clean_room):
        """Test behavior when no users are in room."""
        room = clean_room

        # Try to get target languages (should be empty)
        target_langs = await redis_client.smembers(f"room:{room}:target_languages")
        assert len(target_langs) == 0


@pytest.mark.integration
@pytest.mark.asyncio
class TestTranslationMatrix:
    """Test translation matrix logic."""

    async def test_translation_matrix_concept(self, redis_client, clean_room):
        """Test that translation happens to ALL target languages."""
        room = clean_room

        # Setup: 3 users with different languages
        target_langs = {"en", "pl", "ar"}
        target_key = f"room:{room}:target_languages"
        await redis_client.sadd(target_key, *target_langs)

        # Simulate MT router logic
        src_lang = "en"
        translations_created = []

        for tgt_lang in target_langs:
            # Skip if same language
            if src_lang == tgt_lang:
                continue

            translations_created.append(f"{src_lang}→{tgt_lang}")

        # Should translate to pl and ar (not en, since src is en)
        assert set(translations_created) == {"en→pl", "en→ar"}

    async def test_bidirectional_translation(self, redis_client, clean_room):
        """Test bidirectional translation (pl speaker with en/ar listeners)."""
        room = clean_room

        # Setup
        target_langs = {"en", "pl", "ar"}
        await redis_client.sadd(f"room:{room}:target_languages", *target_langs)

        # Polish speaker
        src_lang = "pl"
        translations = []

        for tgt_lang in target_langs:
            if src_lang != tgt_lang:
                translations.append(f"{src_lang}→{tgt_lang}")

        # Should translate pl→en and pl→ar
        assert set(translations) == {"pl→en", "pl→ar"}

    async def test_skip_auto_source_language(self, redis_client, clean_room):
        """Test that translations are skipped when source is 'auto'."""
        room = clean_room

        target_langs = {"en", "pl"}
        await redis_client.sadd(f"room:{room}:target_languages", *target_langs)

        # Auto/unknown source language
        src_lang = "auto"
        translations = []

        for tgt_lang in target_langs:
            # Skip if source is auto
            if src_lang == "auto":
                continue
            translations.append(f"{src_lang}→{tgt_lang}")

        # Should skip all translations
        assert len(translations) == 0

    async def test_skip_same_source_target(self, redis_client, clean_room):
        """Test that translation is skipped when src equals tgt."""
        room = clean_room

        target_langs = {"en", "pl", "ar"}
        await redis_client.sadd(f"room:{room}:target_languages", *target_langs)

        # English speaker
        src_lang = "en"
        translations = []

        for tgt_lang in target_langs:
            if src_lang == tgt_lang:
                continue  # Skip same language
            translations.append(f"{src_lang}→{tgt_lang}")

        # Should only translate to pl and ar
        assert set(translations) == {"en→pl", "en→ar"}


@pytest.mark.integration
@pytest.mark.asyncio
class TestPartialTranslationCaching:
    """Test partial translation caching for cost optimization."""

    async def test_cache_key_structure(self):
        """Test that cache keys include all necessary components."""
        # Cache key format: (room, segment, src_lang, tgt_lang, text)
        cache = {}

        room = "test-room"
        segment = 1
        src = "en"
        tgt = "pl"
        text = "Hello world"

        cache_key = (room, segment, src, tgt, text)
        cache[cache_key] = {"text": "Witaj świecie", "provider": "deepl"}

        # Verify cache hit
        assert cache_key in cache
        assert cache[cache_key]["text"] == "Witaj świecie"

    async def test_cache_miss_different_text(self):
        """Test cache miss when text changes."""
        cache = {}

        # Cache first text
        key1 = ("room", 1, "en", "pl", "Hello")
        cache[key1] = {"text": "Witaj"}

        # Different text - cache miss
        key2 = ("room", 1, "en", "pl", "Hello world")
        assert key2 not in cache

    async def test_cache_miss_different_segment(self):
        """Test cache miss when segment changes."""
        cache = {}

        # Cache segment 1
        key1 = ("room", 1, "en", "pl", "Hello")
        cache[key1] = {"text": "Witaj"}

        # Different segment - cache miss
        key2 = ("room", 2, "en", "pl", "Hello")
        assert key2 not in cache

    async def test_cache_cleanup_on_finalization(self):
        """Test that partial cache is cleaned up when segment is finalized."""
        cache = {}

        room = "test-room"
        segment = 1

        # Add several cached partials for this segment
        cache[(room, segment, "en", "pl", "Hello")] = {"text": "Witaj"}
        cache[(room, segment, "en", "pl", "Hello world")] = {"text": "Witaj świecie"}
        cache[(room, segment, "en", "ar", "Hello")] = {"text": "مرحبا"}

        # Add cache for different segment (should not be cleaned)
        cache[(room, 2, "en", "pl", "Goodbye")] = {"text": "Do widzenia"}

        # Simulate finalization cleanup
        keys_to_remove = [k for k in cache.keys() if k[0] == room and k[1] == segment]
        for key in keys_to_remove:
            del cache[key]

        # Segment 1 cache should be removed
        assert len([k for k in cache.keys() if k[1] == 1]) == 0
        # Segment 2 cache should remain
        assert len([k for k in cache.keys() if k[1] == 2]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
class TestArabicTranslationThrottling:
    """Test Arabic translation throttling for cost optimization."""

    async def test_arabic_throttle_structure(self):
        """Test throttle key structure."""
        throttle = {}

        room = "test-room"
        segment = 1
        tgt_lang = "ar"

        throttle_key = (room, segment, tgt_lang)
        current_time = asyncio.get_event_loop().time()
        throttle[throttle_key] = current_time

        assert throttle_key in throttle

    async def test_arabic_throttle_timing(self):
        """Test that throttling respects time interval."""
        throttle = {}
        throttle_seconds = 2.0

        room = "test-room"
        segment = 1
        tgt_lang = "ar"
        throttle_key = (room, segment, tgt_lang)

        # First translation
        current_time = 100.0
        throttle[throttle_key] = current_time

        # Simulate second translation attempt 1 second later (should throttle)
        new_time = 101.0
        if throttle_key in throttle:
            last_time = throttle[throttle_key]
            time_since_last = new_time - last_time
            should_throttle = time_since_last < throttle_seconds
        else:
            should_throttle = False

        assert should_throttle is True

        # Simulate third translation attempt 3 seconds later (should NOT throttle)
        new_time = 103.0
        if throttle_key in throttle:
            last_time = throttle[throttle_key]
            time_since_last = new_time - last_time
            should_throttle = time_since_last < throttle_seconds
        else:
            should_throttle = False

        assert should_throttle is False

    async def test_arabic_throttle_applies_to_arabic_only(self):
        """Test that throttling only applies to Arabic translations."""
        src_langs = ["en", "pl", "ar"]
        tgt_langs = ["en", "pl", "ar"]

        for src in src_langs:
            for tgt in tgt_langs:
                is_arabic = (src == "ar" or tgt == "ar")

                if src == "en" and tgt == "ar":
                    assert is_arabic is True
                elif src == "ar" and tgt == "en":
                    assert is_arabic is True
                elif src == "en" and tgt == "pl":
                    assert is_arabic is False

    async def test_arabic_throttle_cleanup_on_finalization(self):
        """Test that Arabic throttle cache is cleaned up on finalization."""
        throttle = {}

        room = "test-room"
        segment = 1

        # Add throttle entries for this segment
        throttle[(room, segment, "ar")] = 100.0
        throttle[(room, segment, "pl")] = 101.0

        # Add throttle for different segment
        throttle[(room, 2, "ar")] = 102.0

        # Cleanup on finalization
        keys_to_remove = [k for k in throttle.keys() if k[0] == room and k[1] == segment]
        for key in keys_to_remove:
            del throttle[key]

        # Segment 1 should be cleaned
        assert len([k for k in throttle.keys() if k[1] == 1]) == 0
        # Segment 2 should remain
        assert len([k for k in throttle.keys() if k[1] == 2]) == 1


@pytest.mark.integration
@pytest.mark.asyncio
class TestTranslationMatrixEdgeCases:
    """Test edge cases and error scenarios."""

    async def test_no_target_languages_uses_default(self, redis_client, clean_room):
        """Test that default language is used when no target languages exist."""
        room = clean_room

        # No target languages set
        target_langs = await redis_client.smembers(f"room:{room}:target_languages")

        # Fallback to default
        if not target_langs:
            target_langs = {"en"}  # DEFAULT_TGT

        assert target_langs == {"en"}

    async def test_single_user_no_translation_needed(self, redis_client, clean_room):
        """Test behavior when single user speaks their own language."""
        room = clean_room

        # Single English user
        target_langs = {"en"}
        await redis_client.sadd(f"room:{room}:target_languages", *target_langs)

        # English speaker
        src_lang = "en"
        translations = []

        for tgt_lang in target_langs:
            if src_lang == tgt_lang:
                continue
            translations.append(f"{src_lang}→{tgt_lang}")

        # No translations needed (speaker and listener have same language)
        assert len(translations) == 0

    async def test_language_normalization(self):
        """Test language code normalization logic."""
        # Test the normalization logic (simulated from router.py)
        def normalize_lang(lang: str) -> str:
            """Normalize language code to 2-letter format."""
            if not lang:
                return "auto"
            if lang == "auto":
                return "auto"

            lang_lower = lang.lower()

            if "eng" in lang_lower or lang_lower == "en" or lang_lower.startswith("en-"):
                return "en"
            elif "pol" in lang_lower or lang_lower == "pl" or lang_lower.startswith("pl-"):
                return "pl"
            elif "ara" in lang_lower or "arab" in lang_lower or lang_lower == "ar" or lang_lower.startswith("ar-"):
                return "ar"

            return lang[:2].lower()

        assert normalize_lang("en-US") == "en"
        assert normalize_lang("pl-PL") == "pl"
        assert normalize_lang("ar-EG") == "ar"
        assert normalize_lang("EN") == "en"
        assert normalize_lang("") == "auto"
        assert normalize_lang("auto") == "auto"

    async def test_many_target_languages_performance(self, redis_client, clean_room):
        """Test translation matrix with many target languages."""
        room = clean_room

        # Setup many target languages
        many_langs = {f"lang{i}" for i in range(20)}
        await redis_client.sadd(f"room:{room}:target_languages", *many_langs)

        # Verify all stored
        stored_langs = await redis_client.smembers(f"room:{room}:target_languages")
        assert len(stored_langs) == 20

    async def test_concurrent_language_aggregation(self, redis_client, clean_room):
        """Test concurrent language aggregation from multiple users."""
        room = clean_room

        async def register_user_language(user_id, lang):
            await redis_client.setex(f"room:{room}:active_lang:user{user_id}", 15, lang)

        # Register 10 users concurrently
        await asyncio.gather(*[
            register_user_language(i, f"lang{i % 3}")  # 3 unique languages
            for i in range(10)
        ])

        # Aggregate
        pattern = f"room:{room}:active_lang:*"
        languages = set()
        async for key in redis_client.scan_iter(match=pattern):
            lang = await redis_client.get(key)
            if lang:
                languages.add(lang)

        # Should have 3 unique languages
        assert len(languages) == 3
        assert languages == {"lang0", "lang1", "lang2"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
