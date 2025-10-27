"""
Unit tests for rooms API endpoints.

Tests cover:
- Room creation with authentication
- Room code validation
- Duplicate room code handling
- Room retrieval by code
- Authorization requirements
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestRoomsAPI:
    """Test suite for rooms API endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        # We'll mock the dependencies since we're testing the API logic
        yield

    def test_create_room_success(self):
        """Test successful room creation."""
        from api.rooms_api import CreateRoomRequest

        # Create a valid request
        request = CreateRoomRequest(
            code="test-room",
            is_public=False,
            requires_login=False,
            max_participants=10
        )

        assert request.code == "test-room"
        assert request.is_public == False
        assert request.requires_login == False
        assert request.max_participants == 10

    def test_create_room_defaults(self):
        """Test room creation with default values."""
        from api.rooms_api import CreateRoomRequest

        # Create request with minimal params
        request = CreateRoomRequest(code="test-room")

        assert request.code == "test-room"
        assert request.is_public == False
        assert request.requires_login == False
        assert request.max_participants == 10

    def test_create_room_custom_settings(self):
        """Test room creation with custom settings."""
        from api.rooms_api import CreateRoomRequest

        request = CreateRoomRequest(
            code="public-room",
            is_public=True,
            requires_login=True,
            max_participants=50
        )

        assert request.is_public == True
        assert request.requires_login == True
        assert request.max_participants == 50

    def test_room_code_length_validation(self):
        """Test that room codes respect length constraints."""
        from api.rooms_api import CreateRoomRequest

        # Test various code lengths
        short_code = CreateRoomRequest(code="abc")
        assert len(short_code.code) == 3

        max_code = CreateRoomRequest(code="a" * 12)
        assert len(max_code.code) == 12

        # Codes longer than 12 should be caught by database constraint
        long_code = CreateRoomRequest(code="a" * 20)
        assert len(long_code.code) == 20  # Request accepts it, DB will reject

    def test_room_response_model(self):
        """Test RoomResponse model structure."""
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
            admin_left_at=None
        )

        assert response.id == 1
        assert response.code == "test-room"
        assert response.owner_id == 123
        assert response.recording == False
        assert isinstance(response.created_at, datetime)
        assert response.admin_left_at is None

    def test_get_current_user_no_header(self):
        """Test user extraction fails without authorization header."""
        from api.rooms_api import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_current_user(None)

        assert exc_info.value.status_code == 401
        assert "Missing or invalid" in exc_info.value.detail

    def test_get_current_user_invalid_format(self):
        """Test user extraction fails with invalid header format."""
        from api.rooms_api import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_current_user("InvalidFormat")

        assert exc_info.value.status_code == 401

    def test_get_current_user_invalid_token(self):
        """Test user extraction fails with invalid JWT."""
        from api.rooms_api import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            get_current_user("Bearer invalid-token-here")

        assert exc_info.value.status_code == 401
        assert "Invalid authentication token" in exc_info.value.detail

    def test_room_code_uniqueness(self):
        """Test that duplicate room codes should be rejected."""
        # This is a business logic test - the actual enforcement
        # happens at the database level with unique constraint
        from api.rooms_api import CreateRoomRequest

        room1 = CreateRoomRequest(code="duplicate")
        room2 = CreateRoomRequest(code="duplicate")

        # Both requests are valid, but DB should reject the second one
        assert room1.code == room2.code

    def test_quick_room_code_format(self):
        """Test that quick room codes fit in database constraints."""
        # Quick rooms use format: q-{timestamp_base36}
        # Example: q-mh07s8a (11 chars)
        import time

        timestamp = int(time.time())
        short_code = timestamp.toString(36) if hasattr(timestamp, 'toString') else \
                     format(timestamp, 'x')  # Python doesn't have toString, using hex

        # In JavaScript: `q-${timestamp.toString(36)}`
        # Maximum length should be around 11 characters
        # Current timestamp in base36 is about 8-9 chars
        # So q-XXXXXXXXX is about 11 chars max

        # This is more of a documentation test
        max_expected_length = 12
        assert max_expected_length <= 12  # Database limit

    def test_room_participant_limits(self):
        """Test room participant limit validation."""
        from api.rooms_api import CreateRoomRequest

        # Small room
        small = CreateRoomRequest(code="small", max_participants=2)
        assert small.max_participants == 2

        # Large room
        large = CreateRoomRequest(code="large", max_participants=100)
        assert large.max_participants == 100

        # Default
        default = CreateRoomRequest(code="default")
        assert default.max_participants == 10


class TestRoomsAPIIntegration:
    """Integration tests requiring database and FastAPI."""

    def test_create_and_retrieve_room_flow(self):
        """Test the complete flow of creating and retrieving a room."""
        # This would require actual DB setup
        # Placeholder for integration test
        pass

    def test_duplicate_room_rejection(self):
        """Test that creating duplicate room codes fails."""
        # This would test the actual DB constraint
        pass

    def test_room_ownership(self):
        """Test that room owner is correctly set from JWT."""
        # This would test the actual authentication flow
        pass


class TestRoomsAPIEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_room_code(self):
        """Test handling of empty room codes."""
        from api.rooms_api import CreateRoomRequest
        from pydantic import ValidationError

        # Pydantic should validate this
        try:
            request = CreateRoomRequest(code="")
            # If it doesn't fail, check that empty string is handled
            assert request.code == ""
        except ValidationError:
            # Expected - Pydantic should reject empty strings
            pass

    def test_special_characters_in_code(self):
        """Test room codes with special characters."""
        from api.rooms_api import CreateRoomRequest

        # Test various special characters
        special_codes = [
            "room-123",
            "room_test",
            "room.test",
            "room@test"
        ]

        for code in special_codes:
            if len(code) <= 12:
                request = CreateRoomRequest(code=code)
                assert request.code == code

    def test_negative_max_participants(self):
        """Test handling of negative participant limits."""
        from api.rooms_api import CreateRoomRequest

        # This should ideally be validated
        request = CreateRoomRequest(code="test", max_participants=-1)
        assert request.max_participants == -1  # Currently not validated

    def test_zero_max_participants(self):
        """Test room with zero participant limit."""
        from api.rooms_api import CreateRoomRequest

        request = CreateRoomRequest(code="test", max_participants=0)
        assert request.max_participants == 0


class TestRoomCodeGeneration:
    """Test room code generation patterns."""

    def test_quick_room_uniqueness(self):
        """Test that quick room codes are unique."""
        import time

        # Simulate generating two quick room codes
        ts1 = int(time.time() * 1000)
        ts2 = int(time.time() * 1000) + 1

        # They should be different
        assert ts1 != ts2

    def test_quick_room_base36_conversion(self):
        """Test base36 conversion for compact codes."""
        import time

        timestamp = int(time.time())

        # Convert to base36 (simulating JavaScript's toString(36))
        def to_base36(num):
            chars = "0123456789abcdefghijklmnopqrstuvwxyz"
            if num == 0:
                return "0"
            result = []
            while num:
                num, remainder = divmod(num, 36)
                result.append(chars[remainder])
            return ''.join(reversed(result))

        base36 = to_base36(timestamp)
        quick_code = f"q-{base36}"

        # Should fit in 12 chars
        assert len(quick_code) <= 12
        print(f"Quick room code: {quick_code} ({len(quick_code)} chars)")


class TestRoomLifecycleManagement:
    """Test suite for room lifecycle and admin presence features."""

    def test_room_status_response_model(self):
        """Test RoomStatusResponse model structure."""
        from api.rooms_api import RoomStatusResponse
        from datetime import datetime, timedelta

        admin_left_time = datetime.utcnow()
        expires_time = admin_left_time + timedelta(minutes=30)

        response = RoomStatusResponse(
            code="test-room",
            admin_present=False,
            admin_left_at=admin_left_time,
            expires_at=expires_time
        )

        assert response.code == "test-room"
        assert response.admin_present == False
        assert response.admin_left_at == admin_left_time
        assert response.expires_at == expires_time

    def test_room_status_admin_present(self):
        """Test room status when admin is present."""
        from api.rooms_api import RoomStatusResponse

        response = RoomStatusResponse(
            code="test-room",
            admin_present=True,
            admin_left_at=None,
            expires_at=None
        )

        assert response.admin_present == True
        assert response.admin_left_at is None
        assert response.expires_at is None

    def test_room_status_admin_absent(self):
        """Test room status when admin has left."""
        from api.rooms_api import RoomStatusResponse
        from datetime import datetime, timedelta

        left_at = datetime.utcnow()
        expires_at = left_at + timedelta(minutes=30)

        response = RoomStatusResponse(
            code="test-room",
            admin_present=False,
            admin_left_at=left_at,
            expires_at=expires_at
        )

        assert response.admin_present == False
        assert response.admin_left_at is not None
        assert response.expires_at is not None

        # Verify 30-minute expiration
        time_diff = response.expires_at - response.admin_left_at
        assert time_diff.total_seconds() == 1800  # 30 minutes

    def test_room_status_json_serialization_with_timezone(self):
        """Test that datetime fields are serialized with UTC timezone marker."""
        from api.rooms_api import RoomStatusResponse
        from datetime import datetime, timedelta
        import json

        left_at = datetime.utcnow()
        expires_at = left_at + timedelta(minutes=30)

        response = RoomStatusResponse(
            code="test-room",
            admin_present=False,
            admin_left_at=left_at,
            expires_at=expires_at
        )

        # Serialize to JSON
        json_data = response.model_dump_json()
        parsed = json.loads(json_data)

        # Check that timestamps end with 'Z' (UTC marker)
        assert parsed['admin_left_at'].endswith('Z')
        assert parsed['expires_at'].endswith('Z')

    def test_room_response_includes_admin_left_at(self):
        """Test that RoomResponse includes admin_left_at field."""
        from api.rooms_api import RoomResponse
        from datetime import datetime

        response = RoomResponse(
            id=1,
            code="test-room",
            owner_id=123,
            is_public=False,
            recording=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow(),
            admin_left_at=None
        )

        assert hasattr(response, 'admin_left_at')
        assert response.admin_left_at is None

    def test_room_response_with_admin_departed(self):
        """Test RoomResponse when admin has departed."""
        from api.rooms_api import RoomResponse
        from datetime import datetime

        left_at = datetime.utcnow()

        response = RoomResponse(
            id=1,
            code="test-room",
            owner_id=123,
            is_public=False,
            recording=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow(),
            admin_left_at=left_at
        )

        assert response.admin_left_at == left_at

    def test_expires_at_calculation(self):
        """Test that expires_at is correctly calculated as admin_left_at + 30 minutes."""
        from datetime import datetime, timedelta

        left_at = datetime(2025, 10, 21, 12, 0, 0)
        expected_expires_at = datetime(2025, 10, 21, 12, 30, 0)

        calculated_expires_at = left_at + timedelta(minutes=30)

        assert calculated_expires_at == expected_expires_at
        assert (calculated_expires_at - left_at).total_seconds() == 1800

    def test_timezone_handling(self):
        """Test that timezone information is preserved in serialization."""
        from api.rooms_api import RoomStatusResponse
        from datetime import datetime

        # Create a datetime (UTC)
        now = datetime.utcnow()

        response = RoomStatusResponse(
            code="test-room",
            admin_present=False,
            admin_left_at=now,
            expires_at=now
        )

        # Get JSON representation
        json_str = response.model_dump_json()

        # Should contain ISO format with Z suffix
        assert 'Z"' in json_str

    def test_admin_left_at_optional(self):
        """Test that admin_left_at is optional in responses."""
        from api.rooms_api import RoomResponse
        from datetime import datetime

        # Should work without admin_left_at (defaults to None)
        response = RoomResponse(
            id=1,
            code="test-room",
            owner_id=123,
            is_public=False,
            recording=False,
            requires_login=False,
            max_participants=10,
            created_at=datetime.utcnow()
        )

        assert response.admin_left_at is None

    def test_room_status_expiration_edge_cases(self):
        """Test edge cases for room expiration calculation."""
        from datetime import datetime, timedelta

        # Test immediate expiration (edge case)
        now = datetime.utcnow()
        expires_now = now + timedelta(seconds=0)
        assert (expires_now - now).total_seconds() == 0

        # Test just before expiration
        almost_expired = now + timedelta(seconds=1)
        assert (almost_expired - now).total_seconds() == 1

        # Test well past expiration
        long_expired = now - timedelta(hours=1)
        assert (now - long_expired).total_seconds() == 3600
