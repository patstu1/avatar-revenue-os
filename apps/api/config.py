import sys
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    api_env: str = "development"
    api_secret_key: str = "changeme"
    api_cors_origins: list[str] = ["http://localhost:3001"]
    log_level: str = "INFO"

    # Database (defaults point to Docker Compose service names for dev)
    database_url: str = "postgresql+asyncpg://avataros:changeme@postgres:5432/avatar_revenue_os"
    database_url_sync: str = "postgresql://avataros:changeme@postgres:5432/avatar_revenue_os"

    @field_validator("api_secret_key")
    @classmethod
    def reject_weak_secret(cls, v: str) -> str:
        weak_keys = {"changeme", "", "secret", "password", "test"}
        if v.lower().strip() in weak_keys:
            if "pytest" not in sys.modules:
                raise ValueError(
                    "API_SECRET_KEY is set to an insecure default. "
                    "Set a strong random key (32+ chars) in your .env file."
                )
        return v

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Celery
    celery_broker_url: str = "redis://redis:6379/1"
    celery_result_backend: str = "redis://redis:6379/2"

    # Auth
    access_token_expire_minutes: int = 60 * 24
    algorithm: str = "HS256"

    # AI Providers — Tiered Routing Stack
    anthropic_api_key: str = ""      # Claude: hero text / orchestrator
    google_ai_api_key: str = ""      # Gemini Flash + Imagen 4
    deepseek_api_key: str = ""       # DeepSeek: bulk text
    openai_api_key: str = ""         # GPT Image 1.5 + Realtime voice
    fal_api_key: str = ""            # Kling video + Flux images
    runway_api_key: str = ""         # Runway Gen-4: hero video
    heygen_api_key: str = ""         # HeyGen: primary avatar
    did_api_key: str = ""            # D-ID: budget avatar
    elevenlabs_api_key: str = ""     # ElevenLabs: hero voice
    fish_audio_api_key: str = ""     # Fish Audio: standard voice
    mistral_api_key: str = ""        # Voxtral: bulk voice
    suno_api_key: str = ""           # Suno: music
    tavus_api_key: str = ""          # Tavus: optional avatar

    # S3
    s3_endpoint_url: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_bucket_name: str = "avatar-revenue-os"
    s3_region: str = "us-east-1"

    # Stripe Billing
    stripe_api_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_starter_monthly: str = ""
    stripe_price_starter_annual: str = ""
    stripe_price_professional_monthly: str = ""
    stripe_price_professional_annual: str = ""
    stripe_price_business_monthly: str = ""
    stripe_price_business_annual: str = ""

    # Observability
    sentry_dsn: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
