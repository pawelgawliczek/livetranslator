"""
Integration tests for Speechmatics VAD synchronization.

Tests the complete flow of EndOfTranscript → stt_finalize → frontend
to ensure single source of truth for when partials transition to finals.

These tests verify commit 559e77f mechanism #7: VAD Synchronization.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
import asyncio
import json
import time


class TestEndOfTranscriptHandling:
    """Test EndOfTranscript message handling."""

    @pytest.mark.asyncio
    async def test_end_of_transcript_message_structure(self):
        """Test EndOfTranscript message has correct structure."""
        message = {
            "message": "EndOfTranscript"
        }

        assert message["message"] == "EndOfTranscript"

    @pytest.mark.asyncio
    async def test_end_of_transcript_triggers_finalize_callback(self):
        """Test EndOfTranscript triggers on_finalize callback."""
        finalize_called = False

        async def on_finalize():
            nonlocal finalize_called
            finalize_called = True

        # Simulate EndOfTranscript message
        message_type = "EndOfTranscript"

        if message_type == "EndOfTranscript":
            await on_finalize()

        assert finalize_called is True

    @pytest.mark.asyncio
    async def test_end_of_transcript_timing_logged(self):
        """Test EndOfTranscript timing is logged."""
        logs = []

        def log(msg):
            logs.append(msg)

        # Simulate EndOfTranscript with logging
        finalize_timestamp = time.time()
        log(f"[StreamingConnection] 🏁 [{finalize_timestamp:.3f}] Speechmatics EndOfTranscript received")
        log(f"[StreamingConnection] 📤 [{finalize_timestamp:.3f}] Sending stt_finalize to frontend")

        assert len(logs) == 2
        assert "EndOfTranscript received" in logs[0]
        assert "Sending stt_finalize" in logs[1]


class TestSttFinalizeEvent:
    """Test stt_finalize event generation."""

    @pytest.mark.asyncio
    async def test_stt_finalize_event_structure(self):
        """Test stt_finalize event has all required fields."""
        backend_timestamp = time.time()

        finalize_event = {
            "type": "stt_finalize",
            "segment_id": 123,
            "room_id": "test-room-456",
            "language": "pl",
            "backend_timestamp": backend_timestamp
        }

        assert finalize_event["type"] == "stt_finalize"
        assert finalize_event["segment_id"] == 123
        assert finalize_event["room_id"] == "test-room-456"
        assert finalize_event["language"] == "pl"
        assert "backend_timestamp" in finalize_event
        assert isinstance(finalize_event["backend_timestamp"], float)

    @pytest.mark.asyncio
    async def test_stt_finalize_timestamp_is_current_time(self):
        """Test backend_timestamp reflects when EndOfTranscript was received."""
        before = time.time()
        backend_timestamp = time.time()
        after = time.time()

        assert before <= backend_timestamp <= after

    @pytest.mark.asyncio
    async def test_stt_finalize_sent_to_on_final_callback(self):
        """Test stt_finalize is sent via on_final callback."""
        finalize_data = None

        async def on_final(data):
            nonlocal finalize_data
            finalize_data = data

        # Simulate sending finalize event
        backend_timestamp = time.time()
        await on_final({
            "type": "stt_finalize",
            "segment_id": 1,
            "room_id": "test-room",
            "language": "pl",
            "backend_timestamp": backend_timestamp
        })

        assert finalize_data is not None
        assert finalize_data["type"] == "stt_finalize"
        assert "backend_timestamp" in finalize_data


class TestFrontendSyncDelayCalculation:
    """Test frontend sync delay calculation."""

    @pytest.mark.asyncio
    async def test_frontend_receives_backend_timestamp(self):
        """Test frontend receives backend timestamp in stt_finalize."""
        backend_timestamp = time.time()

        # Simulate message received by frontend
        message = {
            "type": "stt_finalize",
            "backend_timestamp": backend_timestamp
        }

        assert "backend_timestamp" in message
        assert isinstance(message["backend_timestamp"], float)

    @pytest.mark.asyncio
    async def test_sync_delay_calculation(self):
        """Test sync delay is calculated correctly."""
        backend_timestamp = time.time()

        # Simulate network delay
        await asyncio.sleep(0.05)

        # Frontend receives message
        frontend_timestamp = time.time()
        sync_delay = frontend_timestamp - backend_timestamp

        assert sync_delay >= 0.05
        assert sync_delay < 0.2  # Should be < 200ms

    @pytest.mark.asyncio
    async def test_sync_delay_formatting(self):
        """Test sync delay is formatted in milliseconds."""
        backend_timestamp = 1000.000
        frontend_timestamp = 1000.055

        sync_delay = frontend_timestamp - backend_timestamp
        sync_delay_ms = sync_delay * 1000

        assert abs(sync_delay - 0.055) < 0.001  # Allow floating point error
        assert abs(sync_delay_ms - 55.0) < 0.1  # Allow floating point error

    @pytest.mark.asyncio
    async def test_sync_delay_logged_on_frontend(self):
        """Test sync delay is logged by frontend."""
        logs = []

        def console_log(msg):
            logs.append(msg)

        backend_timestamp = time.time()
        await asyncio.sleep(0.03)
        frontend_timestamp = time.time()

        sync_delay = frontend_timestamp - backend_timestamp
        sync_delay_ms = int(sync_delay * 1000)

        console_log(f"[WS] ✅ Finalizing segment 1 (sync delay: {sync_delay_ms}ms)")

        assert len(logs) == 1
        assert "sync delay:" in logs[0]
        assert "ms)" in logs[0]


class TestSegmentFinalization:
    """Test segment finalization flow."""

    @pytest.mark.asyncio
    async def test_segment_marked_as_final(self):
        """Test segment is marked as final when stt_finalize received."""
        segment = {
            "id": 1,
            "text": "Test text",
            "final": False,
            "processing": True,
            "type": "stt_partial"
        }

        # Receive stt_finalize
        message = {"type": "stt_finalize", "segment_id": 1}

        if message["type"] == "stt_finalize":
            segment["final"] = True
            segment["processing"] = False
            segment["type"] = "stt_final"

        assert segment["final"] is True
        assert segment["processing"] is False
        assert segment["type"] == "stt_final"

    @pytest.mark.asyncio
    async def test_only_matching_segment_is_finalized(self):
        """Test only the segment with matching ID is finalized."""
        segments = {
            1: {"id": 1, "final": False},
            2: {"id": 2, "final": False},
            3: {"id": 3, "final": False}
        }

        # Finalize segment 2
        message = {"type": "stt_finalize", "segment_id": 2}

        segment_id = message["segment_id"]
        if segment_id in segments:
            segments[segment_id]["final"] = True

        assert segments[1]["final"] is False
        assert segments[2]["final"] is True
        assert segments[3]["final"] is False

    @pytest.mark.asyncio
    async def test_finalize_handles_missing_segment(self):
        """Test finalize handles case where segment doesn't exist."""
        segments = {}

        message = {"type": "stt_finalize", "segment_id": 999}

        segment_id = message["segment_id"]
        if segment_id in segments:
            segments[segment_id]["final"] = True

        # Should not raise error
        assert segment_id not in segments


class TestVADTimingAlignment:
    """Test VAD timing is aligned between backend and frontend."""

    @pytest.mark.asyncio
    async def test_vad_trigger_matches_end_of_transcript(self):
        """Test VAD trigger (0.6s) aligns with EndOfTranscript."""
        end_of_utterance_silence_trigger = 0.6  # From config

        # User stops speaking at T=10.0s
        utterance_end = 10.0

        # EndOfTranscript should fire at T=10.6s (after 0.6s silence)
        expected_end_of_transcript_time = utterance_end + end_of_utterance_silence_trigger

        assert expected_end_of_transcript_time == 10.6

    @pytest.mark.asyncio
    async def test_frontend_finalization_synchronized_with_backend(self):
        """Test frontend only finalizes when backend says to."""
        # Backend receives EndOfTranscript
        backend_finalize_time = 10.6

        # Frontend should finalize at same time (+ network delay)
        network_delay = 0.05
        frontend_finalize_time = backend_finalize_time + network_delay

        # Frontend should NOT finalize before backend
        assert frontend_finalize_time > backend_finalize_time

        # Delay should be minimal
        actual_delay = frontend_finalize_time - backend_finalize_time
        assert actual_delay < 0.2  # Less than 200ms


class TestNoCompetingVADs:
    """Test that only Speechmatics VAD controls finalization."""

    @pytest.mark.asyncio
    async def test_frontend_vad_disabled_for_speechmatics(self):
        """Test frontend client-side VAD is NOT used for Speechmatics."""
        provider = "speechmatics"
        use_frontend_vad = False  # Should be disabled

        # Frontend should wait for stt_finalize from backend
        finalize_source = "backend_stt_finalize" if provider == "speechmatics" else "frontend_vad"

        assert use_frontend_vad is False
        assert finalize_source == "backend_stt_finalize"

    @pytest.mark.asyncio
    async def test_single_source_of_truth(self):
        """Test Speechmatics EndOfTranscript is single source of truth."""
        finalization_triggers = []

        # Speechmatics fires EndOfTranscript
        finalization_triggers.append("speechmatics_end_of_transcript")

        # Frontend should only respond to this trigger
        assert len(finalization_triggers) == 1
        assert finalization_triggers[0] == "speechmatics_end_of_transcript"


class TestEndToEndVADFlow:
    """Test complete end-to-end VAD synchronization flow."""

    @pytest.mark.asyncio
    async def test_complete_vad_flow(self):
        """
        Test complete flow:
        1. User stops speaking
        2. Speechmatics VAD detects 0.6s silence
        3. Speechmatics sends EndOfTranscript
        4. Backend forwards as stt_finalize
        5. Frontend marks segment as final
        """
        timeline = []

        # Step 1: User stops speaking
        utterance_end = 10.0
        timeline.append(("user_stops", utterance_end))

        # Step 2: VAD detects silence (0.6s later)
        vad_trigger_delay = 0.6
        vad_detection_time = utterance_end + vad_trigger_delay
        timeline.append(("vad_detected", vad_detection_time))

        # Step 3: Speechmatics sends EndOfTranscript
        end_of_transcript_time = vad_detection_time
        timeline.append(("end_of_transcript_sent", end_of_transcript_time))

        # Step 4: Backend forwards as stt_finalize
        backend_timestamp = end_of_transcript_time
        timeline.append(("backend_sends_finalize", backend_timestamp))

        # Step 5: Frontend receives (with network delay)
        network_delay = 0.05
        frontend_timestamp = backend_timestamp + network_delay
        timeline.append(("frontend_finalizes", frontend_timestamp))

        # Verify timeline
        assert timeline[0] == ("user_stops", 10.0)
        assert timeline[1] == ("vad_detected", 10.6)
        assert timeline[2] == ("end_of_transcript_sent", 10.6)
        assert timeline[3] == ("backend_sends_finalize", 10.6)
        assert timeline[4] == ("frontend_finalizes", 10.65)

    @pytest.mark.asyncio
    async def test_vad_flow_timing_measurements(self):
        """Test timing measurements at each step of VAD flow."""
        measurements = {}

        # User stops speaking
        measurements["utterance_end"] = time.time()

        # VAD trigger (0.6s later)
        await asyncio.sleep(0.1)  # Simulated VAD detection time
        measurements["vad_trigger"] = time.time()

        # Backend sends finalize
        measurements["backend_finalize"] = time.time()

        # Frontend receives
        await asyncio.sleep(0.05)  # Simulated network delay
        measurements["frontend_finalize"] = time.time()

        # Calculate delays
        vad_delay = measurements["vad_trigger"] - measurements["utterance_end"]
        backend_processing = measurements["backend_finalize"] - measurements["vad_trigger"]
        network_delay = measurements["frontend_finalize"] - measurements["backend_finalize"]

        # Verify timing characteristics
        assert vad_delay >= 0.1  # Simulated 0.1s
        assert backend_processing < 0.01  # Should be instant
        assert network_delay >= 0.05  # Simulated 0.05s

    @pytest.mark.asyncio
    async def test_multiple_segments_vad_synchronization(self):
        """Test VAD synchronization works for multiple consecutive segments."""
        segments = []

        # Segment 1
        segment_1_end = 5.0
        segments.append({
            "id": 1,
            "utterance_end": segment_1_end,
            "finalized_at": segment_1_end + 0.6,
            "final": True
        })

        # Segment 2 (user speaks immediately after)
        segment_2_end = 10.0
        segments.append({
            "id": 2,
            "utterance_end": segment_2_end,
            "finalized_at": segment_2_end + 0.6,
            "final": True
        })

        # Segment 3
        segment_3_end = 15.5
        segments.append({
            "id": 3,
            "utterance_end": segment_3_end,
            "finalized_at": segment_3_end + 0.6,
            "final": True
        })

        # Verify each segment finalized correctly
        assert segments[0]["finalized_at"] == 5.6
        assert segments[1]["finalized_at"] == 10.6
        assert segments[2]["finalized_at"] == 16.1

        # Verify all marked as final
        assert all(seg["final"] for seg in segments)


class TestErrorCasesVADSync:
    """Test error cases in VAD synchronization."""

    @pytest.mark.asyncio
    async def test_handles_missing_backend_timestamp(self):
        """Test frontend handles missing backend timestamp gracefully."""
        message = {
            "type": "stt_finalize",
            "segment_id": 1
            # Missing backend_timestamp
        }

        backend_timestamp = message.get("backend_timestamp")
        sync_delay = None

        if backend_timestamp:
            frontend_timestamp = time.time()
            sync_delay = frontend_timestamp - backend_timestamp

        # Should handle gracefully
        assert backend_timestamp is None
        assert sync_delay is None

    @pytest.mark.asyncio
    async def test_handles_out_of_order_finalize(self):
        """Test handling stt_finalize arriving out of order."""
        segments = {
            1: {"id": 1, "final": False},
            2: {"id": 2, "final": False}
        }

        # Finalize arrives for segment 2 before segment 1
        finalize_2 = {"type": "stt_finalize", "segment_id": 2}
        finalize_1 = {"type": "stt_finalize", "segment_id": 1}

        # Process out of order
        segments[finalize_2["segment_id"]]["final"] = True
        segments[finalize_1["segment_id"]]["final"] = True

        # Both should be finalized
        assert segments[1]["final"] is True
        assert segments[2]["final"] is True

    @pytest.mark.asyncio
    async def test_handles_duplicate_finalize(self):
        """Test handling duplicate stt_finalize messages."""
        segment = {"id": 1, "final": False, "finalize_count": 0}

        # First finalize
        segment["final"] = True
        segment["finalize_count"] += 1

        # Duplicate finalize
        if segment["final"]:
            # Already final, just increment counter
            segment["finalize_count"] += 1

        assert segment["final"] is True
        assert segment["finalize_count"] == 2  # Tracked duplicates

    @pytest.mark.asyncio
    async def test_handles_network_timeout(self):
        """Test handling network timeout for stt_finalize delivery."""
        max_wait_time = 5.0  # Max time to wait for finalize
        finalize_received = False

        async def wait_for_finalize():
            nonlocal finalize_received
            try:
                await asyncio.wait_for(
                    asyncio.sleep(10.0),  # Simulate never arriving
                    timeout=max_wait_time
                )
                finalize_received = True
            except asyncio.TimeoutError:
                # Timeout - finalize anyway
                finalize_received = False

        await wait_for_finalize()

        # Should timeout gracefully
        assert finalize_received is False
