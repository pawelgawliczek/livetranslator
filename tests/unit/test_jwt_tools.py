"""
Unit tests for api/jwt_tools.py

Tests JWT token verification with various scenarios:
- Valid tokens
- Expired tokens
- Invalid signatures
- Missing/empty tokens
- Malformed tokens
"""

import pytest
import jwt
import time
from jose import JWTError

# Import the module under test
from api import jwt_tools


@pytest.mark.unit
class TestVerifyToken:
    """Tests for verify_token() function."""

    def test_verify_valid_token(self, mock_jwt_secret, sample_user_token, sample_user_payload):
        """Test that a valid token is correctly decoded."""
        result = jwt_tools.verify_token(sample_user_token)

        assert result is not None
        assert result["sub"] == sample_user_payload["sub"]
        assert result["email"] == sample_user_payload["email"]
        assert "exp" in result
        assert "iat" in result

    def test_verify_token_extracts_all_claims(self, mock_jwt_secret, sample_user_token):
        """Test that all JWT claims are extracted."""
        result = jwt_tools.verify_token(sample_user_token)

        # Standard claims
        assert "sub" in result
        assert "exp" in result
        assert "iat" in result

        # Custom claims
        assert "email" in result
        assert "user_id" in result

    def test_verify_expired_token_raises_error(self, mock_jwt_secret, expired_user_token):
        """Test that an expired token raises JWTError."""
        with pytest.raises(JWTError):
            jwt_tools.verify_token(expired_user_token)

    def test_verify_token_with_invalid_signature(self, mock_jwt_secret, invalid_signature_token):
        """Test that a token with wrong signature raises JWTError."""
        with pytest.raises(JWTError):
            jwt_tools.verify_token(invalid_signature_token)

    def test_verify_empty_token_raises_error(self, mock_jwt_secret):
        """Test that an empty token raises JWTError."""
        with pytest.raises(JWTError, match="missing token"):
            jwt_tools.verify_token("")

    def test_verify_none_token_raises_error(self, mock_jwt_secret):
        """Test that None token raises JWTError."""
        with pytest.raises(JWTError, match="missing token"):
            jwt_tools.verify_token(None)

    def test_verify_malformed_token_raises_error(self, mock_jwt_secret):
        """Test that a malformed token raises JWTError."""
        malformed_tokens = [
            "not.a.valid.jwt",
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.invalid",
            "invalid-token-format",
            "Bearer eyJhbGciOiJIUzI1NiJ9",  # Contains 'Bearer ' prefix
        ]

        for token in malformed_tokens:
            with pytest.raises(JWTError):
                jwt_tools.verify_token(token)

    def test_verify_token_with_custom_claims(self, mock_jwt_secret):
        """Test that custom claims are preserved in verification."""
        custom_payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "role": "admin",
            "permissions": ["read", "write"],
            "exp": int(time.time()) + 3600,
        }

        token = jwt.encode(custom_payload, mock_jwt_secret, algorithm="HS256")
        result = jwt_tools.verify_token(token)

        assert result["role"] == "admin"
        assert result["permissions"] == ["read", "write"]

    def test_verify_token_checks_expiration(self, mock_jwt_secret):
        """Test that token expiration is properly checked."""
        # Token that expires in 1 second
        payload = {
            "sub": "user@example.com",
            "exp": int(time.time()) + 1,
            "iat": int(time.time()),
        }

        token = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")

        # Should work immediately
        result = jwt_tools.verify_token(token)
        assert result["sub"] == "user@example.com"

        # Wait for expiration
        time.sleep(2)

        # Should now raise error
        with pytest.raises(JWTError):
            jwt_tools.verify_token(token)

    def test_verify_token_with_different_algorithm_fails(self, mock_jwt_secret):
        """Test that tokens signed with different algorithm fail."""
        payload = {
            "sub": "user@example.com",
            "exp": int(time.time()) + 3600,
        }

        # Sign with HS512 instead of HS256
        token = jwt.encode(payload, mock_jwt_secret, algorithm="HS512")

        # Should fail when trying to verify with HS256
        with pytest.raises(JWTError):
            jwt_tools.verify_token(token)

    @pytest.mark.parametrize("email", [
        "user@example.com",
        "admin@test.org",
        "guest-123@livetranslator.com",
    ])
    def test_verify_token_with_various_emails(self, mock_jwt_secret, email):
        """Test token verification with various email formats."""
        payload = {
            "sub": email,
            "email": email,
            "exp": int(time.time()) + 3600,
        }

        token = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")
        result = jwt_tools.verify_token(token)

        assert result["email"] == email
        assert result["sub"] == email
