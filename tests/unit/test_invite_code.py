"""
Unit tests for api/utils/invite_code.py

Tests invite code generation and verification:
- generate_invite_code() - Create time-limited room invites (30 min validity)
- verify_invite_code() - Validate and decode invite codes
- get_room_code_from_invite() - Extract room code from invite

Key features tested:
- JWT-based time-limited invites
- 30-minute expiration
- Tampering detection
- Type validation (only 'invite' type tokens)
"""

import pytest
import jwt
import time
from unittest.mock import patch

# Import the module under test
from api.utils import invite_code


@pytest.mark.unit
class TestGenerateInviteCode:
    """Tests for generate_invite_code() function."""

    def test_generate_invite_code_returns_jwt_token(self, mock_jwt_secret, room_code):
        """Test that generated invite code is a valid JWT token."""
        code = invite_code.generate_invite_code(room_code)

        assert code is not None
        assert isinstance(code, str)
        assert len(code) > 20  # JWT tokens are long
        assert "." in code  # JWT format: header.payload.signature

    def test_generate_invite_code_contains_room_code(self, mock_jwt_secret, room_code):
        """Test that invite code contains the room code."""
        code = invite_code.generate_invite_code(room_code)

        # Decode without verification to inspect payload
        payload = jwt.decode(code, options={"verify_signature": False})

        assert payload["room_code"] == room_code

    def test_generate_invite_code_has_invite_type(self, mock_jwt_secret, room_code):
        """Test that invite code has type='invite'."""
        code = invite_code.generate_invite_code(room_code)

        payload = jwt.decode(code, options={"verify_signature": False})

        assert payload["type"] == "invite"

    def test_generate_invite_code_has_expiration(self, mock_jwt_secret, room_code):
        """Test that invite code has expiration timestamp."""
        code = invite_code.generate_invite_code(room_code)

        payload = jwt.decode(code, options={"verify_signature": False})

        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]

    def test_generate_invite_code_expires_in_30_minutes(self, mock_jwt_secret, room_code):
        """Test that invite code expires in exactly 30 minutes."""
        code = invite_code.generate_invite_code(room_code)

        payload = jwt.decode(code, options={"verify_signature": False})

        expiration_time = payload["exp"] - payload["iat"]

        # Should be 30 minutes (1800 seconds)
        assert expiration_time == 1800

    def test_generate_invite_code_unique_per_call(self, mock_jwt_secret, room_code):
        """Test that each generated code is unique (different iat timestamp)."""
        code1 = invite_code.generate_invite_code(room_code)
        time.sleep(0.1)  # Small delay to ensure different timestamp
        code2 = invite_code.generate_invite_code(room_code)

        assert code1 != code2

    @pytest.mark.parametrize("room_code", [
        "room-123",
        "test-room-abc",
        "UPPERCASE-ROOM",
        "room_with_underscores",
        "room.with.dots",
        "very-long-room-code-with-many-characters-12345",
    ])
    def test_generate_invite_code_with_various_room_codes(self, mock_jwt_secret, room_code):
        """Test invite generation with various room code formats."""
        code = invite_code.generate_invite_code(room_code)

        payload = jwt.decode(code, options={"verify_signature": False})

        assert payload["room_code"] == room_code

    def test_generate_invite_code_is_verifiable(self, mock_jwt_secret, room_code):
        """Test that generated code can be verified with correct secret."""
        code = invite_code.generate_invite_code(room_code)

        # Should decode successfully with correct secret
        payload = jwt.decode(code, mock_jwt_secret, algorithms=["HS256"])

        assert payload["room_code"] == room_code


@pytest.mark.unit
class TestVerifyInviteCode:
    """Tests for verify_invite_code() function."""

    def test_verify_valid_invite_code(self, mock_jwt_secret, room_code):
        """Test that valid invite code is successfully verified."""
        code = invite_code.generate_invite_code(room_code)

        payload = invite_code.verify_invite_code(code)

        assert payload is not None
        assert payload["room_code"] == room_code
        assert payload["type"] == "invite"

    def test_verify_invite_code_returns_all_fields(self, mock_jwt_secret, room_code):
        """Test that verification returns all payload fields."""
        code = invite_code.generate_invite_code(room_code)

        payload = invite_code.verify_invite_code(code)

        assert "room_code" in payload
        assert "type" in payload
        assert "iat" in payload
        assert "exp" in payload

    def test_verify_expired_invite_code_returns_none(self, mock_jwt_secret, room_code):
        """Test that expired invite code returns None."""
        # Create an invite code that expired 1 hour ago
        past_time = int(time.time()) - 3600
        expired_payload = {
            "room_code": room_code,
            "type": "invite",
            "iat": past_time - 1800,
            "exp": past_time,  # Expired
        }

        expired_code = jwt.encode(expired_payload, mock_jwt_secret, algorithm="HS256")

        result = invite_code.verify_invite_code(expired_code)

        assert result is None

    def test_verify_invite_code_with_wrong_signature_returns_none(self, mock_jwt_secret, room_code):
        """Test that invite code with wrong signature returns None."""
        # Generate code with different secret
        wrong_secret = "wrong-secret-key"
        payload = {
            "room_code": room_code,
            "type": "invite",
            "iat": int(time.time()),
            "exp": int(time.time()) + 1800,
        }

        tampered_code = jwt.encode(payload, wrong_secret, algorithm="HS256")

        result = invite_code.verify_invite_code(tampered_code)

        assert result is None

    def test_verify_invite_code_with_wrong_type_returns_none(self, mock_jwt_secret, room_code):
        """Test that token with type != 'invite' returns None."""
        # Create a token with wrong type
        payload = {
            "room_code": room_code,
            "type": "access",  # Wrong type
            "iat": int(time.time()),
            "exp": int(time.time()) + 1800,
        }

        wrong_type_code = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")

        result = invite_code.verify_invite_code(wrong_type_code)

        assert result is None

    def test_verify_invalid_invite_code_returns_none(self, mock_jwt_secret):
        """Test that invalid/malformed invite code returns None."""
        invalid_codes = [
            "not-a-jwt-token",
            "invalid.format.here",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
            "",
            None,
        ]

        for invalid_code in invalid_codes:
            result = invite_code.verify_invite_code(invalid_code)
            assert result is None

    def test_verify_invite_code_catches_all_exceptions(self, mock_jwt_secret):
        """Test that any exception during verification returns None (graceful failure)."""
        # Trigger various exceptions
        result1 = invite_code.verify_invite_code("malformed-token")
        result2 = invite_code.verify_invite_code("")
        result3 = invite_code.verify_invite_code(None)

        assert result1 is None
        assert result2 is None
        assert result3 is None

    def test_verify_invite_code_with_missing_room_code(self, mock_jwt_secret):
        """Test verification when room_code field is missing."""
        payload = {
            # Missing room_code
            "type": "invite",
            "iat": int(time.time()),
            "exp": int(time.time()) + 1800,
        }

        code = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")

        result = invite_code.verify_invite_code(code)

        # Should still return the payload (validation is caller's responsibility)
        assert result is not None
        assert result.get("room_code") is None

    def test_verify_invite_code_expiration_boundary(self, mock_jwt_secret, room_code):
        """Test invite code at expiration boundary."""
        # Code that expires in 2 seconds
        payload = {
            "room_code": room_code,
            "type": "invite",
            "iat": int(time.time()),
            "exp": int(time.time()) + 2,
        }

        code = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")

        # Should work immediately
        result1 = invite_code.verify_invite_code(code)
        assert result1 is not None
        assert result1["room_code"] == room_code

        # Wait for expiration
        time.sleep(3)

        # Should now return None
        result2 = invite_code.verify_invite_code(code)
        assert result2 is None


@pytest.mark.unit
class TestGetRoomCodeFromInvite:
    """Tests for get_room_code_from_invite() function."""

    def test_get_room_code_from_valid_invite(self, mock_jwt_secret, room_code):
        """Test extracting room code from valid invite."""
        code = invite_code.generate_invite_code(room_code)

        result = invite_code.get_room_code_from_invite(code)

        assert result == room_code

    def test_get_room_code_from_expired_invite_returns_none(self, mock_jwt_secret, room_code):
        """Test that expired invite returns None."""
        # Create expired invite
        past_time = int(time.time()) - 3600
        expired_payload = {
            "room_code": room_code,
            "type": "invite",
            "iat": past_time - 1800,
            "exp": past_time,
        }

        expired_code = jwt.encode(expired_payload, mock_jwt_secret, algorithm="HS256")

        result = invite_code.get_room_code_from_invite(expired_code)

        assert result is None

    def test_get_room_code_from_invalid_invite_returns_none(self, mock_jwt_secret):
        """Test that invalid invite returns None."""
        invalid_codes = [
            "not-a-jwt",
            "invalid.format",
            "",
            None,
        ]

        for invalid_code in invalid_codes:
            result = invite_code.get_room_code_from_invite(invalid_code)
            assert result is None

    def test_get_room_code_from_wrong_type_token_returns_none(self, mock_jwt_secret, room_code):
        """Test that token with wrong type returns None."""
        payload = {
            "room_code": room_code,
            "type": "access",  # Wrong type
            "iat": int(time.time()),
            "exp": int(time.time()) + 1800,
        }

        wrong_type_code = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")

        result = invite_code.get_room_code_from_invite(wrong_type_code)

        assert result is None

    def test_get_room_code_from_invite_without_room_code_field(self, mock_jwt_secret):
        """Test extraction when room_code field is missing."""
        payload = {
            # Missing room_code
            "type": "invite",
            "iat": int(time.time()),
            "exp": int(time.time()) + 1800,
        }

        code = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")

        result = invite_code.get_room_code_from_invite(code)

        assert result is None

    @pytest.mark.parametrize("room_code", [
        "room-123",
        "test-room",
        "UPPERCASE",
        "room_underscores",
        "room.dots.here",
    ])
    def test_get_room_code_from_invite_various_codes(self, mock_jwt_secret, room_code):
        """Test extraction with various room code formats."""
        code = invite_code.generate_invite_code(room_code)

        result = invite_code.get_room_code_from_invite(code)

        assert result == room_code


@pytest.mark.unit
class TestInviteCodeEndToEnd:
    """End-to-end tests for complete invite code workflow."""

    def test_complete_invite_workflow(self, mock_jwt_secret, room_code):
        """Test complete invite workflow: generate → verify → extract room code."""
        # Generate
        code = invite_code.generate_invite_code(room_code)
        assert code is not None

        # Verify
        payload = invite_code.verify_invite_code(code)
        assert payload is not None
        assert payload["room_code"] == room_code

        # Extract room code
        extracted_room = invite_code.get_room_code_from_invite(code)
        assert extracted_room == room_code

    def test_invite_code_tampering_detected(self, mock_jwt_secret, room_code):
        """Test that tampering with invite code is detected."""
        code = invite_code.generate_invite_code(room_code)

        # Tamper with the code
        tampered_code = code[:-5] + "XXXXX"

        # Verification should fail
        result = invite_code.verify_invite_code(tampered_code)
        assert result is None

        # Room extraction should fail
        room = invite_code.get_room_code_from_invite(tampered_code)
        assert room is None

    def test_invite_code_different_rooms_different_codes(self, mock_jwt_secret):
        """Test that different rooms generate different invite codes."""
        code1 = invite_code.generate_invite_code("room-1")
        code2 = invite_code.generate_invite_code("room-2")

        assert code1 != code2

        room1 = invite_code.get_room_code_from_invite(code1)
        room2 = invite_code.get_room_code_from_invite(code2)

        assert room1 == "room-1"
        assert room2 == "room-2"
