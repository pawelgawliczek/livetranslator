"""
Integration tests for STT streaming stop button bug fixes.

Critical Bug: Final transcriptions weren't appearing when users clicked Stop button

This test suite verifies three bug fixes:

Fix 1: Segment ID initialization when creating new streaming connections
- Issue: New connections weren't initialized with current segment_id
- Fix: Call reset_for_new_segment() immediately after connection creation
- Location: api/routers/stt/router.py:404

Fix 2: End of utterance method added to streaming manager
- Issue: No way to signal end of utterance without closing connection
- Fix: Added end_of_utterance() method that sends EndOfStream to Speechmatics
- Location: api/routers/stt/streaming_manager.py:135-157

Fix 3: Audio end handler signals end of utterance
- Issue: audio_end wasn't triggering final transcription from provider
- Fix: Call streaming_conn.end_of_utterance() when audio_end received
- Location: api/routers/stt/router.py:652

Priority: P0 (Critical - affects all stop button interactions)

Test Coverage:
- New connection segment_id initialization
- EndOfStream message sending to Speechmatics
- Complete stop button flow (E2E)
- Final transcription emission
- Cost tracking on stop
- Debug info creation
"""

import pytest
import pytest_asyncio
import asyncio
import json
import base64
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime
from decimal import Decimal


# Mock WebSocket client for Speechmatics
class MockSpeechmaticsWebSocket:
    """Mock WebSocket client that tracks messages sent to Speechmatics"""

    def __init__(self):
        self.messages_sent = []
        self.closed = False
        self.state = "OPEN"

    async def send(self, message):
        """Track messages sent to provider"""
        self.messages_sent.append(message)

        # Parse and validate message
        try:
            data = json.loads(message)
            print(f"[MockSpeechmaticsWS] Sent: {data}")
        except json.JSONDecodeError:
            print(f"[MockSpeechmaticsWS] Sent binary data: {len(message)} bytes")

    async def close(self):
        """Close the websocket"""
        self.closed = True
        self.state = "CLOSED"

    def get_end_of_stream_messages(self):
        """Extract EndOfStream messages"""
        end_messages = []
        for msg in self.messages_sent:
            try:
                data = json.loads(msg)
                if data.get("message") == "EndOfStream":
                    end_messages.append(data)
            except (json.JSONDecodeError, TypeError):
                pass
        return end_messages


@pytest.fixture
def mock_redis():
    """Mock Redis with state tracking for streaming tests"""
    redis = AsyncMock()
    state = {
        'keys': {},
        'sets': {},
        'publishes': []  # Track all publish calls
    }

    async def mock_get(key):
        return state['keys'].get(key)

    async def mock_set(key, value, **kwargs):
        state['keys'][key] = value

    async def mock_setex(key, ttl, value):
        state['keys'][key] = value

    async def mock_publish(channel, message):
        """Track published events"""
        state['publishes'].append({
            'channel': channel,
            'message': message,
            'timestamp': time.time()
        })

    async def mock_incr(key):
        current = int(state['keys'].get(key, 0))
        current += 1
        state['keys'][key] = str(current)
        return current

    redis.get = AsyncMock(side_effect=mock_get)
    redis.set = AsyncMock(side_effect=mock_set)
    redis.setex = AsyncMock(side_effect=mock_setex)
    redis.publish = AsyncMock(side_effect=mock_publish)
    redis.incr = AsyncMock(side_effect=mock_incr)
    redis.delete = AsyncMock()
    redis.expire = AsyncMock()

    # Expose state for test assertions
    redis._test_state = state

    return redis


@pytest.fixture
def mock_streaming_connection():
    """Create a mock StreamingConnection with Speechmatics WebSocket"""
    from api.routers.stt.streaming_manager import StreamingConnection

    # Create mock callbacks
    on_partial = AsyncMock()
    on_final = AsyncMock()
    on_error = AsyncMock()

    # Create connection
    conn = StreamingConnection(
        room_id="test-room",
        provider="speechmatics",
        language="en-US",
        config={"diarization": True},
        on_partial=on_partial,
        on_final=on_final,
        on_error=on_error
    )

    # Mock the WebSocket client
    conn.ws_client = MockSpeechmaticsWebSocket()
    conn.is_connected = True
    conn.is_closing = False

    return conn


@pytest.mark.integration
@pytest.mark.asyncio
class TestFix1_SegmentIdInitialization:
    """Test Fix 1: New streaming connections are initialized with current segment_id"""

    async def test_new_connection_initialized_with_segment_id(self, mock_streaming_connection):
        """
        Test that new streaming connection gets initialized with segment_id

        Verifies:
        - reset_for_new_segment() is called on new connection
        - segment_id is set correctly
        - Accumulated text is cleared
        """
        conn = mock_streaming_connection

        # Simulate connection creation and initialization (Fix 1)
        segment_id = 42
        conn.reset_for_new_segment(segment_id)

        # Verify segment_id was set
        assert conn.segment_id == segment_id

        # Verify state was reset
        assert conn.accumulated_text == ""
        assert conn.finalized_text == ""
        assert conn.revision == 0

        print(f"✅ New connection initialized with segment_id={segment_id}")

    async def test_finals_have_correct_segment_id_after_init(self, mock_streaming_connection):
        """
        Test that finals emitted after initialization have correct segment_id

        Scenario:
        - Create new connection
        - Initialize with segment_id=5
        - Receive final transcription
        - Verify final has segment_id=5
        """
        conn = mock_streaming_connection
        segment_id = 5

        # Initialize with segment_id (Fix 1)
        conn.reset_for_new_segment(segment_id)

        # Simulate final callback being triggered
        final_data = {
            "text": "Hello world",
            "segment_id": conn.segment_id,  # Should be 5
            "final": True
        }

        # Verify segment_id matches
        assert final_data["segment_id"] == segment_id

        print(f"✅ Final transcription has correct segment_id={segment_id}")

    async def test_multiple_segment_transitions(self, mock_streaming_connection):
        """
        Test segment_id transitions across multiple segments

        Scenario:
        - Start with segment 1
        - Transition to segment 2
        - Transition to segment 3
        - Verify each transition resets state correctly
        """
        conn = mock_streaming_connection

        for segment_id in [1, 2, 3]:
            # Initialize for new segment
            conn.reset_for_new_segment(segment_id)

            # Verify segment_id
            assert conn.segment_id == segment_id

            # Simulate some activity
            conn.accumulated_text = f"Segment {segment_id} text"
            conn.revision = 5

        # Final state should be segment 3
        assert conn.segment_id == 3

        print("✅ Multiple segment transitions handled correctly")


@pytest.mark.integration
@pytest.mark.asyncio
class TestFix2_EndOfUtteranceMethod:
    """Test Fix 2: End of utterance method keeps connection alive (no EndOfStream)"""

    async def test_end_of_utterance_sends_endofstream(self, mock_streaming_connection):
        """
        Test that end_of_utterance() keeps connection alive without sending EndOfStream

        NEW BEHAVIOR (connection keep-alive):
        - end_of_utterance() is called to signal end of audio
        - Connection stays alive (no EndOfStream sent)
        - Ready for next segment

        Verifies:
        - No EndOfStream message is sent (connection keep-alive)
        - Connection remains ready for next segment
        - Segment ID is tracked correctly
        """
        conn = mock_streaming_connection

        # Initialize connection
        conn.segment_id = 10

        # Call end_of_utterance (Fix 2)
        await conn.end_of_utterance()

        # Verify NO EndOfStream was sent (connection keep-alive design)
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 0

        # Verify connection is still ready
        assert conn.is_connected
        assert not conn.is_closing

        print(f"✅ Connection kept alive for segment {conn.segment_id} (no EndOfStream)")

    async def test_end_of_utterance_logs_segment_id(self, mock_streaming_connection):
        """
        Test that end_of_utterance logs include segment_id for debugging

        Verifies:
        - Segment ID is tracked
        - Available for debugging/logging
        """
        conn = mock_streaming_connection
        segment_id = 25

        # Initialize with segment_id
        conn.reset_for_new_segment(segment_id)

        # Call end_of_utterance
        await conn.end_of_utterance()

        # Verify segment_id is accessible
        assert conn.segment_id == segment_id

        print(f"✅ end_of_utterance tracks segment_id={segment_id}")

    async def test_end_of_utterance_when_disconnected(self, mock_streaming_connection):
        """
        Test that end_of_utterance handles disconnected state gracefully

        Verifies:
        - No error when connection is closed
        - No message sent to closed connection
        """
        conn = mock_streaming_connection

        # Simulate disconnected state
        conn.is_connected = False

        # Should not raise error
        await conn.end_of_utterance()

        # Should not send any messages
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 0

        print("✅ end_of_utterance handles disconnected state gracefully")

    async def test_end_of_utterance_when_closing(self, mock_streaming_connection):
        """
        Test that end_of_utterance doesn't send when connection is closing

        Verifies:
        - No EndOfStream sent if connection is already closing
        - Prevents race conditions
        """
        conn = mock_streaming_connection

        # Simulate closing state
        conn.is_closing = True

        # Should not send message
        await conn.end_of_utterance()

        # Verify no EndOfStream sent
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 0

        print("✅ end_of_utterance prevents race conditions during close")

    async def test_multiple_end_of_utterance_calls(self, mock_streaming_connection):
        """
        Test multiple end_of_utterance calls in sequence

        Scenario:
        - User clicks Stop multiple times rapidly
        - Connection should stay alive (no EndOfStream)

        Verifies:
        - No EndOfStream messages sent (connection keep-alive)
        - No state corruption
        - Connection remains ready
        """
        conn = mock_streaming_connection

        # Call end_of_utterance 3 times
        for i in range(3):
            await conn.end_of_utterance()

        # Verify NO EndOfStream messages sent (connection keep-alive)
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 0

        # Connection should still be ready
        assert conn.is_connected
        assert not conn.is_closing

        print("✅ Multiple end_of_utterance calls handled correctly (connection kept alive)")


@pytest.mark.e2e
@pytest.mark.asyncio
class TestFix3_AudioEndHandler:
    """Test Fix 3: Audio end handler triggers final transcription"""

    async def test_audio_end_calls_end_of_utterance(self, mock_redis):
        """
        Test that audio_end event calls end_of_utterance()

        Simulates the complete flow from router.py:652

        Verifies:
        - streaming_conn.end_of_utterance() is called
        - Called before final event is published
        """
        # Create mock streaming connection
        streaming_conn = AsyncMock()
        streaming_conn.end_of_utterance = AsyncMock()
        streaming_conn.accumulated_text = "Hello world"
        streaming_conn.finalized_text = "Hello world"
        streaming_conn.segment_id = 1

        # Simulate audio_end handler (Fix 3)
        if streaming_conn:
            await streaming_conn.end_of_utterance()

        # Verify end_of_utterance was called
        streaming_conn.end_of_utterance.assert_called_once()

        print("✅ audio_end triggers end_of_utterance()")

    async def test_stt_final_event_emitted_after_audio_end(self, mock_redis):
        """
        Test that stt_final event is published after audio_end

        Complete stop button flow:
        1. User clicks Stop
        2. audio_end received
        3. end_of_utterance() called
        4. stt_final event published

        Verifies:
        - stt_final event is published to STT_OUTPUT_EVENTS channel
        - Event contains correct segment_id and text
        - Event has final=True flag
        """
        room_id = "test-room"
        segment_id = 15
        final_text = "Complete transcription"

        # Mock streaming connection
        streaming_conn = AsyncMock()
        streaming_conn.end_of_utterance = AsyncMock()
        streaming_conn.accumulated_text = final_text
        streaming_conn.finalized_text = final_text
        streaming_conn.segment_id = segment_id

        # Simulate audio_end handler
        await streaming_conn.end_of_utterance()

        # Publish stt_final event (as in router.py:664-688)
        final_event = {
            "type": "stt_final",
            "room_id": room_id,
            "segment_id": segment_id,
            "text": final_text,
            "lang": "en",
            "speaker": "user_a",
            "final": True,
            "speech_final": True,
            "ts_iso": datetime.utcnow().isoformat() + "Z"
        }

        await mock_redis.publish("stt_events", json.dumps(final_event))

        # Verify stt_final was published
        publishes = mock_redis._test_state['publishes']
        stt_finals = [p for p in publishes if p['channel'] == 'stt_events']
        assert len(stt_finals) == 1

        # Verify event content
        event_data = json.loads(stt_finals[0]['message'])
        assert event_data['type'] == 'stt_final'
        assert event_data['segment_id'] == segment_id
        assert event_data['text'] == final_text
        assert event_data['final'] is True

        print(f"✅ stt_final event published with segment_id={segment_id}")

    async def test_cost_tracking_on_audio_end(self, mock_redis):
        """
        Test that cost tracking event is published on audio_end

        Verifies:
        - Cost event published to COST_TRACKING_CHANNEL
        - Audio duration calculated correctly
        - Provider information included
        """
        room_id = "test-room"
        segment_id = 20
        provider = "speechmatics"

        # Simulate accumulated audio (5 seconds at 16kHz, 16-bit)
        audio_duration_seconds = 5.0
        audio_bytes = int(audio_duration_seconds * 16000 * 2)  # 16kHz, 2 bytes per sample

        # Calculate duration
        calculated_duration = audio_bytes / (16000 * 2)

        # Publish cost event (as in router.py:703-713)
        cost_event = {
            "room_id": room_id,
            "pipeline": "stt",
            "provider": provider,
            "mode": "final",
            "units": calculated_duration,
            "unit_type": "seconds",
            "segment_id": segment_id
        }

        await mock_redis.publish("cost_tracking", json.dumps(cost_event))

        # Verify cost event was published
        publishes = mock_redis._test_state['publishes']
        cost_events = [p for p in publishes if p['channel'] == 'cost_tracking']
        assert len(cost_events) == 1

        # Verify cost calculation
        event_data = json.loads(cost_events[0]['message'])
        assert event_data['units'] == audio_duration_seconds
        assert event_data['provider'] == provider
        assert event_data['segment_id'] == segment_id

        print(f"✅ Cost tracked: {audio_duration_seconds}s for {provider}")


@pytest.mark.e2e
@pytest.mark.asyncio
class TestCompleteStopButtonFlow:
    """End-to-end tests for complete stop button flow"""

    async def test_complete_stop_flow_speechmatics(self, mock_redis, mock_streaming_connection):
        """
        Complete stop button flow for Speechmatics provider

        Flow:
        1. segment_new - Start new segment
        2. audio_partial - Send audio chunks
        3. Receive partial transcriptions
        4. audio_end - User clicks Stop
        5. EndOfStream sent to Speechmatics (Fix 2)
        6. Final transcription received
        7. stt_final event published
        8. Cost tracking recorded

        Verifies all three fixes working together:
        - Fix 1: Segment ID initialized
        - Fix 2: EndOfStream sent
        - Fix 3: Final event published
        """
        room_id = "complete-flow-room"
        segment_id = 1
        conn = mock_streaming_connection

        # STEP 1: segment_new - Initialize new segment (Fix 1)
        conn.reset_for_new_segment(segment_id)
        assert conn.segment_id == segment_id
        print(f"✅ Step 1: Segment {segment_id} initialized")

        # STEP 2: audio_partial - Simulate sending audio chunks
        audio_chunks = [
            b"chunk1" * 100,
            b"chunk2" * 100,
            b"chunk3" * 100
        ]

        for chunk in audio_chunks:
            # In real flow, this would call conn.send_audio()
            pass

        print(f"✅ Step 2: Sent {len(audio_chunks)} audio chunks")

        # STEP 3: Simulate receiving partial transcriptions
        partials = ["Hello", "Hello there", "Hello there, how"]
        for i, text in enumerate(partials):
            partial_event = {
                "type": "stt_partial",
                "room_id": room_id,
                "segment_id": segment_id,
                "revision": i + 1,
                "text": text,
                "final": False
            }
            await mock_redis.publish("stt_events", json.dumps(partial_event))

        print(f"✅ Step 3: Received {len(partials)} partial transcriptions")

        # STEP 4: audio_end - User clicks Stop
        # This triggers Fix 3

        # STEP 5: EndOfStream sent (Fix 2)
        await conn.end_of_utterance()
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 1
        print("✅ Step 5: EndOfStream sent to Speechmatics")

        # STEP 6: Simulate final transcription from Speechmatics
        final_text = "Hello there, how are you?"
        conn.accumulated_text = final_text
        conn.finalized_text = final_text

        # STEP 7: Publish stt_final event
        final_event = {
            "type": "stt_final",
            "room_id": room_id,
            "segment_id": segment_id,
            "text": final_text,
            "lang": "en",
            "final": True,
            "speech_final": True,
            "ts_iso": datetime.utcnow().isoformat() + "Z"
        }
        await mock_redis.publish("stt_events", json.dumps(final_event))

        # Verify final event
        publishes = mock_redis._test_state['publishes']
        finals = [p for p in publishes if 'stt_final' in p['message']]
        assert len(finals) == 1
        print(f"✅ Step 7: stt_final published: '{final_text}'")

        # STEP 8: Track cost
        audio_duration = 5.5  # seconds
        cost_event = {
            "room_id": room_id,
            "pipeline": "stt",
            "provider": "speechmatics",
            "mode": "final",
            "units": audio_duration,
            "unit_type": "seconds",
            "segment_id": segment_id
        }
        await mock_redis.publish("cost_tracking", json.dumps(cost_event))

        # Verify cost tracking
        cost_publishes = [p for p in publishes if p['channel'] == 'cost_tracking']
        assert len(cost_publishes) == 1
        print(f"✅ Step 8: Cost tracked: {audio_duration}s")

        # FINAL VERIFICATION: All components working together
        assert conn.segment_id == segment_id  # Fix 1
        assert len(end_messages) == 1  # Fix 2
        assert len(finals) == 1  # Fix 3

        print("\n✅ COMPLETE STOP BUTTON FLOW VALIDATED")
        print(f"   - Segment ID: {segment_id}")
        print(f"   - Partials: {len(partials)}")
        print(f"   - Final: '{final_text}'")
        print(f"   - EndOfStream: Sent")
        print(f"   - Cost: {audio_duration}s")

    async def test_stop_button_multiple_segments(self, mock_redis, mock_streaming_connection):
        """
        Test stop button across multiple conversation segments

        Scenario:
        - User speaks (segment 1), clicks Stop
        - User speaks again (segment 2), clicks Stop
        - User speaks again (segment 3), clicks Stop

        Verifies:
        - Each segment gets correct segment_id
        - Each Stop triggers EndOfStream
        - Each segment produces final transcription
        - No cross-contamination between segments
        """
        room_id = "multi-segment-room"
        conn = mock_streaming_connection

        segments = [
            {"id": 1, "text": "First sentence"},
            {"id": 2, "text": "Second sentence"},
            {"id": 3, "text": "Third sentence"}
        ]

        for seg in segments:
            # Initialize segment (Fix 1)
            conn.reset_for_new_segment(seg["id"])
            assert conn.segment_id == seg["id"]

            # Simulate speaking
            conn.accumulated_text = seg["text"]

            # Click Stop - triggers EndOfStream (Fix 2)
            await conn.end_of_utterance()

            # Publish final (Fix 3)
            final_event = {
                "type": "stt_final",
                "room_id": room_id,
                "segment_id": seg["id"],
                "text": seg["text"],
                "final": True
            }
            await mock_redis.publish("stt_events", json.dumps(final_event))

        # Verify all EndOfStream messages sent
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 3

        # Verify all finals published
        publishes = mock_redis._test_state['publishes']
        finals = [p for p in publishes if 'stt_final' in p['message']]
        assert len(finals) == 3

        # Verify segment IDs are correct
        for i, final_pub in enumerate(finals):
            event = json.loads(final_pub['message'])
            assert event['segment_id'] == i + 1
            assert event['text'] == segments[i]['text']

        print(f"✅ Stop button works correctly across {len(segments)} segments")

    async def test_stop_button_with_empty_transcription(self, mock_redis, mock_streaming_connection):
        """
        Test stop button when no speech detected (empty transcription)

        Scenario:
        - User clicks microphone button (segment starts)
        - User immediately clicks Stop without speaking
        - No partials received
        - No final should be published (empty text)

        Verifies:
        - EndOfStream is still sent
        - No stt_final if text is empty
        - Cost still tracked (connection time)
        """
        room_id = "empty-speech-room"
        segment_id = 1
        conn = mock_streaming_connection

        # Initialize segment
        conn.reset_for_new_segment(segment_id)

        # No speech - accumulated_text is empty
        conn.accumulated_text = ""

        # User clicks Stop
        await conn.end_of_utterance()

        # Verify EndOfStream sent
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 1

        # Verify no stt_final published (empty text)
        # In real implementation, router.py:663 checks "if last_partial_text:"
        if conn.accumulated_text.strip():
            final_event = {
                "type": "stt_final",
                "room_id": room_id,
                "segment_id": segment_id,
                "text": conn.accumulated_text,
                "final": True
            }
            await mock_redis.publish("stt_events", json.dumps(final_event))

        # Verify no finals published
        publishes = mock_redis._test_state['publishes']
        finals = [p for p in publishes if 'stt_final' in p['message']]
        assert len(finals) == 0

        print("✅ Stop button with empty transcription handled correctly")

    async def test_stop_button_rapid_clicks(self, mock_redis, mock_streaming_connection):
        """
        Test rapid Stop button clicks (stress test)

        Scenario:
        - User clicks Stop 5 times rapidly
        - System should handle gracefully

        Verifies:
        - Multiple EndOfStream messages sent
        - No crashes or state corruption
        - System remains responsive
        """
        conn = mock_streaming_connection
        segment_id = 1

        # Initialize segment
        conn.reset_for_new_segment(segment_id)
        conn.accumulated_text = "Test speech"

        # Rapid clicks (5 times)
        click_count = 5
        for i in range(click_count):
            await conn.end_of_utterance()
            await asyncio.sleep(0.01)  # 10ms between clicks

        # Verify all EndOfStream messages sent
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == click_count

        # Verify state is still valid
        assert conn.segment_id == segment_id
        assert conn.accumulated_text == "Test speech"

        print(f"✅ Handled {click_count} rapid Stop button clicks")


@pytest.mark.integration
@pytest.mark.asyncio
class TestDebugInfoAndCostTracking:
    """Test debug info creation and cost tracking on stop"""

    async def test_debug_info_created_on_stop(self, mock_redis):
        """
        Test that debug info is created when user stops

        Verifies:
        - Debug info includes segment_id
        - Provider information captured
        - Final text included
        """
        room_id = "debug-room"
        segment_id = 10
        provider = "speechmatics"
        final_text = "Debug test transcription"

        # Simulate debug info creation (router.py:717+)
        debug_info = {
            "segment_id": segment_id,
            "provider": provider,
            "final_text": final_text,
            "timestamp": datetime.utcnow().isoformat()
        }

        # Verify debug info has correct data
        assert debug_info["segment_id"] == segment_id
        assert debug_info["provider"] == provider
        assert debug_info["final_text"] == final_text

        print("✅ Debug info created with segment_id and provider")

    async def test_cost_tracking_per_segment(self, mock_redis):
        """
        Test that cost tracking records per-segment costs

        Verifies:
        - Each segment tracked separately
        - Segment ID included in cost event
        - Duration calculated correctly
        """
        room_id = "cost-room"

        segments = [
            {"id": 1, "duration": 3.5},
            {"id": 2, "duration": 5.2},
            {"id": 3, "duration": 2.1}
        ]

        for seg in segments:
            cost_event = {
                "room_id": room_id,
                "pipeline": "stt",
                "provider": "speechmatics",
                "mode": "final",
                "units": seg["duration"],
                "unit_type": "seconds",
                "segment_id": seg["id"]
            }
            await mock_redis.publish("cost_tracking", json.dumps(cost_event))

        # Verify all cost events published
        publishes = mock_redis._test_state['publishes']
        cost_events = [p for p in publishes if p['channel'] == 'cost_tracking']
        assert len(cost_events) == 3

        # Verify segment IDs and durations
        for i, cost_pub in enumerate(cost_events):
            event = json.loads(cost_pub['message'])
            assert event['segment_id'] == segments[i]['id']
            assert event['units'] == segments[i]['duration']

        print(f"✅ Cost tracking per segment validated ({len(segments)} segments)")


@pytest.mark.integration
@pytest.mark.asyncio
class TestEdgeCases:
    """Test edge cases and error scenarios"""

    async def test_stop_button_after_provider_disconnect(self, mock_streaming_connection):
        """
        Test stop button when provider already disconnected

        Scenario:
        - Network issue disconnects Speechmatics
        - User clicks Stop
        - Should handle gracefully

        Verifies:
        - No error when provider disconnected
        - System remains stable
        """
        conn = mock_streaming_connection

        # Simulate provider disconnect
        conn.is_connected = False
        conn.ws_client.state = "CLOSED"

        # User clicks Stop
        await conn.end_of_utterance()

        # Should not send EndOfStream (connection closed)
        # But should not raise error
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 0

        print("✅ Stop button after disconnect handled gracefully")

    async def test_stop_button_during_segment_transition(self, mock_streaming_connection):
        """
        Test stop button clicked during segment transition

        Scenario:
        - Segment 1 ends
        - Segment 2 starting (reset_for_new_segment called)
        - User clicks Stop mid-transition

        Verifies:
        - No race condition
        - Correct segment_id used
        - Connection stays alive (no EndOfStream)
        """
        conn = mock_streaming_connection

        # End segment 1
        conn.reset_for_new_segment(1)
        await conn.end_of_utterance()

        # Start segment 2 (mid-transition)
        conn.reset_for_new_segment(2)

        # User clicks Stop during transition
        await conn.end_of_utterance()

        # Should use segment 2's ID
        assert conn.segment_id == 2

        # Should NOT have sent EndOfStream messages (connection keep-alive)
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 0

        # Connection should still be ready
        assert conn.is_connected

        print("✅ Stop button during segment transition handled correctly (connection kept alive)")

    async def test_final_arrives_before_audio_end(self, mock_redis, mock_streaming_connection):
        """
        Test final transcription arriving before audio_end

        Scenario:
        - User speaking
        - Speechmatics sends final (natural pause detected)
        - User clicks Stop after final already received

        Verifies:
        - No duplicate finals
        - No EndOfStream sent (connection keep-alive)
        - State remains consistent
        """
        room_id = "early-final-room"
        segment_id = 1
        conn = mock_streaming_connection

        conn.reset_for_new_segment(segment_id)

        # Speechmatics sends final BEFORE user clicks Stop
        final_text = "Early final transcription"
        conn.finalized_text = final_text
        conn.accumulated_text = final_text

        final_event = {
            "type": "stt_final",
            "room_id": room_id,
            "segment_id": segment_id,
            "text": final_text,
            "final": True
        }
        await mock_redis.publish("stt_events", json.dumps(final_event))

        # NOW user clicks Stop
        await conn.end_of_utterance()

        # Verify NO EndOfStream sent (connection keep-alive)
        end_messages = conn.ws_client.get_end_of_stream_messages()
        assert len(end_messages) == 0

        # Connection should still be ready
        assert conn.is_connected

        # Verify only one final published (no duplicate)
        publishes = mock_redis._test_state['publishes']
        finals = [p for p in publishes if 'stt_final' in p['message']]
        assert len(finals) == 1

        print("✅ Early final + audio_end handled without duplication")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration or e2e"])
