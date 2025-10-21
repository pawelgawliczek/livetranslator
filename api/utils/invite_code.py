"""
Invite code generation and validation.

Invite codes are time-limited (30 minutes) JWT tokens that contain:
- room_id: The room to join
- exp: Expiration timestamp (30 minutes from creation)

Format: Short JWT token (encrypted, signed, URL-safe)
Example: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
"""

import jwt
import time
from datetime import datetime, timedelta
from typing import Optional, Dict

# Import JWT secret from settings
from ..settings import JWT_SECRET


# Invite code validity (30 minutes)
INVITE_CODE_VALIDITY_MINUTES = 30


def generate_invite_code(room_code: str) -> str:
    """
    Generate a time-limited invite code for a room.

    Args:
        room_code: The room code (e.g., "room-123")

    Returns:
        Encrypted JWT token valid for 30 minutes

    Example:
        >>> code = generate_invite_code("room-123")
        >>> "eyJhbGci..." # JWT token
    """
    # Use time.time() for consistency with PyJWT's verification
    # (datetime.utcnow().timestamp() can have timezone issues)
    now = int(time.time())
    exp = now + (INVITE_CODE_VALIDITY_MINUTES * 60)

    payload = {
        "room_code": room_code,
        "iat": now,  # Issued at
        "exp": exp,  # Expires at
        "type": "invite"
    }

    # Sign with JWT secret
    secret = JWT_SECRET
    if isinstance(secret, bytes):
        secret = secret.decode('utf-8')

    token = jwt.encode(payload, secret, algorithm="HS256")

    return token


def verify_invite_code(invite_code: str) -> Optional[Dict]:
    """
    Verify and decode an invite code.

    Args:
        invite_code: The JWT token to verify

    Returns:
        Decoded payload with room_code if valid, None if invalid/expired

    Example:
        >>> payload = verify_invite_code("eyJhbGci...")
        >>> payload
        {'room_code': 'room-123', 'iat': 1234567890, 'exp': 1234569690, 'type': 'invite'}
    """
    try:
        secret = JWT_SECRET
        if isinstance(secret, bytes):
            secret = secret.decode('utf-8')

        payload = jwt.decode(
            invite_code,
            secret,
            algorithms=["HS256"],
            options={"verify_exp": True}  # Verify expiration
        )

        # Verify this is an invite token
        if payload.get("type") != "invite":
            return None

        return payload

    except jwt.ExpiredSignatureError:
        # Token has expired (> 30 minutes old)
        return None
    except jwt.InvalidTokenError:
        # Invalid token (tampered, wrong signature, etc.)
        return None
    except Exception:
        # Any other error
        return None


def get_room_code_from_invite(invite_code: str) -> Optional[str]:
    """
    Extract room code from invite code (convenience function).

    Args:
        invite_code: The JWT token

    Returns:
        Room code if valid, None if invalid/expired

    Example:
        >>> get_room_code_from_invite("eyJhbGci...")
        'room-123'
    """
    payload = verify_invite_code(invite_code)
    if payload:
        return payload.get("room_code")
    return None
