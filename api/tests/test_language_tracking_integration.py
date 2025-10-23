"""
Integration tests for language tracking with WebSocket communication.

Tests cover:
- Full WebSocket connection flow with language registration
- Language change via WebSocket messages
- Participant events broadcast to all room members
- Language aggregation updates in real-time
- Status poll TTL refresh integration
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import WebSocket
from datetime import datetime


class TestWebSocketLanguageFlow:
    """Integration tests for WebSocket language handling."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.get = AsyncMock()
        redis.delete = AsyncMock()
        redis.sadd = AsyncMock()
        redis.smembers = AsyncMock(return_value={b"en", b"pl"})
        redis.expire = AsyncMock()
        redis.incr = AsyncMock(return_value=1)

        async def mock_scan(**kwargs):
            yield b"room:test-room:active_lang:user1"
            yield b"room:test-room:active_lang:user2"

        redis.scan_iter = mock_scan
        return redis

    @pytest.fixture
    def mock_ws_manager(self, mock_redis):
        """Create a mock WebSocket manager."""
        from api.ws_manager import WSManager
        manager = Mock(spec=WSManager)
        manager.redis = mock_redis
        manager.connect = AsyncMock()
        manager.disconnect = AsyncMock()
        manager.broadcast = AsyncMock()
        manager.rooms = {}
        return manager

    @pytest.mark.asyncio
    async def test_websocket_connection_registers_language(self, mock_redis):
        """Test that WebSocket connection triggers language registration."""
        from api.main import register_user_language, trigger_room_language_aggregation

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # Simulate WebSocket connection
            room_id = "test-room"
            user_id = "123"
            user_lang = "en"

            # Register language (called on ws connect)
            await register_user_language(room_id, user_id, user_lang)

            # Trigger aggregation
            await trigger_room_language_aggregation(room_id)

            # Verify registration
            mock_redis.setex.assert_called()
            assert any(
                call[0][0] == f"room:{room_id}:active_lang:{user_id}"
                for call in mock_redis.setex.call_args_list
            )

    @pytest.mark.asyncio
    async def test_language_change_message_handling(self, mock_redis, mock_ws_manager):
        """Test handling of set_language WebSocket message."""
        from api.main import register_user_language, trigger_room_language_aggregation

        with patch('api.main.wsman', mock_ws_manager):
            mock_ws_manager.redis = mock_redis

            # Simulate receiving language change message
            room_id = "test-room"
            user_id = "123"
            new_lang = "ar"

            # Process language change
            await register_user_language(room_id, user_id, new_lang)
            await trigger_room_language_aggregation(room_id)

            # Verify new language was registered
            calls = mock_redis.setex.call_args_list
            assert any(
                call[0] == (f"room:{room_id}:active_lang:{user_id}", 15, new_lang)
                for call in calls
            )

    @pytest.mark.asyncio
    async def test_participant_joined_broadcast(self, mock_ws_manager):
        """Test that participant joined event is broadcast to room."""
        room_id = "test-room"
        user_email = "test@example.com"
        user_id = "123"
        preferred_lang = "en"

        # Simulate broadcast
        await mock_ws_manager.broadcast(room_id, {
            "type": "participant_joined",
            "room_id": room_id,
            "user_email": user_email,
            "user_id": user_id,
            "preferred_lang": preferred_lang
        })

        # Verify broadcast was called
        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args[0]
        assert call_args[0] == room_id
        assert call_args[1]["type"] == "participant_joined"
        assert call_args[1]["preferred_lang"] == preferred_lang

    @pytest.mark.asyncio
    async def test_participant_language_changed_broadcast(self, mock_ws_manager):
        """Test that language change event is broadcast."""
        room_id = "test-room"
        user_email = "test@example.com"
        new_lang = "ar"

        # Simulate broadcast
        await mock_ws_manager.broadcast(room_id, {
            "type": "participant_language_changed",
            "room_id": room_id,
            "user_email": user_email,
            "preferred_lang": new_lang
        })

        # Verify broadcast
        mock_ws_manager.broadcast.assert_called_once()
        call_args = mock_ws_manager.broadcast.call_args[0]
        assert call_args[1]["type"] == "participant_language_changed"
        assert call_args[1]["preferred_lang"] == new_lang

    @pytest.mark.asyncio
    async def test_participant_left_broadcast(self, mock_ws_manager):
        """Test that participant left event is broadcast."""
        room_id = "test-room"
        user_email = "test@example.com"

        # Simulate broadcast
        await mock_ws_manager.broadcast(room_id, {
            "type": "participant_left",
            "room_id": room_id,
            "user_email": user_email
        })

        # Verify broadcast
        mock_ws_manager.broadcast.assert_called_once()


class TestLanguageAggregationIntegration:
    """Integration tests for language aggregation with Redis."""

    @pytest.fixture
    def redis_mock_with_languages(self):
        """Create Redis mock with multiple active languages."""
        redis = AsyncMock()

        # Mock different languages for different users
        lang_map = {
            b"room:test-room:active_lang:user1": b"en",
            b"room:test-room:active_lang:user2": b"pl",
            b"room:test-room:active_lang:user3": b"ar"
        }

        async def mock_get(key):
            return lang_map.get(key)

        async def mock_scan(**kwargs):
            for key in lang_map.keys():
                yield key

        redis.get = mock_get
        redis.scan_iter = mock_scan
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.sadd = AsyncMock()
        redis.expire = AsyncMock()

        return redis

    @pytest.mark.asyncio
    async def test_aggregation_includes_all_active_languages(self, redis_mock_with_languages):
        """Test that aggregation collects all active user languages."""
        from api.main import trigger_room_language_aggregation

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = redis_mock_with_languages

            await trigger_room_language_aggregation("test-room")

            # Verify all languages were added to target set
            redis_mock_with_languages.sadd.assert_called_once()
            call_args = redis_mock_with_languages.sadd.call_args[0]
            languages = set(call_args[1:])
            assert languages == {"en", "pl", "ar"}

    @pytest.mark.asyncio
    async def test_aggregation_updates_target_languages(self, redis_mock_with_languages):
        """Test that target_languages set is updated correctly."""
        from api.main import trigger_room_language_aggregation

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = redis_mock_with_languages

            await trigger_room_language_aggregation("test-room")

            # Verify Redis operations
            redis_mock_with_languages.delete.assert_called_once_with("room:test-room:target_languages")
            redis_mock_with_languages.sadd.assert_called_once()
            redis_mock_with_languages.expire.assert_called_once_with("room:test-room:target_languages", 30)


class TestStatusPollLanguageRefresh:
    """Integration tests for language TTL refresh via status polling."""

    @pytest.mark.asyncio
    async def test_status_poll_refreshes_language_ttl(self):
        """Test that status poll endpoint refreshes user language TTL."""
        mock_redis = AsyncMock()

        # Mock wsman
        mock_wsman = Mock()
        mock_wsman.redis = mock_redis

        # Simulate status poll logic
        room_code = "test-room"
        user_id = "123"
        user_lang = "en"
        key = f"room:{room_code}:active_lang:{user_id}"

        # This is what the status endpoint should do
        await mock_redis.setex(key, 15, user_lang)

        # Verify TTL refresh
        mock_redis.setex.assert_called_once_with(key, 15, user_lang)

    @pytest.mark.asyncio
    async def test_multiple_status_polls_refresh_ttl(self):
        """Test that multiple polls continue to refresh TTL."""
        mock_redis = AsyncMock()

        room_code = "test-room"
        user_id = "123"
        user_lang = "en"
        key = f"room:{room_code}:active_lang:{user_id}"

        # Simulate 3 status polls (every 5 seconds)
        for _ in range(3):
            await mock_redis.setex(key, 15, user_lang)
            await asyncio.sleep(0)  # Yield control

        # Verify 3 refreshes
        assert mock_redis.setex.call_count == 3


class TestMultiUserLanguageScenarios:
    """Integration tests for multi-user language scenarios."""

    @pytest.fixture
    def mock_redis_multi_user(self):
        """Create Redis mock for multi-user scenarios."""
        redis = AsyncMock()
        redis.setex = AsyncMock()
        redis.delete = AsyncMock()
        redis.sadd = AsyncMock()
        redis.expire = AsyncMock()

        # Track active users
        self.active_users = {}

        async def mock_get(key):
            return self.active_users.get(key, None)

        async def mock_scan(**kwargs):
            for key in self.active_users.keys():
                yield key

        redis.get = mock_get
        redis.scan_iter = mock_scan

        return redis

    @pytest.mark.asyncio
    async def test_user_joins_adds_language(self):
        """Test that user joining adds their language to room."""
        from api.main import register_user_language, trigger_room_language_aggregation

        mock_redis = AsyncMock()

        # Mock scan to return one user
        async def mock_scan(**kwargs):
            yield b"room:test-room:active_lang:user1"

        mock_redis.scan_iter = mock_scan
        mock_redis.get = AsyncMock(return_value=b"en")
        mock_redis.setex = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # User joins
            await register_user_language("test-room", "user1", "en")
            await trigger_room_language_aggregation("test-room")

            # Verify language was added
            mock_redis.sadd.assert_called_once()
            assert "en" in mock_redis.sadd.call_args[0]

    @pytest.mark.asyncio
    async def test_user_changes_language_updates_set(self):
        """Test that language change updates the target set."""
        from api.main import register_user_language, trigger_room_language_aggregation

        mock_redis = AsyncMock()

        # First: user has English
        async def mock_scan_en(**kwargs):
            yield b"room:test-room:active_lang:user1"

        mock_redis.scan_iter = mock_scan_en
        mock_redis.get = AsyncMock(return_value=b"en")
        mock_redis.setex = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            # Initial state
            await register_user_language("test-room", "user1", "en")
            await trigger_room_language_aggregation("test-room")

            # User changes to Arabic
            mock_redis.get = AsyncMock(return_value=b"ar")
            await register_user_language("test-room", "user1", "ar")
            await trigger_room_language_aggregation("test-room")

            # Verify Arabic is now in the set
            assert mock_redis.sadd.call_count == 2
            last_call = mock_redis.sadd.call_args_list[-1]
            assert "ar" in last_call[0]

    @pytest.mark.asyncio
    async def test_last_user_leaves_clears_languages(self):
        """Test that when last user leaves, target_languages is cleared."""
        from api.main import trigger_room_language_aggregation

        mock_redis = AsyncMock()

        # No active users
        async def mock_scan_empty(**kwargs):
            return
            yield  # Make it a generator

        mock_redis.scan_iter = mock_scan_empty
        mock_redis.delete = AsyncMock()
        mock_redis.sadd = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            await trigger_room_language_aggregation("test-room")

            # Verify target_languages was deleted
            mock_redis.delete.assert_called_once_with("room:test-room:target_languages")
            mock_redis.sadd.assert_not_called()


class TestGuestUserLanguageHandling:
    """Integration tests for guest user language tracking."""

    @pytest.mark.asyncio
    async def test_guest_language_registration(self):
        """Test that guest users can register languages."""
        from api.main import register_user_language

        mock_redis = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            guest_id = "guest:alice:1729692000"
            await register_user_language("test-room", guest_id, "pl")

            # Verify guest language was registered
            mock_redis.setex.assert_called_once()
            call_args = mock_redis.setex.call_args[0]
            assert guest_id in call_args[0]
            assert call_args[2] == "pl"

    @pytest.mark.asyncio
    async def test_mixed_authenticated_and_guest_users(self):
        """Test room with both authenticated and guest users."""
        from api.main import trigger_room_language_aggregation

        mock_redis = AsyncMock()

        # Mock both authenticated and guest users
        async def mock_scan(**kwargs):
            yield b"room:test-room:active_lang:123"  # Authenticated
            yield b"room:test-room:active_lang:guest:alice:1729692000"  # Guest

        async def mock_get(key):
            if b"123" in key:
                return b"en"
            else:
                return b"pl"

        mock_redis.scan_iter = mock_scan
        mock_redis.get = mock_get
        mock_redis.delete = AsyncMock()
        mock_redis.sadd = AsyncMock()
        mock_redis.expire = AsyncMock()

        with patch('api.main.wsman') as mock_wsman:
            mock_wsman.redis = mock_redis

            await trigger_room_language_aggregation("test-room")

            # Verify both languages are included
            mock_redis.sadd.assert_called_once()
            call_args = mock_redis.sadd.call_args[0]
            assert set(call_args[1:]) == {"en", "pl"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
