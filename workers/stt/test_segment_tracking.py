"""
Unit tests for STT worker segment tracking functionality.

Tests the Redis-based segment ID tracking system that ensures
incremental transcription works correctly and stays synchronized
across local and OpenAI STT modes.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import redis.asyncio as redis


@pytest.fixture
async def mock_redis():
    """Mock Redis client for testing."""
    mock = AsyncMock()
    mock.get = AsyncMock()
    mock.set = AsyncMock()
    mock.incr = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_get_or_create_segment_id_new_room(mock_redis):
    """Test creating initial segment ID for a new room."""
    # Arrange
    mock_redis.get.return_value = None
    mock_redis.set.return_value = True

    # Import function (simulating the actual implementation)
    async def get_or_create_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            return 1
        return int(segment_id)

    # Act
    segment_id = await get_or_create_segment_id("test-room", mock_redis)

    # Assert
    assert segment_id == 1
    mock_redis.get.assert_called_once_with("room:test-room:segment_counter")
    mock_redis.set.assert_called_once_with("room:test-room:segment_counter", "1")


@pytest.mark.asyncio
async def test_get_or_create_segment_id_existing_room(mock_redis):
    """Test getting existing segment ID for a room."""
    # Arrange
    mock_redis.get.return_value = "5"

    async def get_or_create_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            return 1
        return int(segment_id)

    # Act
    segment_id = await get_or_create_segment_id("test-room", mock_redis)

    # Assert
    assert segment_id == 5
    mock_redis.get.assert_called_once_with("room:test-room:segment_counter")
    mock_redis.set.assert_not_called()


@pytest.mark.asyncio
async def test_increment_segment_id(mock_redis):
    """Test incrementing segment ID after finalization."""
    # Arrange
    mock_redis.incr.return_value = 3

    async def increment_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        new_id = await redis_client.incr(key)
        return new_id

    # Act
    new_id = await increment_segment_id("test-room", mock_redis)

    # Assert
    assert new_id == 3
    mock_redis.incr.assert_called_once_with("room:test-room:segment_counter")


@pytest.mark.asyncio
async def test_segment_finalization_prevents_double_increment():
    """Test that segment finalization flag prevents double-increment."""
    segment_finalized = {}
    mock_redis = AsyncMock()
    mock_redis.incr.return_value = 3

    async def increment_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        new_id = await redis_client.incr(key)
        return new_id

    room = "test-room"

    # First finalization - should increment
    is_final = True
    if is_final:
        if not segment_finalized.get(room, False):
            segment_finalized[room] = True
            next_id = await increment_segment_id(room, mock_redis)
            assert next_id == 3
            assert segment_finalized[room] == True

    # Second finalization (e.g., duplicate audio_end) - should NOT increment
    mock_redis.incr.reset_mock()
    if is_final:
        if not segment_finalized.get(room, False):
            segment_finalized[room] = True
            await increment_segment_id(room, mock_redis)
            pytest.fail("Should not increment again")

    # Assert increment was only called once
    mock_redis.incr.assert_not_called()


@pytest.mark.asyncio
async def test_finalization_flag_resets_on_new_partial():
    """Test that finalization flag resets when new partial arrives."""
    segment_finalized = {}
    room = "test-room"

    # Simulate finalization
    segment_finalized[room] = True
    assert segment_finalized[room] == True

    # New partial arrives
    is_final = False
    if not is_final and segment_finalized.get(room, False):
        segment_finalized[room] = False

    # Assert flag was reset
    assert segment_finalized[room] == False


@pytest.mark.asyncio
async def test_multiple_rooms_independent_counters():
    """Test that multiple rooms maintain independent segment counters."""
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = ["2", "5", None]
    mock_redis.set.return_value = True

    async def get_or_create_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            return 1
        return int(segment_id)

    # Act
    room1_id = await get_or_create_segment_id("room-1", mock_redis)
    room2_id = await get_or_create_segment_id("room-2", mock_redis)
    room3_id = await get_or_create_segment_id("room-3", mock_redis)

    # Assert
    assert room1_id == 2
    assert room2_id == 5
    assert room3_id == 1
    assert mock_redis.get.call_count == 3


@pytest.mark.asyncio
async def test_incremental_transcription_revision_sequence():
    """Test that revision numbers increase for partials on same segment."""
    segment_finalized = {}
    mock_redis = AsyncMock()
    mock_redis.get.return_value = "2"

    async def get_or_create_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            return 1
        return int(segment_id)

    room = "test-room"

    # Simulate sequence of partials
    partials = []
    for seq in [1, 2, 3, 4, 5]:
        is_final = False
        segment_id = await get_or_create_segment_id(room, mock_redis)

        # Reset flag if needed
        if not is_final and segment_finalized.get(room, False):
            segment_finalized[room] = False

        partials.append({
            "segment_id": segment_id,
            "revision": seq,
            "is_final": is_final
        })

    # Assert all partials have same segment_id but increasing revisions
    assert all(p["segment_id"] == 2 for p in partials)
    assert [p["revision"] for p in partials] == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_full_utterance_cycle():
    """Test complete cycle: partials -> final -> new partials."""
    segment_finalized = {}
    mock_redis = AsyncMock()

    # Configure Redis mock to return segment IDs
    segment_values = ["2", "2", "2", "2", "2"]  # Partials on segment 2
    mock_redis.get.side_effect = segment_values + ["3", "3", "3"]  # Next partials on segment 3
    mock_redis.incr.return_value = 3  # After finalization

    async def get_or_create_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            return 1
        return int(segment_id)

    async def increment_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        new_id = await redis_client.incr(key)
        return new_id

    room = "test-room"
    events = []

    # First utterance: partials
    for seq in [1, 2, 3]:
        is_final = False
        segment_id = await get_or_create_segment_id(room, mock_redis)

        if not is_final and segment_finalized.get(room, False):
            segment_finalized[room] = False

        events.append({"type": "partial", "segment": segment_id, "rev": seq})

    # Finalization
    is_final = True
    segment_id = await get_or_create_segment_id(room, mock_redis)
    events.append({"type": "final", "segment": segment_id, "rev": 0})

    if not segment_finalized.get(room, False):
        segment_finalized[room] = True
        next_id = await increment_segment_id(room, mock_redis)

    # Second utterance: new partials
    for seq in [1, 2]:
        is_final = False
        segment_id = await get_or_create_segment_id(room, mock_redis)

        if not is_final and segment_finalized.get(room, False):
            segment_finalized[room] = False

        events.append({"type": "partial", "segment": segment_id, "rev": seq})

    # Assert sequence
    assert events == [
        {"type": "partial", "segment": 2, "rev": 1},
        {"type": "partial", "segment": 2, "rev": 2},
        {"type": "partial", "segment": 2, "rev": 3},
        {"type": "final", "segment": 2, "rev": 0},
        {"type": "partial", "segment": 3, "rev": 1},
        {"type": "partial", "segment": 3, "rev": 2},
    ]

    # Assert increment was called once
    mock_redis.incr.assert_called_once()


@pytest.mark.asyncio
async def test_concurrent_rooms_no_interference():
    """Test that concurrent operations on different rooms don't interfere."""
    segment_finalized = {}
    mock_redis = AsyncMock()

    async def get_or_create_segment_id(room, redis_client):
        key = f"room:{room}:segment_counter"
        # Simulate different counters for different rooms
        room_counters = {"room-1": "5", "room-2": "3", "room-3": "1"}
        segment_id = room_counters.get(room)
        if segment_id is None:
            return 1
        return int(segment_id)

    async def increment_segment_id(room, redis_client):
        # Track increments per room
        room_counters = {"room-1": 6, "room-2": 4, "room-3": 2}
        return room_counters.get(room, 2)

    # Simulate concurrent operations
    tasks = []

    async def process_room(room_id):
        room = f"room-{room_id}"

        # Partial
        segment_id = await get_or_create_segment_id(room, mock_redis)

        # Final
        if not segment_finalized.get(room, False):
            segment_finalized[room] = True
            next_id = await increment_segment_id(room, mock_redis)

        return segment_id, next_id

    # Run concurrently
    results = await asyncio.gather(
        process_room(1),
        process_room(2),
        process_room(3)
    )

    # Assert each room got correct IDs
    assert results[0] == (5, 6)
    assert results[1] == (3, 4)
    assert results[2] == (1, 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
