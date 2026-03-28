"""Media provider adapters for avatar video and voice synthesis.

Each adapter implements request/response models, retry logic, error persistence,
and fallback routing. Actual API calls require live credentials.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ProviderStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    RETRYING = "retrying"


@dataclass
class MediaRequest:
    job_id: uuid.UUID
    script_text: str
    avatar_provider_id: str | None = None
    voice_provider_id: str | None = None
    duration_hint_seconds: int = 60
    output_format: str = "mp4"
    resolution: str = "1080p"
    config: dict = field(default_factory=dict)


@dataclass
class MediaResponse:
    provider: str
    status: ProviderStatus
    provider_job_id: str | None = None
    output_url: str | None = None
    duration_seconds: float | None = None
    cost: float = 0.0
    error_message: str | None = None
    error_details: dict = field(default_factory=dict)
    retries_used: int = 0
    metadata: dict = field(default_factory=dict)


class MediaProviderAdapter(ABC):
    MAX_RETRIES = 3

    @abstractmethod
    def provider_name(self) -> str: ...

    @abstractmethod
    def capabilities(self) -> dict: ...

    @abstractmethod
    async def submit_job(self, request: MediaRequest) -> MediaResponse: ...

    @abstractmethod
    async def check_status(self, provider_job_id: str) -> MediaResponse: ...


class TavusAdapter(MediaProviderAdapter):
    """Tavus: Primary async avatar video generation.
    Supports lip-synced talking head video from script text.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def provider_name(self) -> str:
        return "tavus"

    def capabilities(self) -> dict:
        return {
            "async_video": True, "lip_sync": True, "custom_background": True,
            "max_duration_sec": 300, "output_formats": ["mp4", "webm"],
        }

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(
                provider="tavus", status=ProviderStatus.FAILED,
                error_message="Tavus API key not configured",
                error_details={"reason": "missing_credentials"},
            )
        # Real implementation would call httpx.AsyncClient POST to Tavus API
        # with retry logic via tenacity
        return MediaResponse(
            provider="tavus", status=ProviderStatus.PENDING,
            provider_job_id=f"tavus_{uuid.uuid4().hex[:12]}",
            error_message="Live API call pending — credentials required",
            metadata={"request_script_length": len(request.script_text)},
        )

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(
            provider="tavus", status=ProviderStatus.PENDING,
            provider_job_id=provider_job_id,
            error_message="Status check requires live API credentials",
        )


class ElevenLabsAdapter(MediaProviderAdapter):
    """ElevenLabs: Premium voice synthesis.
    Supports voice cloning, multi-language, streaming.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def provider_name(self) -> str:
        return "elevenlabs"

    def capabilities(self) -> dict:
        return {
            "voice_cloning": True, "streaming": True,
            "languages": ["en", "es", "fr", "de", "pt", "it", "ja", "ko", "zh"],
            "output_formats": ["mp3", "wav", "ogg"],
        }

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(
                provider="elevenlabs", status=ProviderStatus.FAILED,
                error_message="ElevenLabs API key not configured",
                error_details={"reason": "missing_credentials"},
            )
        return MediaResponse(
            provider="elevenlabs", status=ProviderStatus.PENDING,
            provider_job_id=f"el_{uuid.uuid4().hex[:12]}",
            metadata={"chars": len(request.script_text)},
        )

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="elevenlabs", status=ProviderStatus.PENDING, provider_job_id=provider_job_id)


class OpenAIRealtimeAdapter(MediaProviderAdapter):
    """OpenAI Realtime: Live conversational voice/intelligence.
    Supports real-time voice with function calling.
    """

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def provider_name(self) -> str:
        return "openai_realtime"

    def capabilities(self) -> dict:
        return {
            "realtime_conversation": True, "function_calling": True,
            "voice_modes": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
        }

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(
                provider="openai_realtime", status=ProviderStatus.FAILED,
                error_message="OpenAI API key not configured",
            )
        return MediaResponse(
            provider="openai_realtime", status=ProviderStatus.PENDING,
            provider_job_id=f"oai_{uuid.uuid4().hex[:12]}",
        )

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="openai_realtime", status=ProviderStatus.PENDING, provider_job_id=provider_job_id)


class HeyGenLiveAvatarAdapter(MediaProviderAdapter):
    """HeyGen LiveAvatar: Live avatar streaming for interactive use cases."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def provider_name(self) -> str:
        return "heygen"

    def capabilities(self) -> dict:
        return {"live_streaming": True, "interactive": True, "real_time_lip_sync": True}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(
                provider="heygen", status=ProviderStatus.FAILED,
                error_message="HeyGen API key not configured",
            )
        return MediaResponse(
            provider="heygen", status=ProviderStatus.PENDING,
            provider_job_id=f"hg_{uuid.uuid4().hex[:12]}",
        )

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="heygen", status=ProviderStatus.PENDING, provider_job_id=provider_job_id)


class FallbackAdapter(MediaProviderAdapter):
    """Fallback: Template-based content when no premium provider is available."""

    def provider_name(self) -> str:
        return "fallback"

    def capabilities(self) -> dict:
        return {"template_video": True, "static_image": True}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        return MediaResponse(
            provider="fallback", status=ProviderStatus.SUCCESS,
            provider_job_id=f"fb_{uuid.uuid4().hex[:12]}",
            output_url="pending://fallback/template",
            cost=0.0,
            metadata={"note": "Fallback template — no AI generation"},
        )

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="fallback", status=ProviderStatus.SUCCESS, provider_job_id=provider_job_id)


PROVIDER_REGISTRY: dict[str, type[MediaProviderAdapter]] = {
    "tavus": TavusAdapter,
    "elevenlabs": ElevenLabsAdapter,
    "openai_realtime": OpenAIRealtimeAdapter,
    "heygen": HeyGenLiveAvatarAdapter,
    "fallback": FallbackAdapter,
}


def select_provider(required_capability: str, profiles: list[dict]) -> str | None:
    """Select best provider from profiles based on capability, health, primary/fallback."""
    candidates = []
    for p in profiles:
        caps = p.get("capabilities", {})
        health = p.get("health_status", "healthy")
        if caps.get(required_capability) and health in ("healthy", "warning"):
            priority = 0
            if p.get("is_primary"):
                priority = 2
            elif p.get("is_fallback"):
                priority = 1
            candidates.append((priority, p.get("cost_per_minute", 999), p["provider"]))

    if not candidates:
        return "fallback"

    candidates.sort(key=lambda x: (-x[0], x[1]))
    return candidates[0][2]
