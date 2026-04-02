from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    api_env: str = "development"
    api_secret_key: str = "changeme"
    api_cors_origins: list[str] = ["http://localhost:3001"]
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://avataros:avataros_dev_2026@postgres:5432/avatar_revenue_os"
    database_url_sync: str = "postgresql://avataros:avataros_dev_2026@postgres:5432/avatar_revenue_os"

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

    # Observability
    sentry_dsn: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
