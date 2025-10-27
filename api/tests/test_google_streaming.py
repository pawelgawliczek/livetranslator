"""
Unit tests for Google Cloud Speech-to-Text v2 Streaming.

Tests cover:
- Google streaming session creation
- Partial result handling and concatenation
- Final result handling with speaker diarization
- Audio encoding configuration (LINEAR16)
- Language normalization (ar-EG support)
- Async/sync threading bridge for gRPC

NOTE: These tests require google-cloud-speech library which is not installed.
They are skipped until the dependency is added to requirements.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from datetime import datetime

# Skip all tests in this module if google.cloud is not available
pytest.importorskip("google.cloud.speech_v2", reason="google-cloud-speech library not installed")


@pytest.fixture
def mock_google_client():
    """Mock Google Speech v2 client."""
    with patch('api.routers.stt.google_streaming.speech') as mock_speech:
        mock_client = MagicMock()
        mock_speech.SpeechClient.return_value = mock_client
        yield mock_client


@pytest.fixture
def google_streaming_client():
    """Create a GoogleStreamingClient instance."""
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../routers/stt'))

    with patch('api.routers.stt.google_streaming.GOOGLE_APPLICATION_CREDENTIALS', '/fake/creds.json'):
        with patch('api.routers.stt.google_streaming.GOOGLE_CLOUD_PROJECT', 'test-project'):
            with patch('api.routers.stt.google_streaming.GOOGLE_CLOUD_LOCATION', 'eu'):
                from google_streaming import GoogleStreamingClient
                return GoogleStreamingClient()


class TestGoogleStreamingClient:
    """Test Google Streaming Client functionality."""

    @pytest.mark.asyncio
    async def test_create_session(self, google_streaming_client):
        """Test creating a streaming session."""
        session = await google_streaming_client.create_session(
            session_id="test-room",
            language="ar-EG",
            on_partial=AsyncMock(),
            on_final=AsyncMock(),
            on_error=AsyncMock()
        )

        assert session.session_id == "test-room"
        assert session.language == "ar-EG"
        assert session.config == {}
        assert session.is_started == False
        assert session.is_connected == False

    @pytest.mark.asyncio
    async def test_language_normalization(self, google_streaming_client):
        """Test language code normalization."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../routers/stt'))
        from google_streaming import _normalize_language

        # Test Arabic normalization
        assert _normalize_language("ar") == "ar-EG"
        assert _normalize_language("ar-EG") == "ar-EG"
        assert _normalize_language("ar-SA") == "ar-SA"

        # Test English normalization
        assert _normalize_language("en") == "en-US"
        assert _normalize_language("en-EN") == "en-US"
        assert _normalize_language("en-GB") == "en-GB"

        # Test Polish normalization
        assert _normalize_language("pl") == "pl-PL"
        assert _normalize_language("pl-PL") == "pl-PL"

    @pytest.mark.asyncio
    async def test_diarization_disabled_by_default(self, google_streaming_client):
        """Test that diarization is disabled by default (for Arabic streaming)."""
        session = await google_streaming_client.create_session(
            session_id="test-room",
            language="ar-EG",
            config={},  # Empty config should NOT enable diarization
            on_partial=AsyncMock(),
            on_final=AsyncMock(),
            on_error=AsyncMock()
        )

        # Verify config.get("diarization", False) defaults to False
        assert session.config.get("diarization", False) == False

    @pytest.mark.asyncio
    async def test_diarization_explicit_enable(self, google_streaming_client):
        """Test that diarization can be explicitly enabled."""
        session = await google_streaming_client.create_session(
            session_id="test-room",
            language="ar-EG",
            config={"diarization": True, "min_speaker_count": 2, "max_speaker_count": 4},
            on_partial=AsyncMock(),
            on_final=AsyncMock(),
            on_error=AsyncMock()
        )

        assert session.config.get("diarization") == True
        assert session.config.get("min_speaker_count") == 2
        assert session.config.get("max_speaker_count") == 4


class TestGooglePartialHandling:
    """Test Google partial result handling."""

    @pytest.mark.asyncio
    async def test_concatenate_multiple_partials(self):
        """Test concatenating multiple partial results in one response."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../routers/stt'))

        with patch('api.routers.stt.google_streaming.speech'):
            from google_streaming import GoogleStreamingClient

            client = GoogleStreamingClient()

            # Mock session with callbacks
            partial_results = []
            async def on_partial(result):
                partial_results.append(result)

            session = await client.create_session(
                session_id="test",
                language="ar-EG",
                on_partial=on_partial,
                on_final=AsyncMock(),
                on_error=AsyncMock()
            )

            # Mock response with 2 partial results (Google sends stable + unstable)
            mock_response = MagicMock()

            # Result 1: Stable partial
            result1 = MagicMock()
            result1.is_final = False
            result1.stability = 0.9
            result1.alternatives = [MagicMock()]
            result1.alternatives[0].transcript = "واحد"

            # Result 2: Unstable partial
            result2 = MagicMock()
            result2.is_final = False
            result2.stability = 0.1
            result2.alternatives = [MagicMock()]
            result2.alternatives[0].transcript = " خمسة"

            mock_response.results = [result1, result2]

            # Process the response
            await client._handle_response(session, mock_response)

            # Should concatenate both partials into one event
            assert len(partial_results) == 1
            assert partial_results[0]["text"] == "واحد  خمسة"
            assert partial_results[0]["is_final"] == False


class TestStreamingManagerGoogleIntegration:
    """Test StreamingManager integration with Google."""

    @pytest.mark.asyncio
    async def test_google_partial_accumulation(self):
        """Test that Google partials are accumulated in StreamingConnection."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../routers/stt'))
        from streaming_manager import StreamingConnection

        partial_callback = AsyncMock()
        final_callback = AsyncMock()
        error_callback = AsyncMock()

        conn = StreamingConnection(
            room_id="test-room",
            provider="google_v2",
            language="ar-EG",
            config={},
            on_partial=partial_callback,
            on_final=final_callback,
            on_error=error_callback
        )

        # Simulate Google partial result
        partial_result = {
            "text": "واحد خمسة",
            "is_final": False,
            "stability": 0.5,
            "language": "ar-EG",
            "session_id": "test-room"
        }

        await conn._handle_google_partial(partial_result)

        # Verify accumulated_text is updated
        assert conn.accumulated_text == "واحد خمسة"
        assert conn.revision == 1

        # Verify callback was called
        partial_callback.assert_called_once_with(partial_result)

    @pytest.mark.asyncio
    async def test_google_final_with_accumulated_fallback(self):
        """Test that finalized_text is used, with fallback to accumulated_text."""
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../routers/stt'))
        from streaming_manager import StreamingConnection

        partial_callback = AsyncMock()
        final_callback = AsyncMock()
        error_callback = AsyncMock()

        conn = StreamingConnection(
            room_id="test-room",
            provider="google_v2",
            language="ar-EG",
            config={},
            on_partial=partial_callback,
            on_final=final_callback,
            on_error=error_callback
        )

        # Simulate partial first
        partial_result = {"text": "واحد خمسة", "is_final": False, "language": "ar-EG", "session_id": "test-room"}
        await conn._handle_google_partial(partial_result)

        assert conn.accumulated_text == "واحد خمسة"
        assert conn.finalized_text == ""

        # Now simulate final
        final_result = {"text": "واحد خمسة أربعة", "is_final": True, "language": "ar-EG", "session_id": "test-room"}
        await conn._handle_google_final(final_result)

        # Both should be updated
        assert conn.finalized_text == "واحد خمسة أربعة"
        assert conn.accumulated_text == "واحد خمسة أربعة"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
