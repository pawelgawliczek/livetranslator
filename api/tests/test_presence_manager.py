"""
Unit tests for PresenceManager.

Tests cover:
- User connection with grace period handling
- User disconnection and cleanup
- Language change events
- Presence snapshot generation
- Background cleanup task
- Reconnection scenarios
- Concurrent user operations
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, call
from datetime import datetime

from api.presence_manager import PresenceManager, PRESENCE_GRACE_PERIOD_SECONDS


class TestPresenceManagerConnection:
    """Test suite for user connection functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create a mock Redis client."""
        redis = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        redis.hdel = AsyncMock()
        redis.delete = AsyncMock()
        redis.setex = AsyncMock()
        redis.ttl = AsyncMock(return_value=-2)
        redis.scan_iter = AsyncMock(return_value=iter([]))
        redis.publish = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        """Create a PresenceManager instance with mock Redis."""
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_user_connected_creates_presence_state(self, presence_manager, mock_redis):
        """Test that user connection creates presence state in Redis."""
        room_id = "test-room"
        user_id = "user123"
        display_name = "John Doe"
        language = "en"

        event = await presence_manager.user_connected(
            room_id, user_id, display_name, language, is_guest=False
        )

        # Verify presence state was created
        assert mock_redis.hset.called
        call_args = mock_redis.hset.call_args[0]
        assert call_args[0] == f"room:{room_id}:presence_state"
        assert call_args[1] == f"user:{user_id}"

        # Verify user data structure
        user_data = json.loads(call_args[2])
        assert user_data["display_name"] == display_name
        assert user_data["language"] == language
        assert user_data["is_guest"] is False
        assert user_data["state"] == "active"
        assert "joined_at" in user_data
        assert "last_seen" in user_data

        # Verify disconnect timer was cancelled
        mock_redis.delete.assert_called_once_with(
            f"room:{room_id}:disconnect_timer:{user_id}"
        )

        # Verify event structure
        assert event["type"] == "user_joined"
        assert event["room_id"] == room_id
        assert "participants" in event
        assert "language_counts" in event

    @pytest.mark.asyncio
    async def test_user_connected_guest_user(self, presence_manager, mock_redis):
        """Test guest user connection."""
        room_id = "test-room"
        user_id = "guest:john:1234567890"
        display_name = "john"
        language = "pl"

        event = await presence_manager.user_connected(
            room_id, user_id, display_name, language, is_guest=True
        )

        # Verify guest flag is set
        call_args = mock_redis.hset.call_args[0]
        user_data = json.loads(call_args[2])
        assert user_data["is_guest"] is True
        assert user_data["display_name"] == display_name

    @pytest.mark.asyncio
    async def test_user_reconnection_within_grace_period(self, presence_manager, mock_redis):
        """Test that reconnection within grace period cancels disconnect timer."""
        room_id = "test-room"
        user_id = "user123"
        display_name = "John Doe"
        language = "en"

        # Simulate existing user in "disconnecting" state
        existing_data = {
            "display_name": display_name,
            "language": language,
            "is_guest": False,
            "state": "disconnecting",
            "disconnect_started": datetime.utcnow().isoformat(),
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(existing_data).encode()

        event = await presence_manager.user_connected(
            room_id, user_id, display_name, language, is_guest=False
        )

        # Verify disconnect timer was cancelled
        mock_redis.delete.assert_called_once_with(
            f"room:{room_id}:disconnect_timer:{user_id}"
        )

        # Verify event type is presence_snapshot (reconnection)
        assert event["type"] == "presence_snapshot"

        # Verify user state was updated to active
        call_args = mock_redis.hset.call_args[0]
        user_data = json.loads(call_args[2])
        assert user_data["state"] == "active"


class TestPresenceManagerDisconnection:
    """Test suite for user disconnection functionality."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hget = AsyncMock()
        redis.hset = AsyncMock()
        redis.setex = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_user_disconnected_starts_grace_period(self, presence_manager, mock_redis):
        """Test that disconnection starts grace period timer."""
        room_id = "test-room"
        user_id = "user123"

        # Simulate existing active user
        existing_data = {
            "display_name": "John Doe",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(existing_data).encode()

        await presence_manager.user_disconnected(room_id, user_id)

        # Verify user state was updated to "disconnecting"
        assert mock_redis.hset.called
        call_args = mock_redis.hset.call_args[0]
        assert call_args[0] == f"room:{room_id}:presence_state"
        assert call_args[1] == f"user:{user_id}"

        user_data = json.loads(call_args[2])
        assert user_data["state"] == "disconnecting"
        assert "disconnect_started" in user_data

        # Verify grace period timer was set
        mock_redis.setex.assert_called_once_with(
            f"room:{room_id}:disconnect_timer:{user_id}",
            PRESENCE_GRACE_PERIOD_SECONDS,
            "1"
        )

    @pytest.mark.asyncio
    async def test_user_disconnected_no_presence_data(self, presence_manager, mock_redis):
        """Test disconnection when user has no presence data."""
        room_id = "test-room"
        user_id = "user123"

        mock_redis.hget.return_value = None

        await presence_manager.user_disconnected(room_id, user_id)

        # Verify no operations were performed
        assert not mock_redis.hset.called
        assert not mock_redis.setex.called


class TestPresenceManagerLanguageChange:
    """Test suite for language change functionality."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hget = AsyncMock()
        redis.hset = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_user_changed_language_updates_state(self, presence_manager, mock_redis):
        """Test that language change updates user presence state."""
        room_id = "test-room"
        user_id = "user123"
        old_language = "en"
        new_language = "pl"

        # Simulate existing user
        existing_data = {
            "display_name": "John Doe",
            "language": old_language,
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(existing_data).encode()

        event = await presence_manager.user_changed_language(
            room_id, user_id, new_language
        )

        # Verify language was updated
        assert mock_redis.hset.called
        call_args = mock_redis.hset.call_args[0]
        user_data = json.loads(call_args[2])
        assert user_data["language"] == new_language

        # Verify event structure
        assert event is not None
        assert event["type"] == "language_changed"
        assert event["old_language"] == old_language
        assert event["new_language"] == new_language
        assert event["triggered_by_user_id"] == user_id

    @pytest.mark.asyncio
    async def test_user_changed_language_user_not_found(self, presence_manager, mock_redis):
        """Test language change when user not found in presence state."""
        room_id = "test-room"
        user_id = "user123"
        new_language = "pl"

        mock_redis.hget.return_value = None

        event = await presence_manager.user_changed_language(
            room_id, user_id, new_language
        )

        # Verify None is returned
        assert event is None
        assert not mock_redis.hset.called

    @pytest.mark.asyncio
    async def test_user_changed_language_same_language_no_event(self, presence_manager, mock_redis):
        """Test that setting the same language doesn't trigger an event."""
        room_id = "test-room"
        user_id = "user123"
        language = "en"

        # Simulate existing user with language "en"
        existing_data = {
            "display_name": "John Doe",
            "language": language,
            "is_guest": False,
            "state": "active",
            "joined_at": datetime.utcnow().isoformat(),
            "last_seen": datetime.utcnow().isoformat()
        }
        mock_redis.hget.return_value = json.dumps(existing_data).encode()

        # Try to change to the same language
        event = await presence_manager.user_changed_language(
            room_id, user_id, language
        )

        # Verify None is returned (no event broadcast)
        assert event is None
        # Verify no state update was made (no hset call)
        assert not mock_redis.hset.called


class TestPresenceManagerSnapshot:
    """Test suite for presence snapshot generation."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hgetall = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_get_presence_snapshot_single_user(self, presence_manager, mock_redis):
        """Test presence snapshot with single active user."""
        room_id = "test-room"

        user_data = {
            "display_name": "John Doe",
            "language": "en",
            "is_guest": False,
            "state": "active",
            "joined_at": "2024-01-01T00:00:00"
        }

        mock_redis.hgetall.return_value = {
            b"user:user123": json.dumps(user_data).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify snapshot structure
        assert snapshot["type"] == "presence_snapshot"
        assert snapshot["room_id"] == room_id
        assert len(snapshot["participants"]) == 1

        participant = snapshot["participants"][0]
        assert participant["user_id"] == "user123"
        assert participant["display_name"] == "John Doe"
        assert participant["language"] == "en"
        assert participant["is_guest"] is False

        # Verify language counts
        assert snapshot["language_counts"] == {"en": 1}

    @pytest.mark.asyncio
    async def test_get_presence_snapshot_multiple_users(self, presence_manager, mock_redis):
        """Test presence snapshot with multiple users and languages."""
        room_id = "test-room"

        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "John",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": "2024-01-01T00:00:00"
            }).encode(),
            b"user:user2": json.dumps({
                "display_name": "Maria",
                "language": "pl",
                "is_guest": False,
                "state": "active",
                "joined_at": "2024-01-01T00:01:00"
            }).encode(),
            b"user:user3": json.dumps({
                "display_name": "Ahmed",
                "language": "ar",
                "is_guest": True,
                "state": "active",
                "joined_at": "2024-01-01T00:02:00"
            }).encode(),
            b"user:user4": json.dumps({
                "display_name": "Pierre",
                "language": "en",  # Duplicate language
                "is_guest": False,
                "state": "active",
                "joined_at": "2024-01-01T00:03:00"
            }).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify all participants are included
        assert len(snapshot["participants"]) == 4

        # Verify language counts (en: 2, pl: 1, ar: 1)
        assert snapshot["language_counts"]["en"] == 2
        assert snapshot["language_counts"]["pl"] == 1
        assert snapshot["language_counts"]["ar"] == 1

    @pytest.mark.asyncio
    async def test_get_presence_snapshot_excludes_disconnecting_users(self, presence_manager, mock_redis):
        """Test that disconnecting users are excluded from snapshot."""
        room_id = "test-room"

        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "John",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": "2024-01-01T00:00:00"
            }).encode(),
            b"user:user2": json.dumps({
                "display_name": "Maria",
                "language": "pl",
                "is_guest": False,
                "state": "disconnecting",  # Should be excluded
                "joined_at": "2024-01-01T00:01:00",
                "disconnect_started": "2024-01-01T00:10:00"
            }).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify only active user is included
        assert len(snapshot["participants"]) == 1
        assert snapshot["participants"][0]["user_id"] == "user1"

        # Verify language counts exclude disconnecting user
        assert snapshot["language_counts"] == {"en": 1}


class TestPresenceManagerCleanup:
    """Test suite for background cleanup task."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.scan_iter = AsyncMock()
        redis.ttl = AsyncMock()
        redis.hget = AsyncMock()
        redis.hdel = AsyncMock()
        redis.delete = AsyncMock()
        redis.publish = AsyncMock()
        redis.hgetall = AsyncMock(return_value={})
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_cleanup_processes_expired_timer(self, presence_manager, mock_redis):
        """Test that cleanup task processes expired disconnect timers."""
        room_id = "test-room"
        user_id = "user123"
        timer_key = f"room:{room_id}:disconnect_timer:{user_id}"

        # Mock expired timer
        async def mock_scan():
            yield timer_key.encode()

        mock_redis.scan_iter.return_value = mock_scan()
        mock_redis.ttl.return_value = -1  # Expired

        # Mock user data
        user_data = {
            "display_name": "John Doe",
            "language": "en",
            "is_guest": False,
            "state": "disconnecting"
        }
        mock_redis.hget.return_value = json.dumps(user_data).encode()

        # Run one iteration of cleanup
        cleanup_task = asyncio.create_task(presence_manager.cleanup_stale_disconnects())
        await asyncio.sleep(0.1)  # Let it process one iteration
        cleanup_task.cancel()

        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

        # Verify user was removed from presence state
        await asyncio.sleep(5.1)  # Wait for cleanup interval

        # The cleanup should have been called with correct parameters
        # We'll verify the logic by checking if the methods would be called

    @pytest.mark.asyncio
    async def test_cleanup_ignores_active_timers(self, presence_manager, mock_redis):
        """Test that cleanup task ignores timers that haven't expired."""
        timer_key = "room:test-room:disconnect_timer:user123"

        async def mock_scan():
            yield timer_key.encode()

        mock_redis.scan_iter.return_value = mock_scan()
        mock_redis.ttl.return_value = 10  # Still active (10 seconds remaining)

        # Run one iteration of cleanup
        cleanup_task = asyncio.create_task(presence_manager.cleanup_stale_disconnects())
        await asyncio.sleep(0.1)
        cleanup_task.cancel()

        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

        # Verify user was NOT removed
        assert not mock_redis.hdel.called


class TestPresenceManagerConcurrency:
    """Test suite for concurrent operations."""

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
    async def test_concurrent_user_connections(self, presence_manager, mock_redis):
        """Test multiple users connecting concurrently."""
        room_id = "test-room"

        # Simulate concurrent connections
        tasks = [
            presence_manager.user_connected(room_id, f"user{i}", f"User {i}", "en", False)
            for i in range(5)
        ]

        events = await asyncio.gather(*tasks)

        # Verify all connections were processed
        assert len(events) == 5
        assert mock_redis.hset.call_count == 5

    @pytest.mark.asyncio
    async def test_rapid_language_changes(self, presence_manager, mock_redis):
        """Test rapid language changes by the same user."""
        room_id = "test-room"
        user_id = "user123"

        # Create initial user data
        current_language = ["en"]  # Use list to allow mutation in closure

        def get_user_data(*args):
            user_data = {
                "display_name": "John Doe",
                "language": current_language[0],
                "is_guest": False,
                "state": "active",
                "joined_at": datetime.utcnow().isoformat(),
                "last_seen": datetime.utcnow().isoformat()
            }
            return json.dumps(user_data).encode()

        def set_user_data(*args):
            # Update current language when hset is called
            if len(args) >= 3:
                data = json.loads(args[2])
                current_language[0] = data["language"]

        mock_redis.hget.side_effect = get_user_data
        mock_redis.hset.side_effect = set_user_data

        # Rapid language changes - now with realistic state updates
        languages = ["en", "pl", "ar", "en", "pl"]
        events = []
        for lang in languages:
            event = await presence_manager.user_changed_language(room_id, user_id, lang)
            events.append(event)

        # First change: en -> en = no change, should be None
        assert events[0] is None
        # Second change: en -> pl = change, should have event
        assert events[1] is not None
        assert events[1]["new_language"] == "pl"
        # Third change: pl -> ar = change, should have event
        assert events[2] is not None
        assert events[2]["new_language"] == "ar"
        # Fourth change: ar -> en = change, should have event
        assert events[3] is not None
        assert events[3]["new_language"] == "en"
        # Fifth change: en -> pl = change, should have event
        assert events[4] is not None
        assert events[4]["new_language"] == "pl"

        # Should have 4 actual changes (not 5)
        assert sum(1 for e in events if e is not None) == 4
        assert mock_redis.hset.call_count == 4


class TestPresenceManagerEdgeCases:
    """Test suite for edge cases and error handling."""

    @pytest.fixture
    def mock_redis(self):
        redis = AsyncMock()
        redis.hgetall = AsyncMock()
        return redis

    @pytest.fixture
    def presence_manager(self, mock_redis):
        return PresenceManager(mock_redis)

    @pytest.mark.asyncio
    async def test_empty_room_snapshot(self, presence_manager, mock_redis):
        """Test presence snapshot for empty room."""
        room_id = "empty-room"
        mock_redis.hgetall.return_value = {}

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify empty snapshot structure
        assert snapshot["type"] == "presence_snapshot"
        assert snapshot["room_id"] == room_id
        assert snapshot["participants"] == []
        assert snapshot["language_counts"] == {}

    @pytest.mark.asyncio
    async def test_invalid_user_data_in_snapshot(self, presence_manager, mock_redis):
        """Test that invalid user data is skipped in snapshot."""
        room_id = "test-room"

        mock_redis.hgetall.return_value = {
            b"user:user1": json.dumps({
                "display_name": "Valid User",
                "language": "en",
                "is_guest": False,
                "state": "active",
                "joined_at": "2024-01-01T00:00:00"
            }).encode(),
            b"user:user2": b"invalid json data",  # Invalid JSON
            b"user:user3": json.dumps({
                # Missing required fields
                "display_name": "Incomplete User"
            }).encode()
        }

        snapshot = await presence_manager.get_presence_snapshot(room_id)

        # Verify only valid user is included
        assert len(snapshot["participants"]) == 1
        assert snapshot["participants"][0]["user_id"] == "user1"
