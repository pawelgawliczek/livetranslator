"""
Unit test fixtures - Pure unit tests with no I/O.

Provides:
- Mock JWT secrets
- Sample tokens and payloads
- Test data factories
"""

import pytest
import jwt
import time
from datetime import datetime, timedelta


# Test JWT Secret (different from production)
TEST_JWT_SECRET = "test-secret-for-unit-tests-only"


@pytest.fixture
def mock_jwt_secret(monkeypatch):
    """Mock JWT_SECRET for testing."""
    import api.jwt_tools
    import api.utils.invite_code

    # Mock the JWT_SECRET in both modules
    monkeypatch.setattr(api.jwt_tools, "JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(api.utils.invite_code, "JWT_SECRET", TEST_JWT_SECRET)

    return TEST_JWT_SECRET


@pytest.fixture
def sample_user_payload():
    """Sample user JWT payload."""
    return {
        "sub": "user@example.com",
        "email": "user@example.com",
        "user_id": "123",
        "exp": int(time.time()) + 3600,  # Expires in 1 hour
        "iat": int(time.time()),
    }


@pytest.fixture
def sample_user_token(mock_jwt_secret, sample_user_payload):
    """Generate a valid user JWT token."""
    return jwt.encode(sample_user_payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def expired_user_token(mock_jwt_secret):
    """Generate an expired JWT token."""
    payload = {
        "sub": "user@example.com",
        "email": "user@example.com",
        "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        "iat": int(time.time()) - 7200,
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


@pytest.fixture
def invalid_signature_token():
    """Generate a token with invalid signature."""
    payload = {
        "sub": "user@example.com",
        "exp": int(time.time()) + 3600,
    }
    # Signed with different secret
    return jwt.encode(payload, "wrong-secret", algorithm="HS256")


@pytest.fixture
def sample_invite_payload():
    """Sample invite code payload."""
    return {
        "room_code": "test-room-123",
        "type": "invite",
        "iat": int(time.time()),
        "exp": int(time.time()) + 1800,  # 30 minutes
    }


@pytest.fixture
def sample_invite_url():
    """Sample invite URL for QR codes."""
    return "https://livetranslator.pawelgawliczek.cloud/join/test-room-123?invite=abc123"


# Test room codes
TEST_ROOM_CODES = [
    "test-room-1",
    "test-room-abc",
    "room-with-dashes",
    "UPPERCASE-ROOM",
]


@pytest.fixture(params=TEST_ROOM_CODES)
def room_code(request):
    """Parametrized room codes for testing."""
    return request.param
