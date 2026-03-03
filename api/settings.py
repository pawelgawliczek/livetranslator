import os
from pydantic_settings import BaseSettings
from pydantic import AnyUrl
from pathlib import Path

class Settings(BaseSettings):
    LT_ENV: str = "dev"
    LT_DOMAIN: str = "localhost"
    LT_DB_URL: str
    LT_REDIS_URL: AnyUrl = "redis://localhost:6379/0"
    LT_JWT_SECRET_FILE: str = ""
    LT_GOOGLE_CLIENT_ID_FILE: str = ""
    LT_GOOGLE_CLIENT_SECRET_FILE: str = ""
    LT_AUDIO_DIR: str = "/data/audio"
    LT_MODELS_DIR: str = "/models"
    LT_MT_BASE_URL: str = "http://mt_worker:8081"
    HTTP_TIMEOUT: int = 30

    class Config:
        env_file = ".env"
        env_prefix = ""

def read_secret(path: str) -> str:
    p = Path(path)
    return p.read_text().strip() if p.exists() else ""

settings = Settings()
_jwt = read_secret(settings.LT_JWT_SECRET_FILE) or os.getenv("JWT_SECRET") or ""
if not _jwt:
    raise RuntimeError("JWT_SECRET must be set via LT_JWT_SECRET_FILE or JWT_SECRET env var")
JWT_SECRET = _jwt
GOOGLE_CLIENT_ID = read_secret(settings.LT_GOOGLE_CLIENT_ID_FILE) or os.getenv("GOOGLE_CLIENT_ID") or ""
GOOGLE_CLIENT_SECRET = read_secret(settings.LT_GOOGLE_CLIENT_SECRET_FILE) or os.getenv("GOOGLE_CLIENT_SECRET") or ""
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

