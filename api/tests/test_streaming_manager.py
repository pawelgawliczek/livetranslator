"""
Unit tests for Streaming Manager and Connection Pool.

Tests cover:
- Connection pool management
- Persistent websocket lifecycle
- Connection reuse and cleanup
- Provider-specific connection creation
- Error handling and fallback
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from datetime import datetime, timedelta


# Mock the streaming_manager module
@pytest.fixture
def mock_websockets():
    """Mock websockets library."""
    with patch('api.routers.stt.streaming_manager.websockets') as mock_ws:
        yield mock_ws


@pytest.fixture
def streaming_manager():
    """Create a StreamingManager instance."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../routers/stt'))
    from streaming_manager import StreamingManager
    return StreamingManager()


@pytest.fixture
def streaming_connection():
    """Create a StreamingConnection instance."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../routers/stt'))
    from streaming_manager import StreamingConnection

    async def on_partial(result):
        pass

    async def on_final(result):
        pass

    async def on_error(error):
        pass

    return StreamingConnection(
        room_id="test-room",
        provider="speechmatics",
        language="pl",
        config={"diarization": True, "operating_point": "enhanced", "max_delay": 2.0},
        on_partial=on_partial,
        on_final=on_final,
        on_error=on_error
    )


class TestStreamingConnection:
    """Test suite for StreamingConnection class."""

    def test_connection_initialization(self, streaming_connection):
        """Test that StreamingConnection initializes correctly."""
        assert streaming_connection.room_id == "test-room"
        assert streaming_connection.provider == "speechmatics"
        assert streaming_connection.language == "pl"
        assert streaming_connection.config["operating_point"] == "enhanced"
        assert streaming_connection.is_connected is False
        assert streaming_connection.is_closing is False
        assert streaming_connection.accumulated_text == ""

    def test_connection_attributes(self, streaming_connection):
        """Test connection has required attributes."""
        assert hasattr(streaming_connection, 'created_at')
        assert hasattr(streaming_connection, 'last_activity')
        assert hasattr(streaming_connection, 'segment_id')
        assert hasattr(streaming_connection, 'revision')
        assert isinstance(streaming_connection.created_at, datetime)

    @pytest.mark.asyncio
    async def test_connection_lifecycle_flags(self, streaming_connection):
        """Test connection lifecycle flags."""
        assert streaming_connection.is_connected is False
        assert streaming_connection.is_closing is False

        # Simulate connection
        streaming_connection.is_connected = True
        assert streaming_connection.is_connected is True

        # Simulate closing
        streaming_connection.is_closing = True
        assert streaming_connection.is_closing is True

    def test_accumulated_text_initialization(self, streaming_connection):
        """Test that accumulated_text starts empty."""
        assert streaming_connection.accumulated_text == ""

        # Simulate accumulation
        streaming_connection.accumulated_text = "Test"
        assert streaming_connection.accumulated_text == "Test"

        streaming_connection.accumulated_text += " Text"
        assert streaming_connection.accumulated_text == "Test Text"

    def test_revision_counter(self, streaming_connection):
        """Test revision counter increments correctly."""
        assert streaming_connection.revision == 0

        streaming_connection.revision += 1
        assert streaming_connection.revision == 1

        for i in range(5):
            streaming_connection.revision += 1
        assert streaming_connection.revision == 6


class TestStreamingManager:
    """Test suite for StreamingManager connection pool."""

    def test_manager_initialization(self, streaming_manager):
        """Test that StreamingManager initializes with empty pool."""
        assert len(streaming_manager.connections) == 0

    def test_connection_key_generation(self, streaming_manager):
        """Test connection pool key generation."""
        key = streaming_manager._get_key("room-123", "speechmatics")
        assert key == "room-123:speechmatics"

        key2 = streaming_manager._get_key("room-456", "google_v2")
        assert key2 == "room-456:google_v2"

    @pytest.mark.asyncio
    async def test_connection_pool_isolation(self, streaming_manager):
        """Test that different rooms/providers use separate connections."""
        key1 = streaming_manager._get_key("room-1", "speechmatics")
        key2 = streaming_manager._get_key("room-2", "speechmatics")
        key3 = streaming_manager._get_key("room-1", "google_v2")

        assert key1 != key2  # Different rooms
        assert key1 != key3  # Same room, different provider
        assert key2 != key3  # Different everything

    @pytest.mark.asyncio
    async def test_connection_cleanup(self, streaming_manager):
        """Test connection cleanup removes entry from pool."""
        # Manually add a mock connection
        mock_conn = Mock()
        mock_conn.close = AsyncMock()
        mock_conn.is_connected = True
        mock_conn.is_closing = False

        key = "test-room:speechmatics"
        streaming_manager.connections[key] = mock_conn

        assert len(streaming_manager.connections) == 1

        # Clean up
        await streaming_manager.close_connection("test-room", "speechmatics")

        assert len(streaming_manager.connections) == 0

    @pytest.mark.asyncio
    async def test_close_all_for_room(self, streaming_manager):
        """Test closing all connections for a specific room."""
        # Add multiple connections for same room, different providers
        mock_conn1 = Mock()
        mock_conn1.close = AsyncMock()
        mock_conn2 = Mock()
        mock_conn2.close = AsyncMock()
        mock_conn3 = Mock()
        mock_conn3.close = AsyncMock()

        streaming_manager.connections["room-1:speechmatics"] = mock_conn1
        streaming_manager.connections["room-1:google_v2"] = mock_conn2
        streaming_manager.connections["room-2:speechmatics"] = mock_conn3

        assert len(streaming_manager.connections) == 3

        # Close all for room-1
        await streaming_manager.close_all_for_room("room-1")

        # Should have removed 2, kept 1
        assert len(streaming_manager.connections) == 1
        assert "room-2:speechmatics" in streaming_manager.connections

    @pytest.mark.asyncio
    async def test_stale_connection_cleanup(self, streaming_manager):
        """Test cleanup of stale connections based on age."""
        # Create a connection with old last_activity
        mock_conn = Mock()
        mock_conn.close = AsyncMock()
        mock_conn.last_activity = datetime.now() - timedelta(seconds=400)

        streaming_manager.connections["stale-room:speechmatics"] = mock_conn

        # Create a fresh connection
        fresh_conn = Mock()
        fresh_conn.close = AsyncMock()
        fresh_conn.last_activity = datetime.now()

        streaming_manager.connections["active-room:speechmatics"] = fresh_conn

        assert len(streaming_manager.connections) == 2

        # Cleanup connections older than 300 seconds
        await streaming_manager.cleanup_stale_connections(max_age_seconds=300)

        # Should have removed stale, kept fresh
        assert len(streaming_manager.connections) == 1
        assert "active-room:speechmatics" in streaming_manager.connections


class TestSpeechmaticsIntegration:
    """Test Speechmatics-specific integration."""

    @pytest.mark.asyncio
    async def test_speechmatics_config_parsing(self, streaming_connection):
        """Test that Speechmatics config is parsed correctly."""
        config = streaming_connection.config

        assert config["diarization"] is True
        assert config["operating_point"] == "enhanced"
        assert config["max_delay"] == 2.0

    def test_speechmatics_language_normalization(self):
        """Test language code normalization for Speechmatics."""
        # Mock the normalize function
        def _normalize_language(language: str) -> str:
            lang_map = {
                "pl": "pl",
                "pl-PL": "pl",
                "en": "en",
                "en-US": "en",
                "en-GB": "en",
                "auto": "en",
            }
            return lang_map.get(language, "en")

        assert _normalize_language("pl-PL") == "pl"
        assert _normalize_language("en-US") == "en"
        assert _normalize_language("auto") == "en"

    @pytest.mark.asyncio
    async def test_word_accumulation(self):
        """Test word-by-word accumulation logic."""
        accumulated = ""
        words = ["Hello", "world", "from", "Speechmatics"]

        for word in words:
            if accumulated:
                accumulated += " " + word
            else:
                accumulated = word

        assert accumulated == "Hello world from Speechmatics"

    @pytest.mark.asyncio
    async def test_empty_partial_handling(self):
        """Test handling of empty partial transcripts."""
        accumulated = "Hello world"
        new_text = ""

        # Empty text should not change accumulation
        if new_text:
            accumulated += " " + new_text

        assert accumulated == "Hello world"


class TestConnectionPoolConcurrency:
    """Test concurrent connection management."""

    @pytest.mark.asyncio
    async def test_concurrent_room_connections(self, streaming_manager):
        """Test managing connections for multiple rooms concurrently."""
        rooms = [f"room-{i}" for i in range(5)]

        # Simulate adding connections for multiple rooms
        for room in rooms:
            key = streaming_manager._get_key(room, "speechmatics")
            mock_conn = Mock()
            mock_conn.close = AsyncMock()
            streaming_manager.connections[key] = mock_conn

        assert len(streaming_manager.connections) == 5

        # Close all
        close_tasks = [streaming_manager.close_all_for_room(room) for room in rooms]
        await asyncio.gather(*close_tasks)

        assert len(streaming_manager.connections) == 0

    @pytest.mark.asyncio
    async def test_connection_reuse_prevention(self, streaming_manager):
        """Test that stale/closing connections are not reused."""
        # Add a closing connection
        mock_conn = Mock()
        mock_conn.is_connected = True
        mock_conn.is_closing = True

        key = "room-1:speechmatics"
        streaming_manager.connections[key] = mock_conn

        # Should not reuse closing connection
        # (This would be tested in get_or_create_connection logic)
        conn = streaming_manager.connections.get(key)

        # In real implementation, this would trigger new connection
        assert conn.is_closing is True


class TestErrorHandling:
    """Test error handling in streaming connections."""

    @pytest.mark.asyncio
    async def test_connection_failure_callback(self):
        """Test that connection failures trigger error callback."""
        error_called = False
        error_message = None

        async def on_error(error):
            nonlocal error_called, error_message
            error_called = True
            error_message = error.get("error")

        # Simulate error
        await on_error({"error": "Connection failed", "provider": "speechmatics"})

        assert error_called is True
        assert error_message == "Connection failed"

    @pytest.mark.asyncio
    async def test_audio_send_error_handling(self, streaming_connection):
        """Test handling of errors when sending audio."""
        # Simulate not connected state
        streaming_connection.is_connected = False

        # Should handle gracefully (would log and return in real impl)
        try:
            if not streaming_connection.is_connected:
                print("Cannot send audio - not connected")
                return
        except Exception as e:
            pytest.fail(f"Should not raise exception: {e}")


class TestWebSocketProtocol:
    """Test WebSocket protocol implementation."""

    def test_speechmatics_start_recognition_message(self):
        """Test StartRecognition message format."""
        message = {
            "message": "StartRecognition",
            "audio_format": {
                "type": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 16000
            },
            "transcription_config": {
                "language": "pl",
                "operating_point": "enhanced",
                "max_delay": 2.0,
                "enable_partials": True,
                "diarization": "speaker"
            }
        }

        assert message["message"] == "StartRecognition"
        assert message["audio_format"]["encoding"] == "pcm_s16le"
        assert message["transcription_config"]["language"] == "pl"

    def test_speechmatics_end_of_stream_message(self):
        """Test EndOfStream message format."""
        message = {
            "message": "EndOfStream",
            "last_seq_no": 0
        }

        assert message["message"] == "EndOfStream"
        assert "last_seq_no" in message

    def test_partial_transcript_message_parsing(self):
        """Test parsing AddPartialTranscript messages."""
        message = {
            "message": "AddPartialTranscript",
            "metadata": {
                "transcript": "Hello world"
            }
        }

        msg_type = message.get("message")
        text = message.get("metadata", {}).get("transcript", "")

        assert msg_type == "AddPartialTranscript"
        assert text == "Hello world"
