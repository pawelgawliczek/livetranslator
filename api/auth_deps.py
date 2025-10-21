"""Authentication dependencies for FastAPI endpoints."""
from fastapi import Header, HTTPException
from .jwt_tools import verify_token


def get_current_user(authorization: str = Header(None)) -> dict:
    """
    Extract and verify user from JWT token in Authorization header.

    Args:
        authorization: The Authorization header value (Bearer <token>)

    Returns:
        dict: JWT claims containing user information (email, sub, etc.)

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )

    token = authorization[7:]  # Remove "Bearer " prefix
    try:
        claims = verify_token(token)
        return claims
    except Exception as e:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )
