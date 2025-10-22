"""
Integration tests for segment consistency across STT mode switching.

Tests the critical functionality where users switch between local and OpenAI
STT modes and verify that segment IDs remain synchronized and don't overlap.
"""

import pytest
import pytest_asyncio
import asyncio
import redis.asyncio as redis
import os
from datetime import datetime
import json


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/5")
STT_EVENTS_CHANNEL = "stt_events"


@pytest_asyncio.fixture
async def redis_client():
    """Real Redis client for integration testing."""
    client = redis.from_url(REDIS_URL, decode_responses=True)
    yield client
    await client.close()


@pytest_asyncio.fixture
async def redis_pubsub(redis_client):
    """Redis pubsub for listening to STT events."""
    pubsub = redis_client.pubsub()
    yield pubsub
    await pubsub.close()


@pytest_asyncio.fixture
async def clean_room(redis_client):
    """Provide a clean test room and clean up after."""
    room_code = f"test-cross-mode-{datetime.now().timestamp()}"

    # Clean up before
    await redis_client.delete(f"room:{room_code}:segment_counter")

    yield room_code

    # Clean up after
    await redis_client.delete(f"room:{room_code}:segment_counter")


class STTModeSimulator:
    """Simulates STT mode behavior (local or OpenAI)."""

    def __init__(self, redis_client, room_code, mode_name):
        self.redis = redis_client
        self.room = room_code
        self.mode = mode_name
        self.segment_finalized = {}

    async def get_current_segment_id(self):
        """Get current segment ID from Redis."""
        key = f"room:{self.room}:segment_counter"
        segment_id = await self.redis.get(key)
        if segment_id is None:
            await self.redis.set(key, "1")
            return 1
        return int(segment_id)

    async def increment_segment_id(self):
        """Increment segment ID after finalization."""
        key = f"room:{self.room}:segment_counter"
        new_id = await self.redis.incr(key)
        return new_id

    async def publish_partial(self, text, revision, segment_id=None):
        """Publish a partial transcription event."""
        if segment_id is None:
            segment_id = await self.get_current_segment_id()

        event = {
            "type": "stt_partial",
            "room_id": self.room,
            "segment_id": str(segment_id),
            "revision": revision,
            "text": text,
            "speaker": "test_user",
            "target_lang": "en",
            "final": False,
            "mode": self.mode
        }

        await self.redis.publish(STT_EVENTS_CHANNEL, json.dumps(event))
        return segment_id, revision

    async def publish_final(self, text, segment_id=None):
        """Publish a final transcription event and increment counter."""
        if segment_id is None:
            segment_id = await self.get_current_segment_id()

        event = {
            "type": "stt_final",
            "room_id": self.room,
            "segment_id": str(segment_id),
            "revision": 0,
            "text": text,
            "speaker": "test_user",
            "target_lang": "en",
            "final": True,
            "mode": self.mode
        }

        await self.redis.publish(STT_EVENTS_CHANNEL, json.dumps(event))

        # Increment segment counter (with finalization tracking)
        if not self.segment_finalized.get(self.room, False):
            self.segment_finalized[self.room] = True
            next_id = await self.increment_segment_id()
            return segment_id, next_id
        else:
            return segment_id, None

    def reset_finalization_flag(self):
        """Reset finalization flag for new utterance."""
        self.segment_finalized[self.room] = False


@pytest.mark.asyncio
async def test_local_to_openai_mode_switch(redis_client, clean_room):
    """Test switching from local to OpenAI mode preserves segment counter."""
    room = clean_room

    # Create mode simulators
    local_mode = STTModeSimulator(redis_client, room, "local")
    openai_mode = STTModeSimulator(redis_client, room, "openai")

    events = []

    # === Local mode: Utterance 1 ===
    seg_id = await local_mode.get_current_segment_id()
    events.append(("local", seg_id, 1, "partial"))
    await local_mode.publish_partial("Hello", 1, seg_id)

    seg_id, _ = await local_mode.publish_partial("Hello world", 2, seg_id)
    events.append(("local", seg_id, 2, "partial"))

    seg_id, next_id = await local_mode.publish_final("Hello world", seg_id)
    events.append(("local", seg_id, 0, "final"))
    local_mode.reset_finalization_flag()

    # === Switch to OpenAI mode ===

    # === OpenAI mode: Utterance 2 ===
    seg_id = await openai_mode.get_current_segment_id()
    events.append(("openai", seg_id, 1, "partial"))
    assert seg_id == 2, "OpenAI should start at segment 2"

    await openai_mode.publish_partial("How are", 1, seg_id)
    seg_id, _ = await openai_mode.publish_partial("How are you", 2, seg_id)
    events.append(("openai", seg_id, 2, "partial"))

    seg_id, next_id = await openai_mode.publish_final("How are you", seg_id)
    events.append(("openai", seg_id, 0, "final"))
    openai_mode.reset_finalization_flag()

    # Verify segment sequence
    assert events == [
        ("local", 1, 1, "partial"),
        ("local", 1, 2, "partial"),
        ("local", 1, 0, "final"),
        ("openai", 2, 1, "partial"),
        ("openai", 2, 2, "partial"),
        ("openai", 2, 0, "final"),
    ]

    # Final counter should be 3
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "3"


@pytest.mark.asyncio
async def test_openai_to_local_mode_switch(redis_client, clean_room):
    """Test switching from OpenAI to local mode preserves segment counter."""
    room = clean_room

    local_mode = STTModeSimulator(redis_client, room, "local")
    openai_mode = STTModeSimulator(redis_client, room, "openai")

    events = []

    # === OpenAI mode: Utterance 1 ===
    seg_id = await openai_mode.get_current_segment_id()
    await openai_mode.publish_partial("Testing", 1, seg_id)
    events.append(("openai", seg_id, 1))

    seg_id, next_id = await openai_mode.publish_final("Testing", seg_id)
    events.append(("openai", seg_id, 0))
    openai_mode.reset_finalization_flag()

    # === Switch to Local mode ===

    # === Local mode: Utterance 2 ===
    seg_id = await local_mode.get_current_segment_id()
    assert seg_id == 2, "Local should start at segment 2"

    await local_mode.publish_partial("One two", 1, seg_id)
    events.append(("local", seg_id, 1))

    seg_id, next_id = await local_mode.publish_final("One two three", seg_id)
    events.append(("local", seg_id, 0))

    # Verify
    assert events == [
        ("openai", 1, 1),
        ("openai", 1, 0),
        ("local", 2, 1),
        ("local", 2, 0),
    ]

    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "3"


@pytest.mark.asyncio
async def test_rapid_mode_switching(redis_client, clean_room):
    """Test rapid switching between modes maintains consistency."""
    room = clean_room

    local_mode = STTModeSimulator(redis_client, room, "local")
    openai_mode = STTModeSimulator(redis_client, room, "openai")

    segment_ids = []

    # Local -> OpenAI -> Local -> OpenAI
    for i in range(8):
        mode = local_mode if i % 2 == 0 else openai_mode
        mode.reset_finalization_flag()

        seg_id = await mode.get_current_segment_id()
        await mode.publish_partial(f"Text {i}", 1, seg_id)
        seg_id, next_id = await mode.publish_final(f"Text {i}", seg_id)

        segment_ids.append(seg_id)

    # Should have sequential segment IDs
    assert segment_ids == [1, 2, 3, 4, 5, 6, 7, 8]

    # Final counter should be 9
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "9"


@pytest.mark.asyncio
async def test_simultaneous_mode_switch_during_utterance(redis_client, clean_room):
    """Test mode switch happening mid-utterance (edge case)."""
    room = clean_room

    local_mode = STTModeSimulator(redis_client, room, "local")
    openai_mode = STTModeSimulator(redis_client, room, "openai")

    # Start utterance in local mode
    seg_id = await local_mode.get_current_segment_id()
    await local_mode.publish_partial("Hello", 1, seg_id)
    await local_mode.publish_partial("Hello world", 2, seg_id)

    # User switches to OpenAI mid-utterance
    # The current segment should complete in local mode
    seg_id, next_id = await local_mode.publish_final("Hello world", seg_id)
    assert seg_id == 1
    assert next_id == 2

    local_mode.reset_finalization_flag()

    # New utterance starts in OpenAI mode
    seg_id = await openai_mode.get_current_segment_id()
    assert seg_id == 2, "New mode should use next segment ID"

    await openai_mode.publish_partial("Testing", 1, seg_id)
    seg_id, next_id = await openai_mode.publish_final("Testing", seg_id)

    # Final counter should be 3
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "3"


@pytest.mark.asyncio
async def test_both_modes_partial_and_final_providers(redis_client, clean_room):
    """Test scenario where partial uses local and final uses OpenAI."""
    room = clean_room

    # This simulates: partial_mode=local, final_mode=openai
    local_mode = STTModeSimulator(redis_client, room, "local")
    openai_mode = STTModeSimulator(redis_client, room, "openai")

    # Start segment
    seg_id = await local_mode.get_current_segment_id()
    assert seg_id == 1

    # Local publishes partials
    await local_mode.publish_partial("Hello", 1, seg_id)
    await local_mode.publish_partial("Hello there", 2, seg_id)

    # OpenAI publishes final (using same segment)
    # Note: Both should share the segment counter
    current_seg = await openai_mode.get_current_segment_id()
    assert current_seg == 1, "Both modes share same segment counter"

    seg_id, next_id = await openai_mode.publish_final("Hello there friend", current_seg)
    assert seg_id == 1
    assert next_id == 2

    openai_mode.reset_finalization_flag()

    # Next utterance
    seg_id = await local_mode.get_current_segment_id()
    assert seg_id == 2

    await local_mode.publish_partial("How are you", 1, seg_id)

    current_seg = await openai_mode.get_current_segment_id()
    assert current_seg == 2

    seg_id, next_id = await openai_mode.publish_final("How are you today", current_seg)

    # Final counter should be 3
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "3"


@pytest.mark.asyncio
async def test_counter_survives_worker_restart(redis_client, clean_room):
    """Test that segment counter persists if worker restarts."""
    room = clean_room

    # First "worker instance"
    local_mode_1 = STTModeSimulator(redis_client, room, "local")

    seg_id = await local_mode_1.get_current_segment_id()
    await local_mode_1.publish_partial("Before restart", 1, seg_id)
    seg_id, next_id = await local_mode_1.publish_final("Before restart", seg_id)

    assert next_id == 2

    # Simulate worker restart - create new simulator (new instance)
    local_mode_2 = STTModeSimulator(redis_client, room, "local")

    # Should continue from where it left off
    seg_id = await local_mode_2.get_current_segment_id()
    assert seg_id == 2, "Counter should persist after restart"

    await local_mode_2.publish_partial("After restart", 1, seg_id)
    seg_id, next_id = await local_mode_2.publish_final("After restart", seg_id)

    assert next_id == 3

    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "3"


@pytest.mark.asyncio
async def test_multiple_audio_end_messages_cross_mode(redis_client, clean_room):
    """Test that multiple audio_end from different sources don't double-increment."""
    room = clean_room

    local_mode = STTModeSimulator(redis_client, room, "local")

    # Start utterance
    seg_id = await local_mode.get_current_segment_id()
    await local_mode.publish_partial("Test", 1, seg_id)

    # First final (e.g., from web device)
    seg_id_1, next_id_1 = await local_mode.publish_final("Test", seg_id)
    assert next_id_1 == 2

    # Second final (e.g., from mobile device, duplicate audio_end)
    seg_id_2, next_id_2 = await local_mode.publish_final("Test", seg_id)
    assert next_id_2 is None, "Should not increment again"

    # Counter should only be 2
    final_counter = await redis_client.get(f"room:{room}:segment_counter")
    assert final_counter == "2"


@pytest.mark.asyncio
async def test_segment_alignment_with_persistence(redis_client, clean_room):
    """Test that segment IDs align correctly with what persistence expects."""
    room = clean_room

    local_mode = STTModeSimulator(redis_client, room, "local")

    persistence_received = []

    # Simulate what persistence service would see
    async def simulate_persistence_listener():
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(STT_EVENTS_CHANNEL)

        timeout = asyncio.create_task(asyncio.sleep(2))
        listen = asyncio.create_task(pubsub.get_message(timeout=2))

        while not timeout.done():
            try:
                msg = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=0.5)
                if msg and msg["type"] == "message":
                    data = json.loads(msg["data"])
                    if data.get("room_id") == room:
                        persistence_received.append({
                            "segment_id": int(data["segment_id"]),
                            "revision": data["revision"],
                            "final": data["final"]
                        })
            except asyncio.TimeoutError:
                break

        await pubsub.close()

    # Start listener
    listener_task = asyncio.create_task(simulate_persistence_listener())

    # Give listener time to subscribe
    await asyncio.sleep(0.1)

    # Generate events
    seg_id = await local_mode.get_current_segment_id()
    await local_mode.publish_partial("Test one", 1, seg_id)
    await local_mode.publish_partial("Test one two", 2, seg_id)
    await local_mode.publish_final("Test one two three", seg_id)

    # Wait for events to be processed
    await asyncio.sleep(0.5)

    # Stop listener
    await listener_task

    # Verify persistence received correct sequence
    expected = [
        {"segment_id": 1, "revision": 1, "final": False},
        {"segment_id": 1, "revision": 2, "final": False},
        {"segment_id": 1, "revision": 0, "final": True},
    ]

    assert len(persistence_received) == len(expected)
    for received, expected_event in zip(persistence_received, expected):
        assert received["segment_id"] == expected_event["segment_id"]
        assert received["revision"] == expected_event["revision"]
        assert received["final"] == expected_event["final"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
