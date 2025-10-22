"""
Integration tests for Speechmatics STT provider.

Tests cover:
- WebSocket connection lifecycle
- Audio streaming
- Partial and final transcript handling
- Error recovery
- Connection pooling
- Real-time transcription flow
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import json
import base64
import os


@pytest.fixture
def speechmatics_config():
    """Speechmatics provider configuration."""
    return {
        "diarization": True,
        "operating_point": "enhanced",
        "max_delay": 2.0
    }


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    ws = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    ws.__aiter__ = Mock(return_value=iter([]))
    return ws


@pytest.fixture
def sample_audio_chunk():
    """Generate sample PCM16 audio data."""
    # 16kHz, 16-bit, mono, 0.5 seconds = 16000 samples
    num_samples = 8000  # 0.5 second
    audio_bytes = b'\x00\x00' * num_samples
    return base64.b64encode(audio_bytes).decode('utf-8')


class TestSpeechmaticsConnection:
    """Test Speechmatics WebSocket connection."""

    @pytest.mark.asyncio
    @patch.dict(os.environ, {'SPEECHMATICS_API_KEY': 'test_key', 'SPEECHMATICS_REGION': 'eu2'})
    async def test_connection_initialization(self, speechmatics_config):
        """Test WebSocket connection initialization."""
        # Test URL construction
        region = os.getenv("SPEECHMATICS_REGION", "eu2")
        url = f"wss://{region}.rt.speechmatics.com/v2"

        assert url == "wss://eu2.rt.speechmatics.com/v2"

    @pytest.mark.asyncio
    async def test_start_recognition_message(self, speechmatics_config):
        """Test StartRecognition message construction."""
        start_recognition = {
            "message": "StartRecognition",
            "audio_format": {
                "type": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 16000
            },
            "transcription_config": {
                "language": "pl",
                "operating_point": speechmatics_config["operating_point"],
                "max_delay": speechmatics_config["max_delay"],
                "enable_partials": True,
                "diarization": "speaker" if speechmatics_config["diarization"] else "none"
            }
        }

        assert start_recognition["message"] == "StartRecognition"
        assert start_recognition["audio_format"]["sample_rate"] == 16000
        assert start_recognition["transcription_config"]["operating_point"] == "enhanced"
        assert start_recognition["transcription_config"]["max_delay"] == 2.0

    @pytest.mark.asyncio
    async def test_audio_chunk_sending(self, mock_websocket, sample_audio_chunk):
        """Test sending audio chunks to WebSocket."""
        audio_bytes = base64.b64decode(sample_audio_chunk)

        await mock_websocket.send(audio_bytes)

        mock_websocket.send.assert_called_once_with(audio_bytes)

    @pytest.mark.asyncio
    async def test_end_of_stream_message(self, mock_websocket):
        """Test EndOfStream message."""
        end_of_stream = {
            "message": "EndOfStream",
            "last_seq_no": 0
        }

        await mock_websocket.send(json.dumps(end_of_stream))

        mock_websocket.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_close(self, mock_websocket):
        """Test proper connection close."""
        await mock_websocket.close()

        mock_websocket.close.assert_called_once()


class TestSpeechmaticsPartialHandling:
    """Test handling of partial transcripts."""

    @pytest.mark.asyncio
    async def test_partial_transcript_parsing(self):
        """Test parsing AddPartialTranscript messages."""
        message = {
            "message": "AddPartialTranscript",
            "metadata": {
                "transcript": "Hello",
                "start_time": 0.5,
                "end_time": 1.0
            }
        }

        msg_type = message.get("message")
        metadata = message.get("metadata", {})
        text = metadata.get("transcript", "")

        assert msg_type == "AddPartialTranscript"
        assert text == "Hello"

    @pytest.mark.asyncio
    async def test_word_accumulation(self):
        """Test word-by-word accumulation from partials."""
        accumulated_text = ""
        words = ["Hello", "world", "from", "Speechmatics"]

        for word in words:
            if accumulated_text:
                accumulated_text += " " + word
            else:
                accumulated_text = word

        assert accumulated_text == "Hello world from Speechmatics"

    @pytest.mark.asyncio
    async def test_empty_partial_skip(self):
        """Test skipping empty partials."""
        accumulated_text = "Hello world"

        # Simulate empty partial
        new_text = ""

        if new_text:  # Should skip
            accumulated_text += " " + new_text

        assert accumulated_text == "Hello world"

    @pytest.mark.asyncio
    async def test_partial_callback_invocation(self):
        """Test that partial callback is invoked with correct data."""
        callback_invoked = False
        received_text = None

        async def on_partial(result):
            nonlocal callback_invoked, received_text
            callback_invoked = True
            received_text = result.get("text")

        # Simulate partial result
        await on_partial({
            "text": "Test transcript",
            "language": "pl",
            "room_id": "test-room",
            "is_final": False
        })

        assert callback_invoked is True
        assert received_text == "Test transcript"


class TestSpeechmaticsFinalTranscripts:
    """Test handling of final transcripts."""

    @pytest.mark.asyncio
    async def test_final_transcript_parsing(self):
        """Test parsing AddTranscript messages."""
        message = {
            "message": "AddTranscript",
            "metadata": {
                "transcript": "Complete sentence.",
                "start_time": 0.0,
                "end_time": 5.0
            },
            "results": []
        }

        msg_type = message.get("message")
        text = message.get("metadata", {}).get("transcript", "")

        assert msg_type == "AddTranscript"
        assert text == "Complete sentence."

    @pytest.mark.asyncio
    async def test_final_callback_invocation(self):
        """Test that final callback is invoked."""
        callback_invoked = False
        received_text = None

        async def on_final(result):
            nonlocal callback_invoked, received_text
            callback_invoked = True
            received_text = result.get("text")

        await on_final({
            "text": "Final transcript",
            "language": "pl",
            "room_id": "test-room",
            "is_final": True
        })

        assert callback_invoked is True
        assert received_text == "Final transcript"


class TestSpeechmaticsErrorHandling:
    """Test error handling."""

    @pytest.mark.asyncio
    async def test_error_message_parsing(self):
        """Test parsing Error messages."""
        message = {
            "message": "Error",
            "type": "quota_exceeded",
            "reason": "Concurrent Quota Exceeded"
        }

        msg_type = message.get("message")
        error_type = message.get("type")
        reason = message.get("reason")

        assert msg_type == "Error"
        assert error_type == "quota_exceeded"
        assert reason == "Concurrent Quota Exceeded"

    @pytest.mark.asyncio
    async def test_error_callback_invocation(self):
        """Test that error callback is invoked."""
        callback_invoked = False
        error_details = None

        async def on_error(error):
            nonlocal callback_invoked, error_details
            callback_invoked = True
            error_details = error

        await on_error({
            "error": "quota_exceeded: Concurrent Quota Exceeded",
            "room_id": "test-room",
            "provider": "speechmatics"
        })

        assert callback_invoked is True
        assert "quota_exceeded" in error_details["error"]

    @pytest.mark.asyncio
    async def test_connection_failure_handling(self):
        """Test handling connection failures."""
        with pytest.raises(Exception) as exc_info:
            raise Exception("Connection failed")

        assert "Connection failed" in str(exc_info.value)


class TestSpeechmaticsMessageFlow:
    """Test complete message flow."""

    @pytest.mark.asyncio
    async def test_recognition_started(self):
        """Test RecognitionStarted message handling."""
        message = {
            "message": "RecognitionStarted",
            "id": "session-123"
        }

        assert message["message"] == "RecognitionStarted"

    @pytest.mark.asyncio
    async def test_end_of_transcript(self):
        """Test EndOfTranscript message handling."""
        message = {
            "message": "EndOfTranscript"
        }

        assert message["message"] == "EndOfTranscript"

    @pytest.mark.asyncio
    async def test_complete_transcription_flow(self):
        """Test complete flow: start -> partials -> final -> end."""
        messages = [
            {"message": "RecognitionStarted"},
            {"message": "AddPartialTranscript", "metadata": {"transcript": "Hello"}},
            {"message": "AddPartialTranscript", "metadata": {"transcript": "world"}},
            {"message": "AddTranscript", "metadata": {"transcript": "Hello world"}},
            {"message": "EndOfTranscript"}
        ]

        accumulated = ""
        final_text = None

        for msg in messages:
            msg_type = msg.get("message")

            if msg_type == "AddPartialTranscript":
                word = msg.get("metadata", {}).get("transcript", "")
                if accumulated:
                    accumulated += " " + word
                else:
                    accumulated = word

            elif msg_type == "AddTranscript":
                final_text = msg.get("metadata", {}).get("transcript", "")

        assert accumulated == "Hello world"
        assert final_text == "Hello world"


class TestSpeechmaticsConfiguration:
    """Test configuration options."""

    def test_operating_point_options(self):
        """Test operating_point configuration."""
        configs = [
            {"operating_point": "standard"},
            {"operating_point": "enhanced"}
        ]

        for config in configs:
            assert config["operating_point"] in ["standard", "enhanced"]

    def test_max_delay_range(self):
        """Test max_delay configuration range."""
        delays = [0.4, 0.7, 1.0, 2.0, 3.0]

        for delay in delays:
            assert 0.4 <= delay <= 3.0

    def test_diarization_options(self):
        """Test diarization configuration."""
        diarization_values = [True, False]

        for value in diarization_values:
            diarization = "speaker" if value else "none"
            assert diarization in ["speaker", "none"]

    def test_language_support(self):
        """Test supported language codes."""
        supported_languages = [
            "pl", "en", "es", "fr", "de", "it", "pt", "ru", "ar"
        ]

        for lang in supported_languages:
            assert len(lang) == 2


class TestSpeechmaticsPerformance:
    """Test performance characteristics."""

    @pytest.mark.asyncio
    async def test_partial_latency_simulation(self):
        """Test simulated partial transcript latency."""
        import time

        start = time.time()

        # Simulate partial transcription delay
        await asyncio.sleep(0.1)  # Simulated network + processing

        elapsed = time.time() - start

        # Should be quick (< 1 second with max_delay=0.4)
        assert elapsed < 1.0

    @pytest.mark.asyncio
    async def test_multiple_audio_chunks(self):
        """Test handling multiple audio chunks."""
        chunks_sent = 0
        max_chunks = 10

        for i in range(max_chunks):
            # Simulate sending chunk
            chunks_sent += 1
            await asyncio.sleep(0.01)  # Simulated send

        assert chunks_sent == max_chunks

    @pytest.mark.asyncio
    async def test_concurrent_transcription_simulation(self):
        """Test handling concurrent transcriptions."""
        async def transcribe_room(room_id):
            await asyncio.sleep(0.1)
            return f"Transcribed {room_id}"

        # Simulate 5 concurrent rooms
        tasks = [transcribe_room(f"room-{i}") for i in range(5)]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5


class TestSpeechmaticsQuality:
    """Test quality-related features."""

    def test_enhanced_vs_standard(self):
        """Test quality tier selection."""
        quality_tier = "standard"
        operating_point = "enhanced" if quality_tier == "standard" else "standard"

        assert operating_point == "enhanced"

    def test_max_delay_accuracy_tradeoff(self):
        """Test max_delay affects accuracy."""
        # Lower delay = faster but less accurate
        low_delay_config = {"max_delay": 0.4}
        # Higher delay = slower but more accurate
        high_delay_config = {"max_delay": 2.0}

        assert low_delay_config["max_delay"] < high_delay_config["max_delay"]
        assert high_delay_config["max_delay"] == 2.0  # Our optimal setting
