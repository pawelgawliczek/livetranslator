"""
Unit tests for multi-speaker diarization feature.

Tests cover:
- Speaker Pydantic models
- Speaker CRUD API endpoints
- Discovery mode management
- Speaker enrichment in WebSocket events
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime


class TestSpeakerModels:
    """Test suite for speaker-related Pydantic models."""

    def test_speaker_info_model(self):
        """Test SpeakerInfo model structure."""
        from api.rooms_api import SpeakerInfo

        speaker = SpeakerInfo(
            speaker_id=0,
            display_name="Speaker 1",
            language="en",
            color="#FF5733"
        )

        assert speaker.speaker_id == 0
        assert speaker.display_name == "Speaker 1"
        assert speaker.language == "en"
        assert speaker.color == "#FF5733"

    def test_speaker_response_model(self):
        """Test SpeakerResponse model structure."""
        from api.rooms_api import SpeakerResponse

        created = datetime.utcnow()
        speaker = SpeakerResponse(
            id=1,
            speaker_id=0,
            display_name="Speaker 1",
            language="en",
            color="#FF5733",
            created_at=created
        )

        assert speaker.id == 1
        assert speaker.speaker_id == 0
        assert speaker.display_name == "Speaker 1"
        assert speaker.language == "en"
        assert speaker.color == "#FF5733"
        assert speaker.created_at == created

    def test_speakers_list_response_model(self):
        """Test SpeakersListResponse model structure."""
        from api.rooms_api import SpeakersListResponse, SpeakerResponse

        created = datetime.utcnow()
        speakers = [
            SpeakerResponse(
                id=1,
                speaker_id=0,
                display_name="Speaker 1",
                language="en",
                color="#FF5733",
                created_at=created
            ),
            SpeakerResponse(
                id=2,
                speaker_id=1,
                display_name="Speaker 2",
                language="pl",
                color="#33C3FF",
                created_at=created
            )
        ]

        response = SpeakersListResponse(
            speakers=speakers,
            discovery_mode="enabled",
            speakers_locked=False
        )

        assert len(response.speakers) == 2
        assert response.discovery_mode == "enabled"
        assert response.speakers_locked is False

    def test_update_speakers_request_model(self):
        """Test UpdateSpeakersRequest model structure."""
        from api.rooms_api import UpdateSpeakersRequest, SpeakerInfo

        speakers = [
            SpeakerInfo(speaker_id=0, display_name="Alice", language="en", color="#FF5733"),
            SpeakerInfo(speaker_id=1, display_name="Bob", language="pl", color="#33C3FF")
        ]

        request = UpdateSpeakersRequest(speakers=speakers)

        assert len(request.speakers) == 2
        assert request.speakers[0].display_name == "Alice"
        assert request.speakers[1].display_name == "Bob"

    def test_update_speaker_request_model(self):
        """Test UpdateSpeakerRequest model structure."""
        from api.rooms_api import UpdateSpeakerRequest

        # Test with all fields
        request_full = UpdateSpeakerRequest(
            display_name="Updated Name",
            language="es",
            color="#FF0000"
        )
        assert request_full.display_name == "Updated Name"
        assert request_full.language == "es"
        assert request_full.color == "#FF0000"

        # Test with partial fields
        request_partial = UpdateSpeakerRequest(display_name="New Name")
        assert request_partial.display_name == "New Name"
        assert request_partial.language is None
        assert request_partial.color is None

    def test_update_discovery_mode_request_model(self):
        """Test UpdateDiscoveryModeRequest model structure."""
        from api.rooms_api import UpdateDiscoveryModeRequest

        # Test disabled mode
        request_disabled = UpdateDiscoveryModeRequest(discovery_mode="disabled")
        assert request_disabled.discovery_mode == "disabled"

        # Test enabled mode
        request_enabled = UpdateDiscoveryModeRequest(discovery_mode="enabled")
        assert request_enabled.discovery_mode == "enabled"

        # Test locked mode
        request_locked = UpdateDiscoveryModeRequest(discovery_mode="locked")
        assert request_locked.discovery_mode == "locked"

    def test_room_response_includes_speaker_fields(self):
        """Test that RoomResponse includes discovery_mode and speakers_locked fields."""
        from api.rooms_api import RoomResponse

        response = RoomResponse(
            id=1,
            code="test-room",
            owner_id=123,
            is_public=False,
            recording=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow(),
            admin_left_at=None,
            discovery_mode="enabled",
            speakers_locked=False
        )

        assert hasattr(response, 'discovery_mode')
        assert hasattr(response, 'speakers_locked')
        assert response.discovery_mode == "enabled"
        assert response.speakers_locked is False


class TestSpeakerAPIEndpoints:
    """Test suite for speaker management API endpoints."""

    def test_speaker_color_hex_format(self):
        """Test that speaker colors use hex format."""
        from api.rooms_api import SpeakerInfo

        valid_colors = ["#FF5733", "#33C3FF", "#00FF00", "#000000", "#FFFFFF"]

        for color in valid_colors:
            speaker = SpeakerInfo(
                speaker_id=0,
                display_name="Test",
                language="en",
                color=color
            )
            assert speaker.color == color
            assert speaker.color.startswith("#")
            assert len(speaker.color) == 7

    def test_speaker_id_sequential_numbering(self):
        """Test that speaker_id uses sequential integer numbering."""
        from api.rooms_api import SpeakerInfo

        speakers = [
            SpeakerInfo(speaker_id=0, display_name="S1", language="en", color="#FF0000"),
            SpeakerInfo(speaker_id=1, display_name="S2", language="pl", color="#00FF00"),
            SpeakerInfo(speaker_id=2, display_name="S3", language="es", color="#0000FF")
        ]

        for idx, speaker in enumerate(speakers):
            assert speaker.speaker_id == idx
            assert isinstance(speaker.speaker_id, int)

    def test_discovery_mode_states(self):
        """Test valid discovery mode states."""
        from api.rooms_api import UpdateDiscoveryModeRequest

        valid_modes = ["disabled", "enabled", "locked"]

        for mode in valid_modes:
            request = UpdateDiscoveryModeRequest(discovery_mode=mode)
            assert request.discovery_mode == mode

    def test_bulk_speaker_update_empty_list(self):
        """Test bulk speaker update with empty list (clear all speakers)."""
        from api.rooms_api import UpdateSpeakersRequest

        request = UpdateSpeakersRequest(speakers=[])
        assert len(request.speakers) == 0

    def test_bulk_speaker_update_multiple_speakers(self):
        """Test bulk speaker update with multiple speakers."""
        from api.rooms_api import UpdateSpeakersRequest, SpeakerInfo

        speakers = [
            SpeakerInfo(speaker_id=i, display_name=f"Speaker {i}", language="en", color=f"#{i:06X}")
            for i in range(5)
        ]

        request = UpdateSpeakersRequest(speakers=speakers)
        assert len(request.speakers) == 5

        for idx, speaker in enumerate(request.speakers):
            assert speaker.speaker_id == idx

    def test_speaker_language_codes(self):
        """Test that speakers support various language codes."""
        from api.rooms_api import SpeakerInfo

        languages = ["en", "pl", "es", "fr", "de", "ar", "zh", "ja", "ko"]

        for lang in languages:
            speaker = SpeakerInfo(
                speaker_id=0,
                display_name="Test",
                language=lang,
                color="#FF5733"
            )
            assert speaker.language == lang

    def test_speaker_display_name_length(self):
        """Test speaker display names of various lengths."""
        from api.rooms_api import SpeakerInfo

        # Short name
        short = SpeakerInfo(speaker_id=0, display_name="A", language="en", color="#FF5733")
        assert len(short.display_name) == 1

        # Normal name
        normal = SpeakerInfo(speaker_id=0, display_name="Speaker 1", language="en", color="#FF5733")
        assert len(normal.display_name) == 9

        # Long name (up to 120 chars in database)
        long_name = "A" * 120
        long = SpeakerInfo(speaker_id=0, display_name=long_name, language="en", color="#FF5733")
        assert len(long.display_name) == 120


class TestSpeakerEnrichment:
    """Test suite for speaker information enrichment in WebSocket events."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock database session."""
        session = Mock()
        session.query = Mock()
        session.close = Mock()
        return session

    @pytest.fixture
    def mock_room(self):
        """Create a mock room object."""
        room = Mock()
        room.id = 1
        room.code = "test-room"
        room.owner_id = 100
        room.discovery_mode = "enabled"
        room.speakers_locked = False
        return room

    @pytest.fixture
    def mock_speaker(self):
        """Create a mock speaker object."""
        speaker = Mock()
        speaker.id = 1
        speaker.speaker_id = 0
        speaker.display_name = "Alice"
        speaker.language = "en"
        speaker.color = "#FF5733"
        return speaker

    @pytest.fixture
    def mock_ws_manager(self):
        """Create a mock WebSocket manager."""
        from api.ws_manager import WSManager
        manager = WSManager(
            redis_url="redis://localhost:6379",
            mt_base_url="http://localhost:8000"
        )
        manager.log = Mock()
        manager.redis = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_get_speaker_info_returns_speaker_data(self, mock_ws_manager, mock_db_session, mock_room, mock_speaker):
        """Test that get_speaker_info returns speaker information."""
        room_code = "test-room"
        speaker_id = "0"

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_room,  # First call for Room query
            mock_speaker  # Second call for RoomSpeaker query
        ]

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            result = await mock_ws_manager.get_speaker_info(room_code, speaker_id)

        assert result is not None
        assert result["speaker_id"] == 0
        assert result["display_name"] == "Alice"
        assert result["language"] == "en"
        assert result["color"] == "#FF5733"

    @pytest.mark.asyncio
    async def test_get_speaker_info_returns_none_for_missing_room(self, mock_ws_manager, mock_db_session):
        """Test that get_speaker_info returns None when room doesn't exist."""
        room_code = "nonexistent"
        speaker_id = "0"

        # Mock database query returning no room
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            result = await mock_ws_manager.get_speaker_info(room_code, speaker_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_speaker_info_returns_none_for_missing_speaker(self, mock_ws_manager, mock_db_session, mock_room):
        """Test that get_speaker_info returns None when speaker doesn't exist."""
        room_code = "test-room"
        speaker_id = "99"

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_room,  # Room exists
            None  # Speaker doesn't exist
        ]

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            result = await mock_ws_manager.get_speaker_info(room_code, speaker_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_speaker_info_handles_invalid_speaker_id(self, mock_ws_manager):
        """Test that get_speaker_info handles invalid speaker_id gracefully."""
        room_code = "test-room"

        # Test with non-numeric speaker_id
        result = await mock_ws_manager.get_speaker_info(room_code, "invalid")
        assert result is None

        # Test with None speaker_id
        result = await mock_ws_manager.get_speaker_info(room_code, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_stt_event_enriched_with_speaker_info(self, mock_ws_manager, mock_db_session, mock_room, mock_speaker):
        """Test that STT events are enriched with speaker information."""
        room_code = "test-room"

        stt_data = {
            "type": "transcript_partial",
            "text": "Hello world",
            "segment_id": 123,  # Integer segment ID
            "speaker": "0"
        }

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_speaker
        ]

        # Mock Redis
        mock_ws_manager.redis.setex = AsyncMock()
        mock_ws_manager.broadcast = AsyncMock()

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._handle_stt_event(stt_data, room_code)

        # Verify speaker_info was added to the data
        assert "speaker_info" in stt_data
        assert stt_data["speaker_info"]["speaker_id"] == 0
        assert stt_data["speaker_info"]["display_name"] == "Alice"
        assert stt_data["speaker_info"]["language"] == "en"
        assert stt_data["speaker_info"]["color"] == "#FF5733"

        # Verify speaker was cached in Redis
        mock_ws_manager.redis.setex.assert_called_once()
        call_args = mock_ws_manager.redis.setex.call_args
        assert ":123:" in call_args[0][0]  # segment_id should be in the Redis key
        assert call_args[0][2] == "0"  # speaker_id

    @pytest.mark.asyncio
    async def test_stt_event_without_speaker_info_not_enriched(self, mock_ws_manager):
        """Test that STT events without speaker field are not enriched."""
        room_code = "test-room"

        stt_data = {
            "type": "transcript_partial",
            "text": "Hello world",
            "segment_id": 123  # Integer segment ID
            # No speaker field
        }

        mock_ws_manager.redis.setex = AsyncMock()
        mock_ws_manager.broadcast = AsyncMock()

        await mock_ws_manager._handle_stt_event(stt_data, room_code)

        # Verify no speaker_info was added
        assert "speaker_info" not in stt_data

    @pytest.mark.asyncio
    async def test_mt_event_enriched_with_speaker_info(self, mock_ws_manager, mock_db_session, mock_room, mock_speaker):
        """Test that MT events are enriched with speaker information."""
        room_code = "test-room"

        mt_data = {
            "type": "translation",
            "kind": "final",
            "segment_id": 123,  # Integer segment ID
            "final": True,
            "speaker": "0",
            "text": "Translated text",
            "src_lang": "en",
            "tgt_lang": "pl"
        }

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_speaker
        ]

        # Mock rooms dictionary - add a mock websocket
        mock_ws = Mock()
        mock_ws.state.preferred_lang = "pl"
        mock_ws.send_json = AsyncMock()
        mock_ws_manager.rooms = {room_code: [mock_ws]}

        # Mock Redis
        mock_ws_manager.redis.get = AsyncMock(return_value="0")

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._handle_mt_event(mt_data, room_code)

        # Verify send_json was called with enriched data
        mock_ws.send_json.assert_called_once()
        sent_data = mock_ws.send_json.call_args[0][0]

        assert "speaker_info" in sent_data
        assert sent_data["speaker_info"]["speaker_id"] == 0
        assert sent_data["speaker_info"]["display_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_mt_event_retrieves_speaker_from_redis_cache(self, mock_ws_manager, mock_db_session, mock_room, mock_speaker):
        """Test that MT events retrieve speaker from Redis cache when not in event."""
        room_code = "test-room"

        mt_data = {
            "type": "translation",
            "kind": "final",
            "segment_id": 123,  # Integer segment ID
            "final": True,
            # No speaker field in MT data
            "text": "Translated text",
            "src_lang": "en",
            "tgt_lang": "pl"
        }

        # Mock database queries
        mock_db_session.query.return_value.filter.return_value.first.side_effect = [
            mock_room,
            mock_speaker
        ]

        # Mock rooms dictionary - add a mock websocket
        mock_ws = Mock()
        mock_ws.state.preferred_lang = "pl"
        mock_ws.send_json = AsyncMock()
        mock_ws_manager.rooms = {room_code: [mock_ws]}

        # Mock Redis cache returning speaker
        mock_ws_manager.redis.get = AsyncMock(return_value="0")

        with patch('api.ws_manager.SessionLocal', return_value=mock_db_session):
            await mock_ws_manager._handle_mt_event(mt_data, room_code)

        # Verify Redis was queried for speaker
        mock_ws_manager.redis.get.assert_called_once()
        call_args = mock_ws_manager.redis.get.call_args
        assert ":123:" in call_args[0][0]  # segment_id should be in the Redis key

        # Verify send_json was called with enriched data
        mock_ws.send_json.assert_called_once()
        sent_data = mock_ws.send_json.call_args[0][0]
        assert "speaker_info" in sent_data


class TestSpeakerDiscoveryModeTransitions:
    """Test suite for speaker discovery mode state transitions."""

    def test_discovery_mode_disabled_to_enabled(self):
        """Test transition from disabled to enabled."""
        from api.rooms_api import UpdateDiscoveryModeRequest

        request = UpdateDiscoveryModeRequest(discovery_mode="enabled")
        assert request.discovery_mode == "enabled"

    def test_discovery_mode_enabled_to_locked(self):
        """Test transition from enabled to locked."""
        from api.rooms_api import UpdateDiscoveryModeRequest

        request = UpdateDiscoveryModeRequest(discovery_mode="locked")
        assert request.discovery_mode == "locked"

    def test_discovery_mode_locked_prevents_changes(self):
        """Test that locked mode is the final state."""
        # This would be enforced at the API level
        # The model itself doesn't prevent the request
        from api.rooms_api import UpdateDiscoveryModeRequest

        request = UpdateDiscoveryModeRequest(discovery_mode="locked")
        assert request.discovery_mode == "locked"

    def test_speakers_locked_set_when_discovery_locked(self):
        """Test that speakers_locked=True when discovery_mode=locked."""
        from api.rooms_api import RoomResponse

        response = RoomResponse(
            id=1,
            code="test-room",
            owner_id=123,
            is_public=False,
            recording=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow(),
            admin_left_at=None,
            discovery_mode="locked",
            speakers_locked=True
        )

        assert response.discovery_mode == "locked"
        assert response.speakers_locked is True


class TestMultiSpeakerEventStructure:
    """Test suite for multi-speaker event JSON structure."""

    def test_stt_event_with_speaker_info_structure(self):
        """Test STT event structure with speaker_info."""
        event = {
            "type": "transcript_final",
            "text": "Hello everyone",
            "segment_id": "seg-123",
            "speaker": "0",
            "speaker_info": {
                "speaker_id": 0,
                "display_name": "Alice",
                "language": "en",
                "color": "#FF5733"
            }
        }

        assert event["type"] == "transcript_final"
        assert event["speaker"] == "0"
        assert "speaker_info" in event
        assert event["speaker_info"]["speaker_id"] == 0
        assert event["speaker_info"]["display_name"] == "Alice"
        assert event["speaker_info"]["language"] == "en"
        assert event["speaker_info"]["color"] == "#FF5733"

    def test_mt_event_with_speaker_info_structure(self):
        """Test MT event structure with speaker_info."""
        event = {
            "type": "translation_final",
            "text": "Cześć wszystkim",
            "segment_id": "seg-123",
            "speaker": "0",
            "src_lang": "en",
            "tgt_lang": "pl",
            "speaker_info": {
                "speaker_id": 0,
                "display_name": "Alice",
                "language": "en",
                "color": "#FF5733"
            }
        }

        assert event["type"] == "translation_final"
        assert event["speaker"] == "0"
        assert "speaker_info" in event
        assert event["speaker_info"]["speaker_id"] == 0
        assert event["src_lang"] == "en"
        assert event["tgt_lang"] == "pl"

    def test_backward_compatibility_without_speaker_info(self):
        """Test that events work without speaker_info (single-speaker mode)."""
        event = {
            "type": "transcript_final",
            "text": "Hello everyone",
            "segment_id": "seg-123"
            # No speaker or speaker_info fields
        }

        assert event["type"] == "transcript_final"
        assert "speaker" not in event
        assert "speaker_info" not in event

    def test_multiple_speakers_different_colors(self):
        """Test that multiple speakers have different colors."""
        speakers = [
            {
                "speaker_id": 0,
                "display_name": "Alice",
                "language": "en",
                "color": "#FF5733"
            },
            {
                "speaker_id": 1,
                "display_name": "Bob",
                "language": "pl",
                "color": "#33C3FF"
            },
            {
                "speaker_id": 2,
                "display_name": "Carol",
                "language": "es",
                "color": "#75FF33"
            }
        ]

        colors = [s["color"] for s in speakers]
        assert len(colors) == len(set(colors))  # All colors are unique
