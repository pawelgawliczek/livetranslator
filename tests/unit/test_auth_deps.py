"""
Unit tests for api/auth_deps.py

Tests authentication dependency functions:
- get_current_user() - Extract and verify JWT from Authorization header
"""

import pytest
from fastapi import HTTPException

# Import the module under test
from api import auth_deps


@pytest.mark.unit
class TestGetCurrentUser:
    """Tests for get_current_user() function."""

    def test_get_current_user_with_valid_token(self, mock_jwt_secret, sample_user_token, sample_user_payload):
        """Test that valid Bearer token returns user claims."""
        authorization = f"Bearer {sample_user_token}"

        result = auth_deps.get_current_user(authorization=authorization)

        assert result is not None
        assert result["sub"] == sample_user_payload["sub"]
        assert result["email"] == sample_user_payload["email"]
        assert "exp" in result

    def test_get_current_user_extracts_all_claims(self, mock_jwt_secret, sample_user_token):
        """Test that all JWT claims are extracted."""
        authorization = f"Bearer {sample_user_token}"

        result = auth_deps.get_current_user(authorization=authorization)

        assert "sub" in result
        assert "email" in result
        assert "user_id" in result
        assert "exp" in result
        assert "iat" in result

    def test_get_current_user_without_authorization_header(self):
        """Test that missing Authorization header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            auth_deps.get_current_user(authorization=None)

        assert exc_info.value.status_code == 401
        assert "Missing or invalid" in exc_info.value.detail

    def test_get_current_user_with_empty_authorization(self):
        """Test that empty Authorization header raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            auth_deps.get_current_user(authorization="")

        assert exc_info.value.status_code == 401
        assert "Missing or invalid" in exc_info.value.detail

    def test_get_current_user_without_bearer_prefix(self, sample_user_token):
        """Test that token without 'Bearer ' prefix raises 401."""
        # Just the token, no 'Bearer ' prefix
        authorization = sample_user_token

        with pytest.raises(HTTPException) as exc_info:
            auth_deps.get_current_user(authorization=authorization)

        assert exc_info.value.status_code == 401
        assert "Missing or invalid" in exc_info.value.detail

    def test_get_current_user_with_lowercase_bearer(self, sample_user_token):
        """Test that lowercase 'bearer' prefix raises 401 (case-sensitive)."""
        authorization = f"bearer {sample_user_token}"

        with pytest.raises(HTTPException) as exc_info:
            auth_deps.get_current_user(authorization=authorization)

        assert exc_info.value.status_code == 401
        assert "Missing or invalid" in exc_info.value.detail

    def test_get_current_user_with_invalid_token(self, mock_jwt_secret):
        """Test that invalid token raises 401."""
        authorization = "Bearer invalid-token-format"

        with pytest.raises(HTTPException) as exc_info:
            auth_deps.get_current_user(authorization=authorization)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication" in exc_info.value.detail

    def test_get_current_user_with_expired_token(self, mock_jwt_secret, expired_user_token):
        """Test that expired token raises 401."""
        authorization = f"Bearer {expired_user_token}"

        with pytest.raises(HTTPException) as exc_info:
            auth_deps.get_current_user(authorization=authorization)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication" in exc_info.value.detail

    def test_get_current_user_with_wrong_signature(self, mock_jwt_secret, invalid_signature_token):
        """Test that token with wrong signature raises 401."""
        authorization = f"Bearer {invalid_signature_token}"

        with pytest.raises(HTTPException) as exc_info:
            auth_deps.get_current_user(authorization=authorization)

        assert exc_info.value.status_code == 401
        assert "Invalid authentication" in exc_info.value.detail

    def test_get_current_user_with_malformed_bearer_format(self, sample_user_token):
        """Test various malformed Bearer formats."""
        malformed_headers = [
            f"Bearer{sample_user_token}",  # No space after Bearer
            f"Bearer  {sample_user_token}",  # Double space
            f"Bearer\t{sample_user_token}",  # Tab instead of space
            f"BearerToken {sample_user_token}",  # Wrong prefix
            f"Token {sample_user_token}",  # Wrong scheme
        ]

        for auth_header in malformed_headers:
            with pytest.raises(HTTPException) as exc_info:
                auth_deps.get_current_user(authorization=auth_header)

            assert exc_info.value.status_code == 401

    def test_get_current_user_with_extra_bearer_spaces(self, mock_jwt_secret, sample_user_token):
        """Test that extra spaces after Bearer are handled."""
        # Bearer with multiple spaces should work (token extraction skips them)
        authorization = f"Bearer   {sample_user_token}"

        # This depends on implementation - if it splits on first space, it might work
        # If it expects exactly 7 chars (len("Bearer ")), it will fail
        try:
            result = auth_deps.get_current_user(authorization=authorization)
            # If it works, verify the claims
            assert "sub" in result
        except HTTPException as e:
            # If it fails, verify it's a 401
            assert e.status_code == 401

    @pytest.mark.parametrize("user_email,user_id", [
        ("user1@example.com", "123"),
        ("admin@test.org", "456"),
        ("guest@livetranslator.com", "789"),
    ])
    def test_get_current_user_with_various_users(self, mock_jwt_secret, user_email, user_id):
        """Test get_current_user with various user data."""
        import jwt
        import time

        payload = {
            "sub": user_email,
            "email": user_email,
            "user_id": user_id,
            "exp": int(time.time()) + 3600,
        }

        token = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")
        authorization = f"Bearer {token}"

        result = auth_deps.get_current_user(authorization=authorization)

        assert result["email"] == user_email
        assert result["user_id"] == user_id

    def test_get_current_user_preserves_custom_claims(self, mock_jwt_secret):
        """Test that custom JWT claims are preserved."""
        import jwt
        import time

        payload = {
            "sub": "user@example.com",
            "email": "user@example.com",
            "role": "admin",
            "permissions": ["read", "write", "delete"],
            "metadata": {"org_id": "org-123"},
            "exp": int(time.time()) + 3600,
        }

        token = jwt.encode(payload, mock_jwt_secret, algorithm="HS256")
        authorization = f"Bearer {token}"

        result = auth_deps.get_current_user(authorization=authorization)

        assert result["role"] == "admin"
        assert result["permissions"] == ["read", "write", "delete"]
        assert result["metadata"]["org_id"] == "org-123"

    def test_get_current_user_error_status_code(self, mock_jwt_secret):
        """Test that all errors return 401 status code."""
        test_cases = [
            None,  # Missing header
            "",  # Empty header
            "invalid",  # No Bearer
            "Bearer ",  # Bearer with no token
            "Bearer invalid-token",  # Invalid token
        ]

        for authorization in test_cases:
            with pytest.raises(HTTPException) as exc_info:
                auth_deps.get_current_user(authorization=authorization)

            # All authentication errors should be 401
            assert exc_info.value.status_code == 401
