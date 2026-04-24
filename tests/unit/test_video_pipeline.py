"""Unit tests — full video production pipeline: clients, routing, orchestration."""
from __future__ import annotations

# ── New API Clients ──

def test_elevenlabs_client_blocked():
    from packages.clients.ai_clients import ElevenLabsClient
    c = ElevenLabsClient()
    assert not c._is_configured()
    import asyncio
    result = asyncio.run(c.generate("Hello world"))
    assert not result["success"]
    assert "ELEVENLABS_API_KEY" in result["error"]


def test_heygen_client_blocked():
    from packages.clients.ai_clients import HeyGenClient
    c = HeyGenClient()
    assert not c._is_configured()
    import asyncio
    result = asyncio.run(c.generate("Test script"))
    assert not result["success"]
    assert "HEYGEN_API_KEY" in result["error"]


def test_synthesia_client_blocked():
    from packages.clients.ai_clients import SynthesiaClient
    c = SynthesiaClient()
    assert not c._is_configured()
    import asyncio
    result = asyncio.run(c.generate("Test script"))
    assert not result["success"]
    assert "SYNTHESIA_API_KEY" in result["error"]


def test_elevenlabs_voice_list_blocked():
    import asyncio

    from packages.clients.ai_clients import ElevenLabsClient
    result = asyncio.run(ElevenLabsClient().get_voices())
    assert not result["success"]


def test_heygen_avatar_list_blocked():
    import asyncio

    from packages.clients.ai_clients import HeyGenClient
    result = asyncio.run(HeyGenClient().list_avatars())
    assert not result["success"]


# ── Routing Table ──

def test_routing_avatar_tiers():
    from packages.scoring.tiered_routing_engine import route_to_provider
    assert route_to_provider("avatar", "hero") == "heygen"
    assert route_to_provider("avatar", "standard") == "did"
    assert route_to_provider("avatar", "bulk") == "synthesia"


def test_routing_voice_tiers():
    from packages.scoring.tiered_routing_engine import route_to_provider
    assert route_to_provider("voice", "hero") == "elevenlabs"
    assert route_to_provider("voice", "standard") == "fish_audio"
    assert route_to_provider("voice", "bulk") == "voxtral"


def test_routing_video_tiers():
    from packages.scoring.tiered_routing_engine import route_to_provider
    assert route_to_provider("video", "hero") == "higgsfield"
    assert route_to_provider("video", "standard") == "kling"


def test_routing_image_flux():
    from packages.scoring.tiered_routing_engine import route_to_provider
    assert route_to_provider("image", "standard") == "flux"
    assert route_to_provider("image", "hero") == "gpt_image"
    assert route_to_provider("image", "bulk") == "imagen4"


def test_routing_fallback_per_type():
    from packages.scoring.tiered_routing_engine import route_to_provider
    assert route_to_provider("video", "unknown_tier") == "kling"
    assert route_to_provider("avatar", "unknown_tier") == "did"
    assert route_to_provider("voice", "unknown_tier") == "fish_audio"
    assert route_to_provider("music", "unknown_tier") == "suno"


def test_cost_synthesia():
    from packages.scoring.tiered_routing_engine import estimate_cost
    assert estimate_cost("synthesia") == 0.40
    assert estimate_cost("elevenlabs") == 0.03
    assert estimate_cost("heygen") == 0.50


# ── All Clients Importable ──

def test_all_15_clients_importable():
    from packages.clients.ai_clients import (
        ClaudeContentClient,
        ElevenLabsClient,
        HeyGenClient,
        SynthesiaClient,
    )
    assert ClaudeContentClient is not None
    assert HeyGenClient is not None
    assert ElevenLabsClient is not None
    assert SynthesiaClient is not None


# ── Media Production Service ──

def test_media_service_importable():
    from apps.api.services.media_production_service import (
        produce_full_video,
    )
    assert produce_full_video is not None


def test_voice_client_selection():
    import asyncio

    from apps.api.services.media_production_service import _get_voice_client
    c = asyncio.run(_get_voice_client("elevenlabs"))
    from packages.clients.ai_clients import ElevenLabsClient
    assert isinstance(c, ElevenLabsClient)


def test_avatar_client_selection():
    import asyncio

    from apps.api.services.media_production_service import _get_avatar_client
    c = asyncio.run(_get_avatar_client("heygen"))
    from packages.clients.ai_clients import HeyGenClient
    assert isinstance(c, HeyGenClient)
    c2 = asyncio.run(_get_avatar_client("did"))
    from packages.clients.ai_clients import DIDClient
    assert isinstance(c2, DIDClient)
    c3 = asyncio.run(_get_avatar_client("synthesia"))
    from packages.clients.ai_clients import SynthesiaClient
    assert isinstance(c3, SynthesiaClient)
