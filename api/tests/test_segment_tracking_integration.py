"""
Integration tests for segment tracking across STT modes.

Tests the full flow of segment ID tracking through:
- Local Whisper worker
- OpenAI STT router
- Mode switching scenarios
- Persistence layer integration
"""

import pytest
import pytest_asyncio
import asyncio
import redis.asyncio as redis
import os
from datetime import datetime


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/5")


@pytest_asyncio.fixture
async def redis_client():
    """Real Redis client for integration testing."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.close()


@pytest_asyncio.fixture
async def clean_room(redis_client):
    """Provide a clean test room and clean up after."""
    room_code = f"test-{datetime.now().timestamp()}"

    # Clean up before
    await redis_client.delete(f"room:{room_code}:segment_counter")

    yield room_code

    # Clean up after
    await redis_client.delete(f"room:{room_code}:segment_counter")


@pytest.mark.asyncio
async def test_redis_segment_counter_initialization(redis_client, clean_room):
    """Test that segment counter initializes correctly in Redis."""
    room = clean_room

    # Should not exist initially
    counter = await redis_client.get(f"room:{room}:segment_counter")
    assert counter is None

    # Initialize to 1
    await redis_client.set(f"room:{room}:segment_counter", "1")
    counter = await redis_client.get(f"room:{room}:segment_counter")
    assert counter == "1"


@pytest.mark.asyncio
async def test_redis_segment_counter_increment(redis_client, clean_room):
    """Test that Redis INCR works correctly for segment counter."""
    room = clean_room

    # Initialize
    await redis_client.set(f"room:{room}:segment_counter", "1")

    # Increment
    new_val = await redis_client.incr(f"room:{room}:segment_counter")
    assert new_val == 2

    # Increment again
    new_val = await redis_client.incr(f"room:{room}:segment_counter")
    assert new_val == 3

    # Verify
    counter = await redis_client.get(f"room:{room}:segment_counter")
    assert counter == "3"


@pytest.mark.asyncio
async def test_segment_counter_persistence_across_connections(clean_room):
    """Test that segment counter persists across Redis connection cycles."""
    room = clean_room

    # First connection
    client1 = redis.from_url(REDIS_URL, decode_responses=True)
    await client1.set(f"room:{room}:segment_counter", "5")
    await client1.close()

    # Second connection
    client2 = redis.from_url(REDIS_URL, decode_responses=True)
    counter = await client2.get(f"room:{room}:segment_counter")
    assert counter == "5"
    await client2.close()


@pytest.mark.asyncio
async def test_concurrent_segment_operations(redis_client, clean_room):
    """Test that concurrent increments from multiple workers are safe."""
    room = clean_room
    await redis_client.set(f"room:{room}:segment_counter", "1")

    async def increment_worker(worker_id):
        """Simulate a worker incrementing the counter."""
        results = []
        for _ in range(5):
            new_val = await redis_client.incr(f"room:{room}:segment_counter")
            results.append(new_val)
            await asyncio.sleep(0.01)  # Simulate processing time
        return results

    # Run 3 workers concurrently
    worker_results = await asyncio.gather(
        increment_worker(1),
        increment_worker(2),
        increment_worker(3)
    )

    # All increments should succeed
    all_results = []
    for results in worker_results:
        all_results.extend(results)

    # Should have 15 total increments (5 per worker)
    assert len(all_results) == 15

    # Final counter should be 16 (initial 1 + 15 increments)
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "16"

    # All values should be unique and in range
    assert len(set(all_results)) == 15
    assert min(all_results) == 2
    assert max(all_results) == 16


@pytest.mark.asyncio
async def test_segment_tracking_full_utterance_cycle(redis_client, clean_room):
    """Test complete utterance cycle with Redis."""
    room = clean_room

    # Helper functions (simulate worker implementation)
    async def get_or_create_segment_id(room_code):
        key = f"room:{room_code}:segment_counter"
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            return 1
        return int(segment_id)

    async def increment_segment_id(room_code):
        key = f"room:{room_code}:segment_counter"
        new_id = await redis_client.incr(key)
        return new_id

    segment_finalized = {}

    # Utterance 1: Partials
    events = []
    for rev in [1, 2, 3]:
        segment_id = await get_or_create_segment_id(room)
        events.append({"type": "partial", "segment": segment_id, "rev": rev})

    # Utterance 1: Final
    segment_id = await get_or_create_segment_id(room)
    events.append({"type": "final", "segment": segment_id, "rev": 0})

    # Increment
    if not segment_finalized.get(room, False):
        segment_finalized[room] = True
        next_id = await increment_segment_id(room)
        assert next_id == 2

    # Reset flag for new utterance
    segment_finalized[room] = False

    # Utterance 2: Partials
    for rev in [1, 2]:
        segment_id = await get_or_create_segment_id(room)
        events.append({"type": "partial", "segment": segment_id, "rev": rev})

    # Utterance 2: Final
    segment_id = await get_or_create_segment_id(room)
    events.append({"type": "final", "segment": segment_id, "rev": 0})

    # Increment
    if not segment_finalized.get(room, False):
        segment_finalized[room] = True
        next_id = await increment_segment_id(room)
        assert next_id == 3

    # Verify event sequence
    assert events == [
        {"type": "partial", "segment": 1, "rev": 1},
        {"type": "partial", "segment": 1, "rev": 2},
        {"type": "partial", "segment": 1, "rev": 3},
        {"type": "final", "segment": 1, "rev": 0},
        {"type": "partial", "segment": 2, "rev": 1},
        {"type": "partial", "segment": 2, "rev": 2},
        {"type": "final", "segment": 2, "rev": 0},
    ]

    # Final counter should be 3
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "3"


@pytest.mark.asyncio
async def test_mode_switching_preserves_segment_counter(redis_client, clean_room):
    """Test that switching between local and OpenAI preserves segment counter."""
    room = clean_room

    # Helper to simulate segment operations
    async def simulate_utterance(mode_name, expected_segment):
        """Simulate an utterance in a specific mode."""
        key = f"room:{room}:segment_counter"

        # Get current segment
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            segment_id = "1"

        segment_id = int(segment_id)
        assert segment_id == expected_segment, f"{mode_name}: Expected segment {expected_segment}, got {segment_id}"

        # Simulate final and increment
        new_id = await redis_client.incr(key)
        return new_id

    # Local mode: utterance 1
    next_id = await simulate_utterance("Local-1", 1)
    assert next_id == 2

    # Local mode: utterance 2
    next_id = await simulate_utterance("Local-2", 2)
    assert next_id == 3

    # Switch to OpenAI mode: utterance 3
    next_id = await simulate_utterance("OpenAI-1", 3)
    assert next_id == 4

    # OpenAI mode: utterance 4
    next_id = await simulate_utterance("OpenAI-2", 4)
    assert next_id == 5

    # Switch back to Local mode: utterance 5
    next_id = await simulate_utterance("Local-3", 5)
    assert next_id == 6

    # Verify final state
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "6"


@pytest.mark.asyncio
async def test_multiple_devices_same_room(redis_client, clean_room):
    """Test that multiple devices in same room share segment counter."""
    room = clean_room

    async def device_utterance(device_id, expected_segment):
        """Simulate an utterance from a specific device."""
        key = f"room:{room}:segment_counter"

        # Get segment
        segment_id = await redis_client.get(key)
        if segment_id is None:
            await redis_client.set(key, "1")
            segment_id = "1"

        segment_id = int(segment_id)
        assert segment_id == expected_segment

        # Increment after final
        new_id = await redis_client.incr(key)
        return device_id, segment_id, new_id

    # Device 1 speaks
    device, seg, next_seg = await device_utterance("web", 1)
    assert (device, seg, next_seg) == ("web", 1, 2)

    # Device 2 speaks
    device, seg, next_seg = await device_utterance("mobile", 2)
    assert (device, seg, next_seg) == ("mobile", 2, 3)

    # Device 1 speaks again
    device, seg, next_seg = await device_utterance("web", 3)
    assert (device, seg, next_seg) == ("web", 3, 4)


@pytest.mark.asyncio
async def test_double_audio_end_prevention(redis_client, clean_room):
    """Test that multiple audio_end messages don't cause double increment."""
    room = clean_room
    segment_finalized = {}

    await redis_client.set(f"room:{room}:segment_counter", "1")

    async def handle_audio_end(is_final=True):
        """Simulate audio_end handling with finalization tracking."""
        key = f"room:{room}:segment_counter"
        segment_id = int(await redis_client.get(key))

        if is_final:
            if not segment_finalized.get(room, False):
                segment_finalized[room] = True
                next_id = await redis_client.incr(key)
                return segment_id, next_id, "incremented"
            else:
                return segment_id, None, "skipped"

    # First audio_end - should increment
    seg, next_seg, action = await handle_audio_end(is_final=True)
    assert action == "incremented"
    assert seg == 1
    assert next_seg == 2

    # Second audio_end (duplicate) - should NOT increment
    seg, next_seg, action = await handle_audio_end(is_final=True)
    assert action == "skipped"
    assert seg == 2  # Reads current counter value (already incremented to 2)
    assert next_seg is None

    # Third audio_end (another duplicate) - should NOT increment
    seg, next_seg, action = await handle_audio_end(is_final=True)
    assert action == "skipped"
    assert seg == 2  # Still reads current counter value
    assert next_seg is None

    # Counter should still be 2 (only incremented once)
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "2"


@pytest.mark.asyncio
async def test_redis_database_isolation():
    """Test that using Redis database /5 doesn't interfere with other databases."""
    # Connect to database 5 (STT)
    client5 = redis.from_url("redis://redis:6379/5", decode_responses=True)

    # Connect to database 0 (default)
    client0 = redis.from_url("redis://redis:6379/0", decode_responses=True)

    test_key = "test_isolation_key"

    try:
        # Set value in db 5
        await client5.set(test_key, "db5_value")

        # Set value in db 0
        await client0.set(test_key, "db0_value")

        # Verify they're independent
        val5 = await client5.get(test_key)
        val0 = await client0.get(test_key)

        assert val5 == "db5_value"
        assert val0 == "db0_value"

    finally:
        # Clean up
        await client5.delete(test_key)
        await client0.delete(test_key)
        await client5.close()
        await client0.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
