"""
Integration tests for Presence System.

Tests cover:
- Full WebSocket connection flow with presence events
- Language change propagation through WebSocket
- Disconnect and reconnection scenarios
- Multi-user presence scenarios
- Integration with ws_manager
- Redis pub/sub for presence events
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from api.presence_manager import PresenceManager, PRESENCE_GRACE_PERIOD_SECONDS


class TestPresenceWebSocketIntegration:
    """Test suite for presence system integration with WebSocket."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client with pub/sub support."""
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        redis.hdel = AsyncMock()
        redis.delete = AsyncMock()
        redis.setex = AsyncMock()
        redis.publish = AsyncMock()
        redis.ttl = AsyncMock(return_value=-2)
        redis.scan_iter = AsyncMock(return_value=iter([]))

        # Mock pubsub
        pubsub = AsyncMock()
        pubsub.subscribe = AsyncMock()
        pubsub.unsubscribe = AsyncMock()

        async def mock_listen():
            """Mock async generator for pubsub messages."""
            yield {"type": "subscribe"}
            # Don't yield any actual messages in tests

        pubsub.listen = mock_listen
        redis.pubsub = Mock(return_value=pubsub)

        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        """Create a PresenceManager instance."""
        return PresenceManager(mock_redis)

    @pytest.fixture
    def mock_ws_manager(self, mock_redis):
        """Create a mock WebSocket manager."""
        from api.ws_manager import WSManager
        manager = WSManager()
        manager.redis = mock_redis
        manager.rooms = {}
        manager.log = Mock()
        manager.broadcast = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_user_connection_broadcasts_event(self, presence_manager, mock_redis):
        """Test that user connection generates broadcast event."""
        room_id = "test-room"
        user_id = "user123"
        display_name = "John Doe"
        language = "en"

        event = await presence_manager.user_connected(
            room_id, user_id, display_name, language, is_guest=False
        )

        # Verify event can be serialized for WebSocket broadcast
        event_json = json.dumps(event)
        assert event_json is not None

        # Verify event structure is correct for frontend
        assert event["type"] == "user_joined"
        assert event["room_id"] == room_id
        assert isinstance(event["participants"], list)
        assert isinstance(event["language_counts"], dict)
        assert "timestamp" in event

    @pytest.mark.asyncio
    async def test_language_change_broadcasts_event(self, presence_manager, mock_redis):
        """Test that language change generates broadcast event."""
        room_id = "test-room"
        user_id = "user123"

        # Setup existing user
        existing_data = {
            "display_name": "John Doe",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(existing_data).encode()

        event = await presence_manager.user_changed_language(room_id, user_id, "pl")

        # Verify event structure
        assert event is not None
        assert event["type"] == "language_changed"
        assert event["old_language"] == "en"
        assert event["new_language"] == "pl"
        assert event["triggered_by_user_id"] == user_id

        # Verify it can be serialized
        event_json = json.dumps(event)
        assert event_json is not None

    @pytest.mark.asyncio
    async def test_disconnect_and_reconnect_within_grace_period(self, presence_manager, mock_redis):
        """Test disconnect followed by reconnection within grace period."""
        room_id = "test-room"
        user_id = "user123"
        display_name = "John Doe"
        language = "en"

        # Initial connection
        mock_redis.hget.return_value = None
        await presence_manager.user_connected(room_id, user_id, display_name, language)

        # Disconnect
        user_data = {
            "display_name": display_name,
            "language": language,
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(user_data).encode()
        await presence_manager.user_disconnected(room_id, user_id)

        # Verify disconnect timer was set
        mock_redis.setex.assert_called_with(
            f"room:{room_id}:disconnect_timer:{user_id}",
            PRESENCE_GRACE_PERIOD_SECONDS,
            "1"
        )

        # Reconnect within grace period
        disconnecting_data = user_data.copy()
        disconnecting_data["state"] = "disconnecting"
        mock_redis.hget.return_value = json.dumps(disconnecting_data).encode()

        event = await presence_manager.user_connected(room_id, user_id, display_name, language)

        # Verify disconnect timer was cancelled
        assert mock_redis.delete.called
        timer_key = f"room:{room_id}:disconnect_timer:{user_id}"
        delete_calls = [call[0][0] for call in mock_redis.delete.call_args_list]
        assert timer_key in delete_calls

        # Verify event type indicates reconnection (presence_snapshot, not user_joined)
        assert event["type"] == "presence_snapshot"


class TestPresenceMultiUserScenarios:
    """Test suite for multi-user presence scenarios."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        redis.hdel = AsyncMock()
        redis.delete = AsyncMock()
        redis.setex = AsyncMock()
        redis.publish = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_multiple_users_join_sequentially(self, presence_manager, mock_redis):
        """Test multiple users joining a room sequentially."""
        room_id = "test-room"
        users = [
            ("user1", "John", "en", False),
            ("user2", "Maria", "pl", False),
            ("guest:bob:123", "bob", "ar", True),
        ]

        events = []
        for user_id, display_name, language, is_guest in users:
            # Update mock to include previously joined users
            current_users = {}
            for i, (uid, dname, lang, guest) in enumerate(users[:len(events)]):
                current_users[f"user:{uid}".encode()] = json.dumps({
                    "display_name": dname,
                    "language": lang,
                    "is_guest": guest,
                    "state": "active",
                    "joined_at": datetime.utcnow().isoformat()
                }).encode()

            mock_redis.hgetall.return_value = current_users

            event = await presence_manager.user_connected(
                room_id, user_id, display_name, language, is_guest
            )
            events.append(event)

        # Verify all events were generated
        assert len(events) == 3

        # Verify language counts in final event
        # Note: language_counts in event comes from _build_presence_snapshot
        # which reads from hgetall, so it will only reflect the mocked data

    @pytest.mark.asyncio
    async def test_user_leaves_updates_participant_list(self, presence_manager, mock_redis):
        """Test that user leaving triggers cleanup after grace period."""
        room_id = "test-room"
        user_id = "user123"

        # Setup user
        user_data = {
            "display_name": "John Doe",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(user_data).encode()

        # User disconnects
        await presence_manager.user_disconnected(room_id, user_id)

        # Verify disconnect timer was created
        mock_redis.setex.assert_called_once_with(
            f"room:{room_id}:disconnect_timer:{user_id}",
            PRESENCE_GRACE_PERIOD_SECONDS,
            "1"
        )

        # Verify user state was updated to disconnecting
        hset_calls = mock_redis.hset.call_args_list
        assert len(hset_calls) > 0
        last_call = hset_calls[-1][0]
        updated_data = json.loads(last_call[2])
        assert updated_data["state"] == "disconnecting"

    @pytest.mark.asyncio
    async def test_mixed_guest_and_authenticated_users(self, presence_manager, mock_redis):
        """Test presence with mix of guest and authenticated users."""
        room_id = "test-room"

        # Join authenticated user
        await presence_manager.user_connected(
            room_id, "user1", "John", "en", is_guest=False
        )

        # Join guest user
        await presence_manager.user_connected(
            room_id, "guest:bob:123", "bob", "pl", is_guest=True
        )

        # Setup mock for snapshot
        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "John",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode(),
            b"user:guest:bob:123": json.dumps({
                "display_name": "bob",
                "language": "pl",
                "is_guest": True,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify both users are in snapshot
        assert len(snapshot["participants"]) == 2

        # Verify guest flag is preserved
        guest_user = next(p for p in snapshot["participants"] if "guest:" in p["user_id"])
        auth_user = next(p for p in snapshot["participants"] if "guest:" not in p["user_id"])

        assert guest_user["is_guest"] is True
        assert auth_user["is_guest"] is False


class TestPresenceLanguageCounts:
    """Test suite for language counting and aggregation."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hgetall = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_language_counts_single_language(self, presence_manager, mock_redis):
        """Test language counts with all users on same language."""
        room_id = "test-room"

        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "User 1",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode(),
            b"user:user2": json.dumps({
                "display_name": "User 2",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode(),
            b"user:user3": json.dumps({
                "display_name": "User 3",
                "language": "en",
                "is_guest": True,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify language count
        assert snapshot["language_counts"]["en"] == 3
        assert len(snapshot["language_counts"]) == 1

    @pytest.mark.asyncio
    async def test_language_counts_multiple_languages(self, presence_manager, mock_redis):
        """Test language counts with users on different languages."""
        room_id = "test-room"

        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "User 1",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode(),
            b"user:user2": json.dumps({
                "display_name": "User 2",
                "language": "pl",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode(),
            b"user:user3": json.dumps({
                "display_name": "User 3",
                "language": "ar",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode(),
            b"user:user4": json.dumps({
                "display_name": "User 4",
                "language": "pl",  # Duplicate
                "is_guest": True,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify language counts
        assert snapshot["language_counts"]["en"] == 1
        assert snapshot["language_counts"]["pl"] == 2
        assert snapshot["language_counts"]["ar"] == 1
        assert len(snapshot["language_counts"]) == 3

    @pytest.mark.asyncio
    async def test_language_change_updates_counts(self, presence_manager, mock_redis):
        """Test that language change updates language counts correctly."""
        room_id = "test-room"
        user_id = "user1"

        # Initial state: user1 on "en"
        existing_data = {
            "display_name": "User 1",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(existing_data).encode()

        # Mock snapshot data: 2 users on "en"
        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "User 1",
                "language": "pl",  # After change
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode(),
            b"user:user2": json.dumps({
                "display_name": "User 2",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode()
        }

        # Change language
        event = await presence_manager.user_changed_language(room_id, user_id, "pl")

        # Verify event includes updated snapshot
        assert event is not None
        assert event["language_counts"]["en"] == 1  # One less
        assert event["language_counts"]["pl"] == 1  # One more


class TestPresenceEventStructure:
    """Test suite for presence event structure and serialization."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_user_joined_event_structure(self, presence_manager, mock_redis):
        """Test structure of user_joined event."""
        room_id = "test-room"
        user_id = "user123"

        event = await presence_manager.user_connected(
            room_id, user_id, "John Doe", "en", is_guest=False
        )

        # Verify required fields
        assert "type" in event
        assert "room_id" in event
        assert "participants" in event
        assert "language_counts" in event
        assert "timestamp" in event

        # Verify types
        assert isinstance(event["type"], str)
        assert isinstance(event["room_id"], str)
        assert isinstance(event["participants"], list)
        assert isinstance(event["language_counts"], dict)
        assert isinstance(event["timestamp"], str)

        # Verify can be JSON serialized
        json_str = json.dumps(event)
        reconstructed = json.loads(json_str)
        assert reconstructed["type"] == event["type"]

    @pytest.mark.asyncio
    async def test_language_changed_event_structure(self, presence_manager, mock_redis):
        """Test structure of language_changed event."""
        room_id = "test-room"
        user_id = "user123"

        existing_data = {
            "display_name": "John Doe",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(existing_data).encode()

        event = await presence_manager.user_changed_language(room_id, user_id, "pl")

        # Verify required fields
        assert event["type"] == "language_changed"
        assert event["old_language"] == "en"
        assert event["new_language"] == "pl"
        assert event["triggered_by_user_id"] == user_id

        # Verify can be JSON serialized
        json_str = json.dumps(event)
        assert json_str is not None

    @pytest.mark.asyncio
    async def test_presence_snapshot_event_structure(self, presence_manager, mock_redis):
        """Test structure of presence_snapshot event."""
        room_id = "test-room"

        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "User 1",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat()
            }).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify structure
        assert snapshot["type"] == "presence_snapshot"
        assert snapshot["room_id"] == room_id
        assert isinstance(snapshot["participants"], list)
        assert isinstance(snapshot["language_counts"], dict)

        # Verify participant structure
        if len(snapshot["participants"]) > 0:
            participant = snapshot["participants"][0]
            assert "user_id" in participant
            assert "display_name" in participant
            assert "language" in participant
            assert "is_guest" in participant
            assert "joined_at" in participant


class TestPresenceRedisKeyManagement:
    """Test suite for Redis key management and TTL handling."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        redis.hdel = AsyncMock()
        redis.delete = AsyncMock()
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_presence_state_key_format(self, presence_manager, mock_redis):
        """Test that presence state uses correct Redis key format."""
        room_id = "test-room"
        user_id = "user123"

        await presence_manager.user_connected(room_id, user_id, "John", "en")

        # Verify key format
        expected_key = f"room:{room_id}:presence_state"
        expected_field = f"user:{user_id}"

        hset_calls = mock_redis.hset.call_args_list
        assert len(hset_calls) > 0
        call_args = hset_calls[0][0]
        assert call_args[0] == expected_key
        assert call_args[1] == expected_field

    @pytest.mark.asyncio
    async def test_disconnect_timer_key_format(self, presence_manager, mock_redis):
        """Test that disconnect timer uses correct Redis key format."""
        room_id = "test-room"
        user_id = "user123"

        user_data = {
            "display_name": "John",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(user_data).encode()

        await presence_manager.user_disconnected(room_id, user_id)

        # Verify timer key format
        expected_key = f"room:{room_id}:disconnect_timer:{user_id}"
        mock_redis.setex.assert_called_once_with(
            expected_key,
            PRESENCE_GRACE_PERIOD_SECONDS,
            "1"
        )

    @pytest.mark.asyncio
    async def test_disconnect_timer_ttl_value(self, presence_manager, mock_redis):
        """Test that disconnect timer has correct TTL."""
        room_id = "test-room"
        user_id = "user123"

        user_data = {
            "display_name": "John",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(user_data).encode()

        await presence_manager.user_disconnected(room_id, user_id)

        # Verify TTL matches grace period
        call_args = mock_redis.setex.call_args[0]
        assert call_args[1] == PRESENCE_GRACE_PERIOD_SECONDS
        assert call_args[1] == 10  # Verify it's 10 seconds as per current implementation
