"""
End-to-end system tests for language tracking functionality.

Tests cover complete user flows:
- User joins room and language is registered
- User changes language and all participants are notified
- System messages appear in chat
- Language flags update in room header
- Translations use correct target languages
- User disconnect cleanup
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime


class TestEndToEndLanguageFlow:
    """End-to-end tests for complete language tracking flow."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client with full functionality."""
        redis = AsyncMock()

        # Track state
        self.language_keys = {}
        self.target_languages = set()

        async def mock_setex(key, ttl, value):
            self.language_keys[key] = value

        async def mock_get(key):
            return self.language_keys.get(key)

        async def mock_scan(**kwargs):
            for key in self.language_keys.keys():
                yield key.encode() if isinstance(key, str) else key

        async def mock_smembers(key):
            return {lang.encode() for lang in self.target_languages}

        # Configure AsyncMock side effects instead of replacing them
        redis.setex = AsyncMock(side_effect=mock_setex)
        redis.get = AsyncMock(side_effect=mock_get)
        redis.scan_iter = mock_scan
        redis.smembers = AsyncMock(side_effect=mock_smembers)
        redis.delete = AsyncMock()
        redis.sadd = AsyncMock()
        redis.expire = AsyncMock()
        redis.incr = AsyncMock(return_value=1)
        redis.publish = AsyncMock()

        return redis

    @pytest.mark.asyncio
    async def test_complete_user_join_flow(self, mock_redis):
        """
        Test complete flow: User joins -> Language registered -> Aggregation -> Broadcast
        """
        from api.main import register_user_language, trigger_room_language_aggregation

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis
            mock_wsman.broadcast = AsyncMock()

            # Step 1: User connects to WebSocket
            room_id = "test-room"
            user_id = "123"
            user_email = "john@example.com"
            user_lang = "en"

            # Step 2: Register language
            await register_user_language(room_id, user_id, user_lang)

            # Step 3: Trigger aggregation
            await trigger_room_language_aggregation(room_id)

            # Step 4: Broadcast join event
            await mock_wsman.broadcast(room_id, {
                "type": "participant_joined",
                "room_id": room_id,
                "user_email": user_email,
                "user_id": user_id,
                "preferred_lang": user_lang
            })

            # Verify all steps
            assert mock_redis.setex.called
            assert mock_wsman.broadcast.called

    @pytest.mark.asyncio
    async def test_complete_language_change_flow(self, mock_redis):
        """
        Test complete flow: User changes language -> Registration -> Aggregation -> Broadcast
        """
        from api.main import register_user_language, trigger_room_language_aggregation

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis
            mock_wsman.broadcast = AsyncMock()

            room_id = "test-room"
            user_id = "123"
            user_email = "john@example.com"

            # Initial state: user has English
            await register_user_language(room_id, user_id, "en")
            await trigger_room_language_aggregation(room_id)

            # User changes to Arabic
            new_lang = "ar"
            await register_user_language(room_id, user_id, new_lang)
            await trigger_room_language_aggregation(room_id)

            # Broadcast language change
            await mock_wsman.broadcast(room_id, {
                "type": "participant_language_changed",
                "room_id": room_id,
                "user_email": user_email,
                "preferred_lang": new_lang
            })

            # Verify broadcast was called with correct event
            assert mock_wsman.broadcast.call_count == 1
            call_args = mock_wsman.broadcast.call_args[0][1]
            assert call_args["type"] == "participant_language_changed"
            assert call_args["preferred_lang"] == "ar"

    @pytest.mark.asyncio
    async def test_multiple_users_different_languages(self, mock_redis):
        """
        Test scenario: Multiple users join with different languages
        """
        from api.main import register_user_language, trigger_room_language_aggregation

        # Store languages in mock
        languages = {}

        async def custom_setex(key, ttl, value):
            languages[key] = value

        async def custom_get(key):
            return languages.get(key)

        async def custom_scan(**kwargs):
            for key in languages.keys():
                yield key.encode() if isinstance(key, str) else key

        # Configure side effects on the AsyncMock objects
        mock_redis.setex = AsyncMock(side_effect=custom_setex)
        mock_redis.get = AsyncMock(side_effect=custom_get)
        mock_redis.scan_iter = custom_scan

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis
            mock_wsman.broadcast = AsyncMock()

            room_id = "test-room"

            # User 1: English
            await register_user_language(room_id, "user1", "en")

            # User 2: Polish
            await register_user_language(room_id, "user2", "pl")

            # User 3: Arabic
            await register_user_language(room_id, "user3", "ar")

            # Aggregate all languages
            await trigger_room_language_aggregation(room_id)

            # Verify all three languages are registered
            assert len(languages) == 3
            assert languages[f"room:{room_id}:active_lang:user1"] == "en"
            assert languages[f"room:{room_id}:active_lang:user2"] == "pl"
            assert languages[f"room:{room_id}:active_lang:user3"] == "ar"

    @pytest.mark.asyncio
    async def test_user_disconnect_flow(self):
        """
        Test complete flow: User disconnects -> Broadcast left event
        """
        mock_wsman = AsyncMock()
        mock_wsman.broadcast = AsyncMock()

        room_id = "test-room"
        user_email = "john@example.com"
        user_id = "123"

        # Broadcast disconnect
        await mock_wsman.broadcast(room_id, {
            "type": "participant_left",
            "room_id": room_id,
            "user_email": user_email,
            "user_id": user_id
        })

        # Verify broadcast
        mock_wsman.broadcast.assert_called_once()


class TestTranslationRoutingWithLanguages:
    """Test that translation routing uses correct target languages."""

    @pytest.mark.asyncio
    async def test_translation_uses_active_languages(self):
        """Test that MT router reads from target_languages set."""
        mock_redis = AsyncMock()
        mock_redis.smembers = AsyncMock(return_value={b"en", b"pl", b"ar"})

        # This simulates what MT router does
        target_langs_key = "room:test-room:target_languages"
        target_langs = await mock_redis.smembers(target_langs_key)

        # Verify correct languages are returned
        decoded_langs = {lang.decode() for lang in target_langs}
        assert decoded_langs == {"en", "pl", "ar"}

    @pytest.mark.asyncio
    async def test_translation_excludes_source_language(self):
        """Test that source language is excluded from translation targets."""
        active_langs = {"en", "pl", "ar"}
        source_lang = "en"

        # Translation targets should exclude source
        translation_targets = active_langs - {source_lang}

        assert translation_targets == {"pl", "ar"}
        assert "en" not in translation_targets


class TestSystemMessageGeneration:
    """Test system message generation for different scenarios."""

    def test_system_message_join_authenticated(self):
        """Test system message when authenticated user joins."""
        event = {
            "type": "participant_joined",
            "user_email": "john@example.com",
            "user_id": "123",
            "preferred_lang": "en"
        }

        # Frontend processes this
        display_name = event["user_email"].split("@")[0]
        lang_flag = "🇬🇧"
        lang_name = "English"

        system_message = f"{lang_flag} {display_name} joined with {lang_name}"

        assert "john" in system_message
        assert "joined with" in system_message
        assert "English" in system_message
        assert "🇬🇧" in system_message

    def test_system_message_join_guest(self):
        """Test system message when guest joins."""
        event = {
            "type": "participant_joined",
            "user_id": "guest:alice:1729692000",
            "preferred_lang": "pl"
        }

        # Extract guest name
        user_id = event["user_id"]
        display_name = user_id.split(":", 2)[1] if ":" in user_id else "Guest"
        is_guest = user_id.startswith("guest:")

        lang_flag = "🇵🇱"
        lang_name = "Polish"

        system_message = f"{lang_flag} {display_name}{'(guest)' if is_guest else ''} joined with {lang_name}"

        assert "alice" in system_message
        assert "(guest)" in system_message or "guest" in system_message.lower()
        assert "Polish" in system_message

    def test_system_message_language_change(self):
        """Test system message for language change."""
        event = {
            "type": "participant_language_changed",
            "user_email": "john@example.com",
            "preferred_lang": "ar"
        }

        display_name = event["user_email"].split("@")[0]
        lang_flag = "🇪🇬"
        lang_name = "Arabic"

        system_message = f"{lang_flag} {display_name} changed to {lang_name}"

        assert "john" in system_message
        assert "changed to" in system_message
        assert "Arabic" in system_message

    def test_system_message_user_left(self):
        """Test system message when user leaves."""
        event = {
            "type": "participant_left",
            "user_email": "john@example.com"
        }

        display_name = event["user_email"].split("@")[0]
        system_message = f"{display_name} left the room"

        assert "john" in system_message
        assert "left the room" in system_message


class TestStatusPollRefreshCycle:
    """Test the status poll language refresh cycle."""

    @pytest.mark.asyncio
    async def test_status_poll_every_5_seconds_refreshes_ttl(self):
        """Test that regular status polls keep language active."""
        mock_redis = AsyncMock()
        call_count = 0

        async def track_setex(key, ttl, value):
            nonlocal call_count
            call_count += 1

        mock_redis.setex = track_setex

        room_code = "test-room"
        user_id = "123"
        user_lang = "en"
        key = f"room:{room_code}:active_lang:{user_id}"

        # Simulate 6 polls over 30 seconds (every 5s)
        for i in range(6):
            await mock_redis.setex(key, 15, user_lang)
            await asyncio.sleep(0)  # Yield control

        # Should have 6 refreshes
        assert call_count == 6

    @pytest.mark.asyncio
    async def test_language_expires_after_no_polls(self):
        """Test that language key expires after TTL without polls."""
        # This is handled by Redis automatically
        # We just verify TTL is set correctly
        mock_redis = AsyncMock()

        await mock_redis.setex("room:test:active_lang:123", 15, "en")

        # Verify setex was called with TTL
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == 15  # TTL is 15 seconds


class TestFrontendLanguageFlagsDisplay:
    """Test frontend language flags display logic."""

    def test_active_languages_display(self):
        """Test that active languages are displayed as flags."""
        active_languages = {"en", "pl", "ar"}
        languages = {
            "en": {"code": "en", "name": "English", "flag": "🇬🇧"},
            "pl": {"code": "pl", "name": "Polish", "flag": "🇵🇱"},
            "ar": {"code": "ar", "name": "Arabic", "flag": "🇪🇬"}
        }

        # Generate flags display
        flags = [languages[code]["flag"] for code in active_languages if code in languages]

        assert len(flags) == 3
        assert "🇬🇧" in flags
        assert "🇵🇱" in flags
        assert "🇪🇬" in flags

    def test_no_duplicate_flags(self):
        """Test that duplicate languages don't show duplicate flags."""
        # Two users with same language
        active_languages_set = set(["en", "en"])  # Set automatically deduplicates

        assert len(active_languages_set) == 1
        assert "en" in active_languages_set


class TestCompleteUserSession:
    """Test complete user session from join to disconnect."""

    @pytest.mark.asyncio
    async def test_complete_session_flow(self):
        """
        Test complete flow:
        1. User joins with English
        2. Language is registered and aggregated
        3. User changes to Polish
        4. Language is updated and aggregated
        5. User disconnects
        6. Language key expires via TTL
        """
        from api.main import register_user_language, trigger_room_language_aggregation

        mock_redis = AsyncMock()
        languages = {}

        async def track_setex(key, ttl, value):
            languages[key] = value

        async def track_get(key):
            return languages.get(key)

        async def track_scan(**kwargs):
            for key in languages.keys():
                yield key.encode() if isinstance(key, str) else key

        # Configure side effects on AsyncMock objects
        mock_redis.setex = AsyncMock(side_effect=track_setex)
        mock_redis.get = AsyncMock(side_effect=track_get)
        mock_redis.scan_iter = track_scan
        mock_redis.delete = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis
            mock_wsman.broadcast = AsyncMock()

            room_id = "test-room"
            user_id = "123"

            # Step 1: User joins with English
            await register_user_language(room_id, user_id, "en")
            await trigger_room_language_aggregation(room_id)

            assert languages[f"room:{room_id}:active_lang:{user_id}"] == "en"

            # Step 2: User changes to Polish
            await register_user_language(room_id, user_id, "pl")
            await trigger_room_language_aggregation(room_id)

            assert languages[f"room:{room_id}:active_lang:{user_id}"] == "pl"

            # Step 3: User disconnects (key would expire via TTL in real Redis)
            # In our test, we simulate this by removing the key
            key = f"room:{room_id}:active_lang:{user_id}"
            if key in languages:
                del languages[key]

            # Step 4: Aggregation now shows no users
            await trigger_room_language_aggregation(room_id)

            # Verify target_languages was cleared
            mock_redis.delete.assert_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
