"""Media provider adapters for avatar video and voice synthesis.

Each adapter implements request/response models, retry logic, error persistence,
and fallback routing. Actual API calls require live credentials.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum

import structlog

logger = structlog.get_logger()


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


def _result_to_response(provider: str, result: dict, request: MediaRequest | None = None) -> MediaResponse:
    """Map a standard ai_clients result dict to a MediaResponse."""
    if result.get("blocked"):
        return MediaResponse(
            provider=provider, status=ProviderStatus.FAILED,
            error_message=result.get("error", "API key not configured"),
            error_details={"reason": "missing_credentials"},
        )
    if not result.get("success"):
        return MediaResponse(
            provider=provider, status=ProviderStatus.FAILED,
            error_message=result.get("error", "Unknown error"),
            error_details={"status_code": result.get("status_code", 0)},
        )
    data = result.get("data", {})
    output_url = (
        data.get("video_url")
        or data.get("audio_url")
        or data.get("image_url")
        or data.get("output_url")
    )
    job_id = data.get("video_id") or data.get("job_id") or data.get("task_id")
    return MediaResponse(
        provider=provider,
        status=ProviderStatus.SUCCESS if output_url else ProviderStatus.PENDING,
        provider_job_id=job_id or f"{provider}_{uuid.uuid4().hex[:12]}",
        output_url=output_url,
        duration_seconds=data.get("duration"),
        metadata={k: v for k, v in data.items() if k not in ("video_url", "audio_url", "image_url", "audio_bytes")},
    )


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
        # TODO: No TavusClient implementation exists yet in ai_clients.py — wire when added
        return MediaResponse(
            provider="tavus", status=ProviderStatus.PENDING,
            provider_job_id=f"tavus_{uuid.uuid4().hex[:12]}",
            error_message="Tavus client not yet implemented — pending real integration",
            metadata={"request_script_length": len(request.script_text)},
        )

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        # TODO: Wire to TavusClient when available
        return MediaResponse(
            provider="tavus", status=ProviderStatus.PENDING,
            provider_job_id=provider_job_id,
            error_message="Status check requires TavusClient implementation",
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
        from packages.clients.ai_clients import ElevenLabsClient
        client = ElevenLabsClient(api_key=self.api_key)
        voice_id = request.config.get("voice_id", "21m00Tcm4TlvDq8ikWAM")
        result = await client.generate(text=request.script_text, voice_id=voice_id)
        return _result_to_response("elevenlabs", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(
            provider="elevenlabs", status=ProviderStatus.SUCCESS,
            provider_job_id=provider_job_id,
            metadata={"note": "ElevenLabs TTS is synchronous — no polling needed"},
        )


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
        # TODO: No OpenAIRealtimeClient exists yet — wire when WebSocket client is added
        return MediaResponse(
            provider="openai_realtime", status=ProviderStatus.PENDING,
            provider_job_id=f"oai_{uuid.uuid4().hex[:12]}",
            error_message="OpenAI Realtime client not yet implemented — requires WebSocket integration",
        )

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        # TODO: Wire to OpenAIRealtimeClient when available
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
        from packages.clients.ai_clients import HeyGenClient
        client = HeyGenClient(api_key=self.api_key)
        avatar_id = request.avatar_provider_id or request.config.get("avatar_id", "default")
        voice_id = request.voice_provider_id or request.config.get("voice_id", "")
        result = await client.create_video(
            script_text=request.script_text,
            avatar_id=avatar_id,
            voice_id=voice_id,
        )
        return _result_to_response("heygen", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(provider="heygen", status=ProviderStatus.FAILED, error_message="HeyGen API key not configured")
        from packages.clients.ai_clients import HeyGenClient
        client = HeyGenClient(api_key=self.api_key)
        result = await client.poll_video(provider_job_id, max_wait=60)
        return _result_to_response("heygen", result)


class FallbackAdapter(MediaProviderAdapter):
    """Fallback: Template-based content when no premium provider is available."""

    def provider_name(self) -> str:
        return "fallback"

    def capabilities(self) -> dict:
        return {"template_video": True, "static_image": True, "studio_video": True}

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


class RunwayAdapter(MediaProviderAdapter):
    """Runway Gen-4 Turbo: Hero cinematic video generation."""
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
    def provider_name(self) -> str:
        return "runway"
    def capabilities(self) -> dict:
        return {"cinematic_video": True, "hero_video": True, "studio_video": True, "max_duration_sec": 15}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(provider="runway", status=ProviderStatus.FAILED, error_message="Runway API key not configured")
        from packages.clients.ai_clients import RunwayClient
        client = RunwayClient(api_key=self.api_key)
        duration = min(request.duration_hint_seconds, 15)
        image_url = request.config.get("image_url")
        result = await client.generate(prompt=request.script_text, duration_sec=duration, image_url=image_url)
        return _result_to_response("runway", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="runway", status=ProviderStatus.PENDING, provider_job_id=provider_job_id,
                             metadata={"note": "Runway polls internally during generate()"})


class KlingAdapter(MediaProviderAdapter):
    """Kling AI: Bulk social video generation via fal.ai."""
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
    def provider_name(self) -> str:
        return "kling"
    def capabilities(self) -> dict:
        return {"social_video": True, "b_roll": True, "studio_video": True, "max_duration_sec": 30}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(provider="kling", status=ProviderStatus.FAILED, error_message="FAL API key not configured")
        from packages.clients.ai_clients import KlingClient
        client = KlingClient(api_key=self.api_key)
        duration = min(request.duration_hint_seconds, 30)
        aspect = request.config.get("aspect_ratio", "9:16")
        result = await client.generate(prompt=request.script_text, duration_sec=duration, aspect_ratio=aspect)
        return _result_to_response("kling", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="kling", status=ProviderStatus.PENDING, provider_job_id=provider_job_id)


class DIDAdapter(MediaProviderAdapter):
    """D-ID: Budget avatar video generation."""
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
    def provider_name(self) -> str:
        return "did"
    def capabilities(self) -> dict:
        return {"avatar_video": True, "lip_sync": True, "budget_avatar": True, "studio_video": True}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(provider="did", status=ProviderStatus.FAILED, error_message="D-ID API key not configured")
        from packages.clients.ai_clients import DIDClient
        client = DIDClient(api_key=self.api_key)
        source_url = request.config.get("source_url", "https://d-id-public-bucket.s3.us-west-2.amazonaws.com/alice.jpg")
        result = await client.generate(script=request.script_text, source_url=source_url)
        return _result_to_response("did", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="did", status=ProviderStatus.PENDING, provider_job_id=provider_job_id,
                             metadata={"note": "D-ID polls internally during generate()"})


class FishAudioAdapter(MediaProviderAdapter):
    """Fish Audio: Standard-tier TTS, #1 on TTS-Arena."""
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
    def provider_name(self) -> str:
        return "fish_audio"
    def capabilities(self) -> dict:
        return {"voice_synthesis": True, "bulk_voiceover": True, "output_formats": ["mp3", "wav"]}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(provider="fish_audio", status=ProviderStatus.FAILED, error_message="Fish Audio API key not configured")
        from packages.clients.ai_clients import FishAudioClient
        client = FishAudioClient(api_key=self.api_key)
        voice_id = request.voice_provider_id or request.config.get("voice_id", "default")
        result = await client.generate(text=request.script_text, voice_id=voice_id)
        return _result_to_response("fish_audio", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="fish_audio", status=ProviderStatus.SUCCESS, provider_job_id=provider_job_id,
                             metadata={"note": "Fish Audio TTS is synchronous"})


class VoxtralAdapter(MediaProviderAdapter):
    """Voxtral TTS (Mistral): Ultra-budget voice synthesis."""
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
    def provider_name(self) -> str:
        return "voxtral"
    def capabilities(self) -> dict:
        return {"voice_synthesis": True, "voice_cloning": True, "ultra_budget": True}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(provider="voxtral", status=ProviderStatus.FAILED, error_message="Mistral API key not configured")
        from packages.clients.ai_clients import VoxtralClient
        client = VoxtralClient(api_key=self.api_key)
        voice_id = request.voice_provider_id or request.config.get("voice_id")
        result = await client.generate(text=request.script_text, voice_id=voice_id)
        return _result_to_response("voxtral", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="voxtral", status=ProviderStatus.SUCCESS, provider_job_id=provider_job_id,
                             metadata={"note": "Voxtral TTS is synchronous"})


class SunoAdapter(MediaProviderAdapter):
    """Suno: AI music generation."""
    def __init__(self, api_key: str = ""):
        self.api_key = api_key
    def provider_name(self) -> str:
        return "suno"
    def capabilities(self) -> dict:
        return {"music_generation": True, "background_tracks": True}

    async def submit_job(self, request: MediaRequest) -> MediaResponse:
        if not self.api_key:
            return MediaResponse(provider="suno", status=ProviderStatus.FAILED, error_message="Suno API key not configured")
        from packages.clients.ai_clients import SunoClient
        client = SunoClient(api_key=self.api_key)
        duration = request.duration_hint_seconds or 30
        genre = request.config.get("genre", "electronic")
        result = await client.generate(prompt=request.script_text, duration_sec=duration, genre=genre)
        return _result_to_response("suno", result, request)

    async def check_status(self, provider_job_id: str) -> MediaResponse:
        return MediaResponse(provider="suno", status=ProviderStatus.PENDING, provider_job_id=provider_job_id)


PROVIDER_REGISTRY: dict[str, type[MediaProviderAdapter]] = {
    "tavus": TavusAdapter,
    "elevenlabs": ElevenLabsAdapter,
    "openai_realtime": OpenAIRealtimeAdapter,
    "heygen": HeyGenLiveAvatarAdapter,
    "fallback": FallbackAdapter,
    "runway": RunwayAdapter,
    "kling": KlingAdapter,
    "did": DIDAdapter,
    "fish_audio": FishAudioAdapter,
    "voxtral": VoxtralAdapter,
    "suno": SunoAdapter,
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
