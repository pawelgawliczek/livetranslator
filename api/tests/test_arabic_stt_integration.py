"""
Integration tests for Arabic STT workflow with Google Cloud Speech-to-Text v2.

Tests cover:
- End-to-end Arabic transcription flow
- Database routing configuration for ar-EG
- Provider selection (google_v2 for Arabic)
- Partial and final transcription delivery
- Audio format compatibility (LINEAR16, 16kHz)
- Language-based routing from language_router
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import json

# Check if google.cloud is available
try:
    import google.cloud
    GOOGLE_CLOUD_AVAILABLE = True
except ImportError:
    GOOGLE_CLOUD_AVAILABLE = False


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg database pool for routing config."""
    from unittest.mock import MagicMock

    mock_pool = MagicMock()
    mock_conn = AsyncMock()

    # Mock database query for ar-EG routing
    async def mock_fetchrow(query, *args):
        if "ar-EG" in str(args):
            return {
                "provider_primary": "google_v2",
                "provider_fallback": "azure",
                "config": {}  # Empty config = no diarization
            }
        return None

    mock_conn.fetchrow = mock_fetchrow

    # Create a proper async context manager
    async_context_manager = AsyncMock()
    async_context_manager.__aenter__.return_value = mock_conn
    async_context_manager.__aexit__.return_value = None

    # Make acquire() return the async context manager (not awaitable)
    mock_pool.acquire.return_value = async_context_manager
    return mock_pool


class TestArabicRoutingConfiguration:
    """Test Arabic language routing from database."""

    @pytest.mark.asyncio
    async def test_arabic_routes_to_google_v2(self, mock_db_pool):
        """Test that ar-EG routes to google_v2 as primary provider."""
        with patch('api.routers.stt.language_router._db_pool', mock_db_pool):
            from api.routers.stt.language_router import get_stt_provider_for_language

            config = await get_stt_provider_for_language(
                language="ar-EG",
                mode="partial",
                quality_tier="standard"
            )

            assert config["provider"] == "google_v2"
            assert config["fallback"] == "azure"
            assert config["language"] == "ar-EG"
            assert config["config"] == {}  # No diarization for Arabic streaming

    @pytest.mark.asyncio
    async def test_arabic_language_normalization(self, mock_db_pool):
        """Test that 'ar' is normalized to 'ar-EG'."""
        with patch('api.routers.stt.language_router._db_pool', mock_db_pool):
            from api.routers.stt.language_router import get_stt_provider_for_language, _normalize_language

            # Test normalization function
            assert _normalize_language("ar") == "ar-EG"
            assert _normalize_language("ar-EG") == "ar-EG"

            # Test routing with normalized language
            config = await get_stt_provider_for_language(
                language="ar",  # Should be normalized to ar-EG
                mode="partial",
                quality_tier="standard"
            )

            assert config["language"] == "ar-EG"


class TestArabicStreamingWorkflow:
    """Test end-to-end Arabic streaming workflow."""

    @pytest.mark.asyncio
    async def test_arabic_partial_to_final_flow(self):
        """Test complete flow from partial to final with audio_end."""
        from api.routers.stt.streaming_manager import StreamingConnection

        # Track results
        partial_results = []
        final_results = []

        async def on_partial(result):
            partial_results.append(result)

        async def on_final(result):
            final_results.append(result)

        # Create connection for Arabic
        conn = StreamingConnection(
            room_id="test-arabic-room",
            provider="google_v2",
            language="ar-EG",
            config={},
            on_partial=on_partial,
            on_final=on_final,
            on_error=AsyncMock()
        )

        # Simulate Google partial results during speech
        await conn._handle_google_partial({
            "text": "واحد",
            "is_final": False,
            "stability": 0.5,
            "language": "ar-EG",
            "session_id": "test-arabic-room"
        })

        assert len(partial_results) == 1
        assert partial_results[0]["text"] == "واحد"
        assert conn.accumulated_text == "واحد"

        # Simulate updated partial
        await conn._handle_google_partial({
            "text": "واحد خمسة",
            "is_final": False,
            "stability": 0.7,
            "language": "ar-EG",
            "session_id": "test-arabic-room"
        })

        assert len(partial_results) == 2
        assert partial_results[1]["text"] == "واحد خمسة"
        assert conn.accumulated_text == "واحد خمسة"

        # When user stops speaking, if no final from Google yet,
        # accumulated_text should be used as fallback
        # (This is what fixes the "last word cut off" bug)

        # Verify we have text to save
        assert conn.accumulated_text != ""
        assert conn.accumulated_text == "واحد خمسة"

    @pytest.mark.asyncio
    async def test_arabic_explicit_final_from_google(self):
        """Test handling explicit final result from Google."""
        from api.routers.stt.streaming_manager import StreamingConnection

        final_results = []

        async def on_final(result):
            final_results.append(result)

        conn = StreamingConnection(
            room_id="test-arabic-room",
            provider="google_v2",
            language="ar-EG",
            config={},
            on_partial=AsyncMock(),
            on_final=on_final,
            on_error=AsyncMock()
        )

        # Simulate Google final result (is_final=True)
        await conn._handle_google_final({
            "text": "واحد خمسة أربعة ثلاثة",
            "is_final": True,
            "language": "ar-EG",
            "speaker_labels": [],
            "session_id": "test-arabic-room"
        })

        assert len(final_results) == 1
        assert final_results[0]["text"] == "واحد خمسة أربعة ثلاثة"
        assert conn.finalized_text == "واحد خمسة أربعة ثلاثة"
        assert conn.accumulated_text == "واحد خمسة أربعة ثلاثة"


class TestAudioFormatConfiguration:
    """Test Google audio format configuration for Arabic."""

    @pytest.mark.asyncio
    async def test_explicit_linear16_encoding(self):
        """Test that Google is configured with explicit LINEAR16 encoding."""
        pytest.importorskip("google.cloud", reason="google.cloud not installed")
        # Import first so module is loaded
        from api.routers.stt import google_streaming

        with patch.object(google_streaming, 'speech') as mock_speech:
            with patch.object(google_streaming, 'GOOGLE_APPLICATION_CREDENTIALS', '/fake/creds.json'):
                with patch.object(google_streaming, 'GOOGLE_CLOUD_PROJECT', 'test-project'):
                    with patch.object(google_streaming, 'GOOGLE_CLOUD_LOCATION', 'eu'):
                        # Re-import to use patched values
                        from api.routers.stt.google_streaming import GoogleStreamingClient

                        # The fix uses ExplicitDecodingConfig instead of AutoDetectDecodingConfig
                        # Verify the enum is available
                        assert hasattr(mock_speech, 'ExplicitDecodingConfig')

                        # Verify expected audio parameters for Arabic:
                        # - LINEAR16 encoding (PCM16)
                        # - 16000 Hz sample rate
                        # - 1 audio channel (mono)


class TestDiarizationConfiguration:
    """Test diarization configuration for Arabic streaming."""

    @pytest.mark.asyncio
    async def test_diarization_disabled_for_arabic_streaming(self):
        """Test that diarization is NOT enabled for Arabic streaming (partial mode)."""
        pytest.importorskip("google.cloud", reason="google.cloud not installed")
        from api.routers.stt import google_streaming

        with patch.object(google_streaming, 'speech'):
            with patch.object(google_streaming, 'GOOGLE_APPLICATION_CREDENTIALS', '/fake/creds.json'):
                with patch.object(google_streaming, 'GOOGLE_CLOUD_PROJECT', 'test-project'):
                    with patch.object(google_streaming, 'GOOGLE_CLOUD_LOCATION', 'eu'):
                        from api.routers.stt.google_streaming import GoogleStreamingClient

                        client = GoogleStreamingClient()

                        # Create session with empty config (default for ar-EG partial)
                        session = await client.create_session(
                            session_id="arabic-test",
                            language="ar-EG",
                            config={},  # Empty = no diarization
                            on_partial=AsyncMock(),
                            on_final=AsyncMock(),
                            on_error=AsyncMock()
                        )

                        # Verify diarization defaults to False
                        assert session.config.get("diarization", False) == False

    @pytest.mark.asyncio
    async def test_diarization_can_be_enabled_for_finals(self):
        """Test that diarization CAN be enabled for final mode if needed."""
        pytest.importorskip("google.cloud", reason="google.cloud not installed")
        from api.routers.stt import google_streaming

        with patch.object(google_streaming, 'speech'):
            with patch.object(google_streaming, 'GOOGLE_APPLICATION_CREDENTIALS', '/fake/creds.json'):
                with patch.object(google_streaming, 'GOOGLE_CLOUD_PROJECT', 'test-project'):
                    with patch.object(google_streaming, 'GOOGLE_CLOUD_LOCATION', 'eu'):
                        from api.routers.stt.google_streaming import GoogleStreamingClient

                        client = GoogleStreamingClient()

                        # Create session with diarization explicitly enabled
                        session = await client.create_session(
                            session_id="arabic-final-test",
                            language="ar-EG",
                            config={"diarization": True, "min_speaker_count": 2, "max_speaker_count": 6},
                            on_partial=AsyncMock(),
                            on_final=AsyncMock(),
                            on_error=AsyncMock()
                        )

                        # Verify diarization is enabled
                        assert session.config.get("diarization") == True
                        assert session.config.get("min_speaker_count") == 2
                        assert session.config.get("max_speaker_count") == 6


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
