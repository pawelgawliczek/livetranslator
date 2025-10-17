from jose import jwt, JWTError
from .settings import JWT_SECRET
ALGO = "HS256"

def verify_token(token: str) -> dict:
    if not token:
        raise JWTError("missing token")
    return jwt.decode(token, JWT_SECRET, algorithms=[ALGO])
