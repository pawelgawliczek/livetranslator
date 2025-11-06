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
    STRIPE_MODE: str = "test"  # "test" or "live"

    class Config:
        env_file = ".env"
        env_prefix = ""

def read_secret(path: str) -> str:
    p = Path(path)
    return p.read_text().strip() if p.exists() else ""

settings = Settings()
JWT_SECRET = read_secret(settings.LT_JWT_SECRET_FILE) or os.getenv("JWT_SECRET") or "CHANGE_ME_BEFORE_DEPLOY"
GOOGLE_CLIENT_ID = read_secret(settings.LT_GOOGLE_CLIENT_ID_FILE) or os.getenv("GOOGLE_CLIENT_ID") or ""
GOOGLE_CLIENT_SECRET = read_secret(settings.LT_GOOGLE_CLIENT_SECRET_FILE) or os.getenv("GOOGLE_CLIENT_SECRET") or ""
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "")

# Payment provider keys (CRIT-1: Load from secrets directory)
# Mode-aware loading: test or live based on STRIPE_MODE setting
_stripe_mode = settings.STRIPE_MODE.lower()
STRIPE_SECRET_KEY = (
    read_secret(f"/run/secrets/stripe_{_stripe_mode}_secret_key")
    or os.getenv("STRIPE_SECRET_KEY", "sk_test_PLACEHOLDER")
)

STRIPE_PUBLISHABLE_KEY = (
    read_secret(f"/run/secrets/stripe_{_stripe_mode}_publishable_key")
    or os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_PLACEHOLDER")
)

STRIPE_WEBHOOK_SECRET = (
    read_secret(f"/run/secrets/stripe_{_stripe_mode}_webhook_secret")
    or os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_PLACEHOLDER")
)

# Production safety: Fail hard if using placeholder secrets in prod
if settings.LT_ENV == "prod":
    if "PLACEHOLDER" in STRIPE_SECRET_KEY:
        raise RuntimeError(f"Stripe {_stripe_mode} secret key not configured in production")
    if "PLACEHOLDER" in STRIPE_WEBHOOK_SECRET:
        raise RuntimeError(f"Stripe {_stripe_mode} webhook secret not configured in production")

APPLE_SHARED_SECRET = (
    read_secret("/opt/stack/secrets/apple_shared_secret")
    or os.getenv("APPLE_SHARED_SECRET", "PLACEHOLDER")
)

# Internal API key for service-to-service communication (CRIT-2)
INTERNAL_API_KEY = (
    read_secret("/opt/stack/secrets/internal_api_key")
    or os.getenv("INTERNAL_API_KEY")
    or "dev-internal-key"  # Development fallback
)

