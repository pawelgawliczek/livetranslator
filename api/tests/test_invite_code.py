"""
Unit tests for invite code generation and validation.

Tests cover:
- JWT token generation with correct expiration
- Token validation and decoding
- Room code extraction
- Expired token handling
- Invalid token handling
"""

import time
import pytest
from datetime import datetime, timedelta

# Mock the JWT_SECRET before importing the module
import sys
from unittest.mock import Mock, patch

# Add parent directory to path
sys.path.insert(0, '/app')


class TestInviteCode:
    """Test suite for invite code utilities."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        # Mock the JWT_SECRET
        with patch('api.settings.JWT_SECRET', 'test-secret-key'):
            from api.utils.invite_code import (
                generate_invite_code,
                verify_invite_code,
                get_room_code_from_invite,
                INVITE_CODE_VALIDITY_MINUTES
            )
            self.generate_invite_code = generate_invite_code
            self.verify_invite_code = verify_invite_code
            self.get_room_code_from_invite = get_room_code_from_invite
            self.INVITE_CODE_VALIDITY_MINUTES = INVITE_CODE_VALIDITY_MINUTES
            yield

    def test_generate_invite_code_returns_jwt(self):
        """Test that generate_invite_code returns a valid JWT token."""
        room_code = "test-room"
        invite_code = self.generate_invite_code(room_code)

        # JWT tokens have 3 parts separated by dots
        assert isinstance(invite_code, str)
        assert invite_code.count('.') == 2

        # Should be URL-safe (no special characters except dots, dashes, underscores)
        allowed_chars = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.')
        assert all(c in allowed_chars for c in invite_code)

    def test_generate_invite_code_contains_room_code(self):
        """Test that generated token contains the room code."""
        room_code = "my-special-room"
        invite_code = self.generate_invite_code(room_code)

        # Verify the token
        payload = self.verify_invite_code(invite_code)
        assert payload is not None
        assert payload['room_code'] == room_code

    def test_generate_invite_code_has_correct_expiration(self):
        """Test that generated token expires in 30 minutes."""
        room_code = "test-room"
        before_time = int(time.time())
        invite_code = self.generate_invite_code(room_code)
        after_time = int(time.time())

        payload = self.verify_invite_code(invite_code)
        assert payload is not None

        # Check issued at time is recent
        assert payload['iat'] >= before_time
        assert payload['iat'] <= after_time

        # Check expiration is 30 minutes from issued time
        expected_exp = payload['iat'] + (self.INVITE_CODE_VALIDITY_MINUTES * 60)
        assert payload['exp'] == expected_exp

    def test_generate_invite_code_has_type_field(self):
        """Test that generated token has type='invite'."""
        room_code = "test-room"
        invite_code = self.generate_invite_code(room_code)

        payload = self.verify_invite_code(invite_code)
        assert payload is not None
        assert payload['type'] == 'invite'

    def test_verify_invite_code_valid_token(self):
        """Test that verify_invite_code accepts valid tokens."""
        room_code = "test-room"
        invite_code = self.generate_invite_code(room_code)

        payload = self.verify_invite_code(invite_code)
        assert payload is not None
        assert isinstance(payload, dict)
        assert 'room_code' in payload
        assert 'iat' in payload
        assert 'exp' in payload
        assert 'type' in payload

    def test_verify_invite_code_invalid_token(self):
        """Test that verify_invite_code rejects invalid tokens."""
        invalid_token = "not-a-valid-jwt-token"
        payload = self.verify_invite_code(invalid_token)
        assert payload is None

    def test_verify_invite_code_wrong_signature(self):
        """Test that verify_invite_code rejects tokens with wrong signature."""
        # This is a valid JWT but signed with a different secret
        wrong_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb29tX2NvZGUiOiJ0ZXN0Iiwic3ViIjoiMTIzNDU2Nzg5MCIsIm5hbWUiOiJKb2huIERvZSIsImlhdCI6MTUxNjIzOTAyMn0.wrong-signature"
        payload = self.verify_invite_code(wrong_token)
        assert payload is None

    def test_verify_invite_code_expired_token(self):
        """Test that verify_invite_code rejects expired tokens."""
        import jwt
        from api.settings import JWT_SECRET

        # Create an expired token (expired 1 hour ago)
        now = int(time.time())
        payload = {
            'room_code': 'test-room',
            'iat': now - 3600 - 1800,  # Issued 1.5 hours ago
            'exp': now - 3600,  # Expired 1 hour ago
            'type': 'invite'
        }

        expired_token = jwt.encode(payload, 'test-secret-key', algorithm='HS256')

        with patch('api.settings.JWT_SECRET', 'test-secret-key'):
            result = self.verify_invite_code(expired_token)
            assert result is None

    def test_verify_invite_code_wrong_type(self):
        """Test that verify_invite_code rejects tokens with wrong type."""
        import jwt

        # Create a token with type='access' instead of 'invite'
        now = int(time.time())
        payload = {
            'room_code': 'test-room',
            'iat': now,
            'exp': now + 1800,
            'type': 'access'  # Wrong type
        }

        token = jwt.encode(payload, 'test-secret-key', algorithm='HS256')

        with patch('api.settings.JWT_SECRET', 'test-secret-key'):
            result = self.verify_invite_code(token)
            assert result is None

    def test_get_room_code_from_invite_valid(self):
        """Test extracting room code from valid invite."""
        room_code = "my-test-room"
        invite_code = self.generate_invite_code(room_code)

        extracted = self.get_room_code_from_invite(invite_code)
        assert extracted == room_code

    def test_get_room_code_from_invite_invalid(self):
        """Test extracting room code from invalid invite."""
        invalid_token = "not-a-valid-token"
        extracted = self.get_room_code_from_invite(invalid_token)
        assert extracted is None

    def test_get_room_code_from_invite_expired(self):
        """Test that expired tokens don't return room code."""
        import jwt

        # Create an expired token
        now = int(time.time())
        payload = {
            'room_code': 'test-room',
            'iat': now - 3600,
            'exp': now - 1800,  # Expired 30 minutes ago
            'type': 'invite'
        }

        expired_token = jwt.encode(payload, 'test-secret-key', algorithm='HS256')

        with patch('api.settings.JWT_SECRET', 'test-secret-key'):
            result = self.get_room_code_from_invite(expired_token)
            # Should return None because token is expired
            assert result is None

    def test_multiple_rooms_different_codes(self):
        """Test that different rooms get different invite codes."""
        code1 = self.generate_invite_code("room-1")
        code2 = self.generate_invite_code("room-2")

        # Codes should be different
        assert code1 != code2

        # But both should be valid
        payload1 = self.verify_invite_code(code1)
        payload2 = self.verify_invite_code(code2)

        assert payload1['room_code'] == "room-1"
        assert payload2['room_code'] == "room-2"

    def test_invite_code_reproducibility(self):
        """Test that generating code at same timestamp produces same code."""
        room_code = "test-room"

        # Generate two codes in quick succession
        with patch('time.time', return_value=1234567890):
            code1 = self.generate_invite_code(room_code)

        with patch('time.time', return_value=1234567890):
            code2 = self.generate_invite_code(room_code)

        # Should be identical if generated at same timestamp
        assert code1 == code2


class TestInviteCodeIntegration:
    """Integration tests for invite code with actual JWT library."""

    def test_jwt_decode_without_verification(self):
        """Test that we can decode JWT without verification to inspect payload."""
        import jwt
        from api.utils.invite_code import generate_invite_code

        with patch('api.settings.JWT_SECRET', 'test-secret'):
            room_code = "inspect-room"
            invite_code = generate_invite_code(room_code)

            # Decode without verification
            payload = jwt.decode(invite_code, options={'verify_signature': False})

            assert payload['room_code'] == room_code
            assert payload['type'] == 'invite'
            assert 'iat' in payload
            assert 'exp' in payload

    def test_jwt_structure(self):
        """Test the structure of the JWT token."""
        import base64
        import json
        from api.utils.invite_code import generate_invite_code

        with patch('api.settings.JWT_SECRET', 'test-secret'):
            invite_code = generate_invite_code("test-room")

            # JWT has 3 parts: header.payload.signature
            parts = invite_code.split('.')
            assert len(parts) == 3

            # Decode header
            header_bytes = parts[0] + '=' * (4 - len(parts[0]) % 4)  # Add padding
            header = json.loads(base64.urlsafe_b64decode(header_bytes))
            assert header['alg'] == 'HS256'
            assert header['typ'] == 'JWT'

            # Decode payload
            payload_bytes = parts[1] + '=' * (4 - len(parts[1]) % 4)  # Add padding
            payload = json.loads(base64.urlsafe_b64decode(payload_bytes))
            assert 'room_code' in payload
            assert 'iat' in payload
            assert 'exp' in payload
            assert payload['type'] == 'invite'
