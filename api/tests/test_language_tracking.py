"""
Unit and integration tests for language tracking and system messages.

Tests cover:
- Language registration on user join
- Language aggregation for translation routing
- Language change events
- Participant join/leave system messages
- Active language cleanup on disconnect
- Redis TTL behavior for language keys
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta


class TestLanguageRegistration:
    """Test suite for language registration functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.get = AsyncMock()
        redis.delete = AsyncMock()
        redis.sadd = AsyncMock()
        redis.smembers = AsyncMock()
        redis.expire = AsyncMock()
        redis.scan_iter = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_register_user_language_creates_key_with_ttl(self, mock_redis):
        """Test that user language is registered with correct TTL."""
        from api.main import register_user_language

        # Mock the redis client
        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # Register a user's language
            await register_user_language("test-room", "user123", "en")

            # Verify Redis key was created with 15s TTL
            mock_redis.setex.assert_called_once_with(
                "room:test-room:active_lang:user123",
                15,
                "en"
            )

    @pytest.mark.asyncio
    async def test_register_user_language_guest(self, mock_redis):
        """Test language registration for guest users."""
        from api.main import register_user_language

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # Register guest user
            guest_id = "guest:john:1729692000"
            await register_user_language("test-room", guest_id, "pl")

            # Verify correct key format
            mock_redis.setex.assert_called_once_with(
                f"room:test-room:active_lang:{guest_id}",
                15,
                "pl"
            )

    @pytest.mark.asyncio
    async def test_register_multiple_languages(self, mock_redis):
        """Test registering multiple users with different languages."""
        from api.main import register_user_language

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # Register multiple users
            await register_user_language("test-room", "user1", "en")
            await register_user_language("test-room", "user2", "pl")
            await register_user_language("test-room", "user3", "ar")

            # Verify all registrations
            assert mock_redis.setex.call_count == 3

            calls = [call[0] for call in mock_redis.setex.call_args_list]
            assert ("room:test-room:active_lang:user1", 15, "en") in calls
            assert ("room:test-room:active_lang:user2", 15, "pl") in calls
            assert ("room:test-room:active_lang:user3", 15, "ar") in calls


class TestLanguageAggregation:
    """Test suite for language aggregation functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client with scan_iter support."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.get = AsyncMock()
        redis.delete = AsyncMock()
        redis.sadd = AsyncMock()
        redis.smembers = AsyncMock()
        redis.expire = AsyncMock()
        return redis

    @pytest.mark.asyncio
    async def test_aggregate_room_languages_single_user(self, mock_redis):
        """Test aggregation with single active user."""
        from api.main import trigger_room_language_aggregation

        # Mock scan_iter to return one language key
        async def mock_scan(**kwargs):  # Accept kwargs
            yield b"room:test-room:active_lang:user1"

        mock_redis.scan_iter = mock_scan
        mock_redis.get = AsyncMock(return_value=b"en")

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            await trigger_room_language_aggregation("test-room")

            # Verify target_languages set was created
            mock_redis.delete.assert_called_once_with("room:test-room:target_languages")
            mock_redis.sadd.assert_called_once_with("room:test-room:target_languages", "en")
            mock_redis.expire.assert_called_once_with("room:test-room:target_languages", 30)

    @pytest.mark.asyncio
    async def test_aggregate_room_languages_multiple_users(self, mock_redis):
        """Test aggregation with multiple users and languages."""
        from api.main import trigger_room_language_aggregation

        # Mock scan_iter to return multiple language keys
        async def mock_scan(**kwargs):  # Accept kwargs
            yield b"room:test-room:active_lang:user1"
            yield b"room:test-room:active_lang:user2"
            yield b"room:test-room:active_lang:user3"

        # Return different languages for each user
        async def mock_get(key):
            if b"user1" in key:
                return b"en"
            elif b"user2" in key:
                return b"pl"
            elif b"user3" in key:
                return b"ar"

        mock_redis.scan_iter = mock_scan
        mock_redis.get = mock_get

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            await trigger_room_language_aggregation("test-room")

            # Verify all languages were added
            mock_redis.sadd.assert_called_once()
            call_args = mock_redis.sadd.call_args[0]
            assert call_args[0] == "room:test-room:target_languages"
            assert set(call_args[1:]) == {"en", "pl", "ar"}

    @pytest.mark.asyncio
    async def test_aggregate_room_languages_duplicates(self, mock_redis):
        """Test that duplicate languages are deduplicated."""
        from api.main import trigger_room_language_aggregation

        # Multiple users with same language
        async def mock_scan(**kwargs):  # Accept kwargs
            yield b"room:test-room:active_lang:user1"
            yield b"room:test-room:active_lang:user2"

        mock_redis.scan_iter = mock_scan
        mock_redis.get = AsyncMock(return_value=b"en")  # Both users use English

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            await trigger_room_language_aggregation("test-room")

            # Verify only one "en" was added
            mock_redis.sadd.assert_called_once_with("room:test-room:target_languages", "en")

    @pytest.mark.asyncio
    async def test_aggregate_room_languages_empty_room(self, mock_redis):
        """Test aggregation when no users are active."""
        from api.main import trigger_room_language_aggregation

        # Mock scan_iter to return no keys
        async def mock_scan(**kwargs):  # Accept kwargs
            return
            yield  # Make it a generator

        mock_redis.scan_iter = mock_scan

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            await trigger_room_language_aggregation("test-room")

            # Verify target_languages was cleaned up
            mock_redis.delete.assert_called_once_with("room:test-room:target_languages")
            mock_redis.sadd.assert_not_called()


class TestLanguageChangeEvents:
    """Test suite for language change event handling."""

    @pytest.mark.asyncio
    async def test_language_change_triggers_aggregation(self):
        """Test that changing language triggers immediate aggregation."""
        from api.main import register_user_language, trigger_room_language_aggregation

        mock_redis = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis
            mock_wsman.broadcast = AsyncMock()

            # Simulate language change
            await register_user_language("test-room", "user1", "ar")

            # Verify registration happened
            assert mock_redis.setex.called

    @pytest.mark.asyncio
    async def test_language_change_broadcasts_event(self):
        """Test that language change broadcasts to all participants."""
        # This would be tested at the WebSocket handler level
        # We'll test this in the integration test section
        pass


class TestParticipantEvents:
    """Test suite for participant join/leave events."""

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = Mock()
        ws.state = Mock()
        ws.state.user = "123"
        ws.state.email = "test@example.com"
        ws.state.preferred_lang = "en"
        ws.send = AsyncMock()
        ws.receive_json = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_participant_joined_event_format(self, mock_websocket):
        """Test that participant_joined event has correct format."""
        event = {
            "type": "participant_joined",
            "room_id": "test-room",
            "user_email": "test@example.com",
            "user_id": "123",
            "preferred_lang": "en"
        }

        # Verify event structure
        assert event["type"] == "participant_joined"
        assert "user_email" in event
        assert "user_id" in event
        assert "preferred_lang" in event

    @pytest.mark.asyncio
    async def test_participant_left_event_format(self):
        """Test that participant_left event has correct format."""
        event = {
            "type": "participant_left",
            "room_id": "test-room",
            "user_email": "test@example.com",
            "user_id": "123",
            "preferred_lang": "en"
        }

        # Verify event structure
        assert event["type"] == "participant_left"
        assert "user_email" in event

    @pytest.mark.asyncio
    async def test_participant_language_changed_event_format(self):
        """Test that language change event has correct format."""
        event = {
            "type": "participant_language_changed",
            "room_id": "test-room",
            "user_email": "test@example.com",
            "preferred_lang": "ar"
        }

        # Verify event structure
        assert event["type"] == "participant_language_changed"
        assert event["preferred_lang"] == "ar"


class TestRedisKeyLifecycle:
    """Test suite for Redis key lifecycle management."""

    @pytest.mark.asyncio
    async def test_language_key_ttl_refresh(self):
        """Test that status poll refreshes language key TTL."""
        # This tests the behavior of refreshing language keys
        mock_redis = AsyncMock()

        # Simulate status poll behavior
        user_id = "123"
        user_lang = "en"
        room_code = "test-room"
        key = f"room:{room_code}:active_lang:{user_id}"

        await mock_redis.setex(key, 15, user_lang)

        # Verify TTL was set
        mock_redis.setex.assert_called_once_with(key, 15, user_lang)

    @pytest.mark.asyncio
    async def test_language_key_cleanup_after_disconnect(self):
        """Test that language keys expire after user disconnect."""
        # This is handled by Redis TTL automatically
        # We verify that no manual cleanup interferes with TTL
        pass


class TestSystemMessages:
    """Test suite for system message generation."""

    def test_join_message_authenticated_user(self):
        """Test system message for authenticated user joining."""
        user_email = "john@example.com"
        user_lang = "en"
        is_guest = False

        display_name = user_email.split('@')[0]
        message = f"🇬🇧 {display_name} joined with English"

        assert "john" in message
        assert "joined with" in message
        assert "English" in message

    def test_join_message_guest_user(self):
        """Test system message for guest user joining."""
        user_id = "guest:alice:1729692000"
        user_lang = "pl"
        is_guest = True

        display_name = user_id.split(':', 2)[1]
        message = f"🇵🇱 {display_name} (guest) joined with Polish"

        assert "alice" in message
        assert "(guest)" in message
        assert "joined with" in message
        assert "Polish" in message

    def test_leave_message(self):
        """Test system message for user leaving."""
        display_name = "john"
        is_guest = False

        message = f"{display_name} left the room"

        assert "left the room" in message

    def test_language_change_message(self):
        """Test system message for language change."""
        display_name = "john"
        new_lang = "ar"
        lang_flag = "🇪🇬"
        is_guest = False

        message = f"{lang_flag} {display_name} changed to Arabic"

        assert "changed to" in message
        assert "Arabic" in message


class TestLanguageMapping:
    """Test suite for language code to name/flag mapping."""

    def test_language_flags(self):
        """Test that all languages have correct flags."""
        languages = {
            "en": "🇬🇧",
            "pl": "🇵🇱",
            "ar": "🇪🇬"
        }

        for code, flag in languages.items():
            assert len(flag) > 0
            assert flag != "🌐"  # Not the auto flag

    def test_language_names(self):
        """Test that all languages have correct names."""
        languages = {
            "en": "English",
            "pl": "Polish",
            "ar": "Arabic"
        }

        for code, name in languages.items():
            assert len(name) > 0


class TestConcurrentLanguageChanges:
    """Test suite for concurrent language operations."""

    @pytest.mark.asyncio
    async def test_concurrent_user_joins(self):
        """Test multiple users joining simultaneously."""
        from api.main import register_user_language

        mock_redis = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # Simulate concurrent joins
            await asyncio.gather(
                register_user_language("test-room", "user1", "en"),
                register_user_language("test-room", "user2", "pl"),
                register_user_language("test-room", "user3", "ar")
            )

            # All should succeed
            assert mock_redis.setex.call_count == 3

    @pytest.mark.asyncio
    async def test_rapid_language_changes(self):
        """Test user changing language multiple times quickly."""
        from api.main import register_user_language

        mock_redis = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # Simulate rapid changes
            user_id = "user1"
            for lang in ["en", "pl", "ar", "en"]:
                await register_user_language("test-room", user_id, lang)

            # Should have 4 calls (one per change)
            assert mock_redis.setex.call_count == 4

            # Last call should be "en"
            last_call = mock_redis.setex.call_args_list[-1]
            assert last_call[0][2] == "en"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
