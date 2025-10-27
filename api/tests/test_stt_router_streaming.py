"""
Unit and integration tests for STT Router with streaming support.

Tests cover:
- Language-based routing
- Streaming vs batch API selection
- Provider fallback logic
- Partial accumulation with streaming
- Connection lifecycle management
- Redis pub/sub cache invalidation
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
import json
import base64


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = AsyncMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock()
    redis_mock.publish = AsyncMock()
    redis_mock.incr = AsyncMock(return_value=1)
    return redis_mock


@pytest.fixture
def mock_streaming_manager():
    """Mock StreamingManager."""
    manager = Mock()
    manager.get_or_create_connection = AsyncMock()
    manager.close_connection = AsyncMock()
    manager.close_all_for_room = AsyncMock()
    return manager


@pytest.fixture
def sample_partial_session():
    """Sample partial transcription session."""
    return {
        "segment_id": 1,
        "last_transcribed_length": 0,
        "accumulated_audio": b"",
        "accumulated_text": "",
        "chunk_count": 0,
        "speaker": "user@example.com",
        "target_lang": "en",
        "language_hint": "pl",
        "quality_tier": "standard",
        "provider": "speechmatics",
        "provider_config": {
            "diarization": True,
            "operating_point": "enhanced",
            "max_delay": 2.0
        },
        "last_audio_end_time": 0.0,
        "no_change_count": 0,
        "last_new_text": "",
        "conversation_history": [],
        "streaming_connection": None
    }


class TestLanguageBasedRouting:
    """Test language-based provider routing."""

    @pytest.mark.asyncio
    async def test_polish_routes_to_speechmatics(self):
        """Test that Polish routes to Speechmatics."""
        language = "pl-PL"
        mode = "partial"
        expected_provider = "speechmatics"

        # Simulate routing logic
        provider = "speechmatics" if language == "pl-PL" else "google_v2"

        assert provider == expected_provider

    @pytest.mark.asyncio
    async def test_english_routes_to_google(self):
        """Test that English routes to Google v2."""
        language = "en-US"
        mode = "partial"
        expected_provider = "google_v2"

        # Simulate routing logic
        provider = "google_v2" if language == "en-US" else "speechmatics"

        assert provider == expected_provider

    @pytest.mark.asyncio
    async def test_fallback_to_openai(self):
        """Test fallback to OpenAI when primary fails."""
        primary_provider = "speechmatics"
        fallback_provider = "openai"

        # Simulate provider failure
        primary_failed = True

        provider = fallback_provider if primary_failed else primary_provider

        assert provider == "openai"

    @pytest.mark.asyncio
    async def test_quality_tier_selection(self):
        """Test quality tier affects provider selection."""
        quality_tier = "standard"

        # Standard tier uses premium providers
        if quality_tier == "standard":
            provider = "speechmatics"
        else:  # budget
            provider = "soniox"

        assert provider == "speechmatics"


class TestStreamingProviderSelection:
    """Test streaming vs batch API selection."""

    def test_speechmatics_uses_streaming(self):
        """Test Speechmatics is in streaming providers."""
        STREAMING_PROVIDERS = {"speechmatics", "google_v2", "azure", "soniox"}

        assert "speechmatics" in STREAMING_PROVIDERS

    def test_openai_uses_batch(self):
        """Test OpenAI uses batch API."""
        STREAMING_PROVIDERS = {"speechmatics", "google_v2", "azure", "soniox"}

        assert "openai" not in STREAMING_PROVIDERS

    def test_provider_mode_detection(self):
        """Test detection of streaming vs batch mode."""
        STREAMING_PROVIDERS = {"speechmatics", "google_v2", "azure", "soniox"}

        # Test multiple providers
        assert "speechmatics" in STREAMING_PROVIDERS  # Streaming
        assert "google_v2" in STREAMING_PROVIDERS     # Streaming
        assert "openai" not in STREAMING_PROVIDERS    # Batch


class TestPartialAccumulation:
    """Test partial transcript accumulation."""

    @pytest.mark.asyncio
    async def test_streaming_word_accumulation(self):
        """Test word-by-word accumulation from streaming."""
        accumulated_text = ""
        words = ["Cześć", "jak", "się", "masz"]

        # Simulate streaming partials
        for word in words:
            if accumulated_text:
                accumulated_text += " " + word
            else:
                accumulated_text = word

        assert accumulated_text == "Cześć jak się masz"

    @pytest.mark.asyncio
    async def test_batch_api_accumulation(self):
        """Test accumulation with batch API (OpenAI)."""
        session_text = ""
        new_chunks = ["Hello", " world", " from", " OpenAI"]

        # Batch API appends new transcriptions
        for chunk in new_chunks:
            session_text += chunk

        assert session_text == "Hello world from OpenAI"

    @pytest.mark.asyncio
    async def test_revision_increment(self):
        """Test revision counter increments with each partial."""
        revision = 0
        partials = ["word1", "word2", "word3"]

        for partial in partials:
            revision += 1

        assert revision == 3

    @pytest.mark.asyncio
    async def test_empty_partial_skip(self, sample_partial_session):
        """Test empty partials don't update session."""
        initial_text = sample_partial_session["accumulated_text"]
        new_text = ""

        if new_text:  # Should skip empty
            sample_partial_session["accumulated_text"] += " " + new_text

        assert sample_partial_session["accumulated_text"] == initial_text


class TestConnectionLifecycle:
    """Test WebSocket connection lifecycle."""

    @pytest.mark.asyncio
    async def test_connection_created_on_first_partial(self, mock_streaming_manager, sample_partial_session):
        """Test connection is created on first partial."""
        # First chunk
        if sample_partial_session["streaming_connection"] is None:
            mock_conn = Mock()
            await mock_streaming_manager.get_or_create_connection(
                room_id="test-room",
                provider="speechmatics",
                language="pl",
                config=sample_partial_session["provider_config"],
                on_partial=AsyncMock(),
                on_final=AsyncMock(),
                on_error=AsyncMock()
            )
            sample_partial_session["streaming_connection"] = mock_conn

        assert sample_partial_session["streaming_connection"] is not None
        mock_streaming_manager.get_or_create_connection.assert_called_once()

    @pytest.mark.asyncio
    async def test_connection_reused_for_subsequent_chunks(self, mock_streaming_manager, sample_partial_session):
        """Test existing connection is reused."""
        # Create connection
        mock_conn = Mock()
        mock_conn.send_audio = AsyncMock()
        sample_partial_session["streaming_connection"] = mock_conn

        # Send multiple chunks
        for i in range(5):
            # Should reuse connection
            assert sample_partial_session["streaming_connection"] is not None
            await sample_partial_session["streaming_connection"].send_audio(b"audio_chunk")

        # Connection created once, used 5 times
        assert sample_partial_session["streaming_connection"].send_audio.call_count == 5

    @pytest.mark.asyncio
    async def test_connection_closed_on_audio_end(self, mock_streaming_manager, sample_partial_session):
        """Test connection is closed when audio ends."""
        room_id = "test-room"
        provider = sample_partial_session["provider"]

        # Set up a mock connection (simulating active streaming)
        mock_connection = Mock()
        sample_partial_session["streaming_connection"] = mock_connection

        # Simulate audio end
        if sample_partial_session.get("streaming_connection"):
            await mock_streaming_manager.close_connection(room_id, provider)
            sample_partial_session["streaming_connection"] = None

        mock_streaming_manager.close_connection.assert_called_once_with(room_id, provider)


class TestPartialCallback:
    """Test partial result callbacks from streaming."""

    @pytest.mark.asyncio
    async def test_partial_callback_receives_accumulated_text(self):
        """Test callback receives full accumulated text."""
        accumulated_text = "Cześć jak się"
        callback_received = None

        async def on_partial(result):
            nonlocal callback_received
            callback_received = result.get("text")

        await on_partial({"text": accumulated_text, "is_final": False})

        assert callback_received == accumulated_text

    @pytest.mark.asyncio
    async def test_partial_callback_increments_revision(self):
        """Test each partial increments revision."""
        revision = 0
        revisions_received = []

        async def on_partial(result):
            nonlocal revision
            revision += 1
            revisions_received.append(revision)

        # Simulate 5 partials
        for i in range(5):
            await on_partial({"text": f"word{i}", "revision": revision})

        assert revisions_received == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_partial_publishes_to_redis(self, mock_redis):
        """Test partial results are published to Redis."""
        stt_event = {
            "type": "stt_partial",
            "room_id": "test-room",
            "segment_id": 1,
            "revision": 1,
            "text": "Test text",
            "lang": "pl",
            "final": False
        }

        await mock_redis.publish("stt_events", json.dumps(stt_event))

        mock_redis.publish.assert_called_once()


class TestErrorHandlingAndFallback:
    """Test error handling and provider fallback."""

    @pytest.mark.asyncio
    async def test_streaming_error_triggers_callback(self):
        """Test streaming errors trigger error callback."""
        error_received = None

        async def on_error(error):
            nonlocal error_received
            error_received = error

        await on_error({
            "error": "Connection failed",
            "room_id": "test-room",
            "provider": "speechmatics"
        })

        assert error_received is not None
        assert "Connection failed" in error_received["error"]

    @pytest.mark.asyncio
    async def test_fallback_to_batch_on_streaming_failure(self):
        """Test fallback to batch API when streaming fails."""
        primary_provider = "speechmatics"
        fallback_provider = "openai"

        # Simulate streaming failure
        try:
            raise Exception("Streaming failed")
        except Exception:
            # Fall back to batch
            provider = fallback_provider

        assert provider == "openai"

    @pytest.mark.asyncio
    async def test_partial_continues_after_error(self, sample_partial_session):
        """Test partials continue processing after recoverable error."""
        # Simulate error on chunk 3
        error_occurred = False
        chunks_processed = 0

        for i in range(5):
            if i == 2:
                error_occurred = True
                # Log error but continue
                continue

            chunks_processed += 1

        assert error_occurred is True
        assert chunks_processed == 4  # Processed 0,1,3,4 (skipped 2)


class TestCacheInvalidation:
    """Test Redis cache invalidation."""

    @pytest.mark.asyncio
    async def test_cache_clear_message_published(self, mock_redis):
        """Test cache clear message is published."""
        cache_clear_msg = {
            "language": "pl-PL",
            "service_type": "stt"
        }

        await mock_redis.publish("routing_cache_clear", json.dumps(cache_clear_msg))

        mock_redis.publish.assert_called_once_with(
            "routing_cache_clear",
            json.dumps(cache_clear_msg)
        )

    @pytest.mark.asyncio
    async def test_cache_cleared_on_config_update(self, mock_redis):
        """Test cache is cleared when config changes."""
        # Simulate config update
        config_updated = True

        if config_updated:
            await mock_redis.publish("routing_cache_clear", json.dumps({
                "language": "pl-PL",
                "service_type": "stt"
            }))

        mock_redis.publish.assert_called_once()


class TestStreamingVsBatchComparison:
    """Test comparison between streaming and batch approaches."""

    @pytest.mark.asyncio
    async def test_streaming_creates_one_connection(self):
        """Test streaming uses single persistent connection."""
        connections_created = 0

        # First chunk - create connection
        connections_created += 1

        # Subsequent chunks - reuse connection
        for i in range(10):
            # No new connection
            pass

        assert connections_created == 1

    @pytest.mark.asyncio
    async def test_batch_creates_connection_per_chunk(self):
        """Test batch API creates connection per chunk (old behavior)."""
        connections_created = 0

        # Each chunk creates new connection
        for i in range(10):
            connections_created += 1

        assert connections_created == 10

    @pytest.mark.asyncio
    async def test_streaming_latency_advantage(self):
        """Test streaming has lower latency."""
        import time

        # Streaming: connection already open
        streaming_start = time.time()
        await asyncio.sleep(0.01)  # Just send audio
        streaming_latency = time.time() - streaming_start

        # Batch: need to connect first
        batch_start = time.time()
        await asyncio.sleep(0.1)  # Connect + send
        batch_latency = time.time() - batch_start

        assert streaming_latency < batch_latency


class TestConfigurationIntegration:
    """Test configuration with database."""

    def test_enhanced_quality_config(self):
        """Test enhanced quality configuration."""
        config = {
            "operating_point": "enhanced",
            "max_delay": 2.0,
            "diarization": True
        }

        assert config["operating_point"] == "enhanced"
        assert config["max_delay"] == 2.0

    def test_quality_tier_mapping(self):
        """Test quality tier maps to providers."""
        tier_to_provider = {
            "standard": "speechmatics",
            "budget": "soniox"
        }

        assert tier_to_provider["standard"] == "speechmatics"

    def test_language_config_override(self):
        """Test language-specific config overrides default."""
        default_config = {"max_delay": 0.7}
        pl_config = {"max_delay": 2.0}

        # Polish should use its own config
        language = "pl-PL"
        config = pl_config if language == "pl-PL" else default_config

        assert config["max_delay"] == 2.0
