"""Media Production Service — full script-to-video orchestrator.

Chains: Script → Voice Narration → Avatar Video → B-Roll → Assembly → Assets
This is the core pipeline that transforms text scripts into publishable video content.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.content import Asset, ContentItem, Script
from packages.scoring.tiered_routing_engine import classify_task_tier, route_to_provider

logger = logging.getLogger(__name__)


async def _get_voice_client(provider_key: str):
    from packages.clients.ai_clients import ElevenLabsClient, FishAudioClient, VoxtralClient
    if provider_key == "elevenlabs":
        return ElevenLabsClient()
    elif provider_key == "fish_audio":
        return FishAudioClient()
    elif provider_key == "voxtral":
        return VoxtralClient()
    return FishAudioClient()


async def _get_avatar_client(provider_key: str):
    from packages.clients.ai_clients import DIDClient, HeyGenClient, SynthesiaClient
    if provider_key == "heygen":
        return HeyGenClient()
    elif provider_key == "did":
        return DIDClient()
    elif provider_key == "synthesia":
        return SynthesiaClient()
    return DIDClient()


async def _get_video_client(provider_key: str):
    from packages.clients.ai_clients import HiggsFieldClient, KlingClient, RunwayClient, WanClient
    if provider_key == "higgsfield":
        return HiggsFieldClient()
    elif provider_key == "runway":
        return RunwayClient()
    elif provider_key == "kling":
        return KlingClient()
    elif provider_key == "wan":
        return WanClient()
    return KlingClient()


async def produce_voice_narration(
    db: AsyncSession, script: Script, brand_id: uuid.UUID, tier: str = "standard",
    voice_id: str = "",
) -> dict[str, Any]:
    """Generate voice narration from script text."""
    provider_key = route_to_provider("voice", tier)
    client = await _get_voice_client(provider_key)

    if not client._is_configured():
        return {"success": False, "error": f"{provider_key} not configured", "provider": provider_key}

    text = script.full_script or script.body_text or ""
    if not text:
        return {"success": False, "error": "No script text to narrate"}

    if provider_key == "elevenlabs":
        result = await client.generate(text, voice_id=voice_id or "21m00Tcm4TlvDq8ikWAM")
    else:
        result = await client.generate(text, voice_id=voice_id or "default")

    if not result.get("success"):
        return {"success": False, "error": result.get("error"), "provider": provider_key}

    audio_url = ""
    data = result.get("data", {})
    if isinstance(data, dict):
        audio_url = data.get("audio_url", "") or data.get("url", "")
        if data.get("audio_bytes") and not audio_url:
            audio_url = f"memory://voice/{script.id}/{provider_key}"

    asset = Asset(
        brand_id=brand_id, asset_type="voice_narration",
        file_path=audio_url or f"voice/{script.id}/{provider_key}",
        mime_type="audio/mpeg", storage_provider="external_url" if audio_url.startswith("http") else "memory",
        metadata_blob={"provider": provider_key, "script_id": str(script.id), "char_count": len(text)},
    )
    db.add(asset)
    await db.flush()

    return {"success": True, "asset_id": str(asset.id), "audio_url": audio_url, "provider": provider_key}


async def produce_avatar_video(
    db: AsyncSession, script: Script, brand_id: uuid.UUID, tier: str = "hero",
    voice_url: str = "", avatar_id: str = "default",
) -> dict[str, Any]:
    """Generate avatar video from script + optional voice audio."""
    provider_key = route_to_provider("avatar", tier)
    await _get_avatar_client(provider_key)

    text = script.full_script or script.body_text or ""
    fallback_order = ["heygen", "did", "synthesia"]
    if provider_key in fallback_order:
        fallback_order.remove(provider_key)
    fallback_order.insert(0, provider_key)

    result = None
    for try_key in fallback_order:
        try_client = await _get_avatar_client(try_key)
        if not try_client._is_configured():
            continue
        try:
            if try_key == "heygen":
                result = await try_client.generate(text, avatar_id=avatar_id, voice_url=voice_url)
            elif try_key == "synthesia":
                result = await try_client.generate(text, avatar_id=avatar_id)
            else:
                result = await try_client.generate(text, source_url=voice_url) if voice_url else await try_client.generate(text)
            if result.get("success"):
                provider_key = try_key
                break
            logger.warning("Avatar provider %s failed: %s — trying next", try_key, result.get("error", "unknown"))
        except Exception as e:
            logger.warning("Avatar provider %s crashed: %s — trying next", try_key, str(e)[:100])
            result = {"success": False, "error": str(e)}

    if not result or not result.get("success"):
        return {"success": False, "error": result.get("error", "All avatar providers failed") if result else "No avatar provider configured"}

    video_url = result.get("data", {}).get("video_url", "") or result.get("data", {}).get("result_url", "")
    duration = result.get("data", {}).get("duration")

    asset = Asset(
        brand_id=brand_id, asset_type="avatar_video",
        file_path=video_url or f"avatar/{script.id}/{provider_key}",
        mime_type="video/mp4", duration_seconds=duration,
        storage_provider="external_url" if video_url.startswith("http") else "provider",
        metadata_blob={"provider": provider_key, "script_id": str(script.id), "avatar_id": avatar_id},
    )
    db.add(asset)
    await db.flush()

    return {"success": True, "asset_id": str(asset.id), "video_url": video_url, "provider": provider_key, "duration": duration}


async def produce_broll_clips(
    db: AsyncSession, script: Script, brand_id: uuid.UUID, tier: str = "standard", num_clips: int = 2,
) -> list[dict[str, Any]]:
    """Generate b-roll video clips from script key points."""
    provider_key = route_to_provider("video", tier)
    client = await _get_video_client(provider_key)

    if not client._is_configured():
        return []

    key_points = []
    if script.hook_text:
        key_points.append(f"Visual for: {script.hook_text[:100]}")
    body = script.body_text or ""
    sentences = [s.strip() for s in body.split(".") if len(s.strip()) > 20]
    key_points.extend(sentences[:num_clips])

    clips = []
    for i, prompt in enumerate(key_points[:num_clips]):
        try:
            result = await client.generate(prompt)
            if result.get("success"):
                video_url = result.get("data", {}).get("video_url", "") or result.get("data", {}).get("url", "")
                asset = Asset(
                    brand_id=brand_id, asset_type="broll_clip",
                    file_path=video_url or f"broll/{script.id}/{i}",
                    mime_type="video/mp4", storage_provider="external_url" if video_url and video_url.startswith("http") else "provider",
                    metadata_blob={"provider": provider_key, "clip_index": i, "prompt": prompt[:200]},
                )
                db.add(asset)
                await db.flush()
                clips.append({"success": True, "asset_id": str(asset.id), "video_url": video_url})
        except Exception:
            logger.warning("B-roll clip %d failed for script %s", i, script.id)

    return clips


async def produce_full_video(
    db: AsyncSession,
    content_item_id: uuid.UUID,
) -> dict[str, Any]:
    """Full media production pipeline for a content item.

    1. Load the script
    2. Generate voice narration (TTS)
    3. Generate avatar video (talking head)
    4. Generate b-roll clips
    5. Store all assets, link to content item
    """
    ci = (await db.execute(select(ContentItem).where(ContentItem.id == content_item_id))).scalar_one_or_none()
    if not ci:
        return {"success": False, "error": "Content item not found"}

    if not ci.script_id:
        return {"success": False, "error": "Content item has no script"}

    script = (await db.execute(select(Script).where(Script.id == ci.script_id))).scalar_one_or_none()
    if not script:
        return {"success": False, "error": "Script not found"}

    ct = ci.content_type.value if hasattr(ci.content_type, 'value') else str(ci.content_type)
    is_video = ct in ("SHORT_VIDEO", "LONG_VIDEO", "REEL", "SHORT", "STORY")
    if not is_video:
        return {"success": False, "skip": True, "reason": f"Content type {ct} does not need video production"}

    tier = classify_task_tier(ci.platform or "youtube")
    results: dict[str, Any] = {"voice": None, "avatar": None, "broll": [], "tier": tier}

    voice_result = await produce_voice_narration(db, script, ci.brand_id, tier)
    results["voice"] = voice_result
    voice_url = voice_result.get("audio_url", "") if voice_result.get("success") else ""

    avatar_result = await produce_avatar_video(db, script, ci.brand_id, tier, voice_url=voice_url)
    results["avatar"] = avatar_result

    if ct == "LONG_VIDEO":
        broll = await produce_broll_clips(db, script, ci.brand_id, tier, num_clips=3)
        results["broll"] = broll

    if avatar_result.get("success"):
        avatar_asset_id = uuid.UUID(avatar_result["asset_id"])
        ci.video_asset_id = avatar_asset_id
    elif voice_result.get("success"):
        voice_asset_id = uuid.UUID(voice_result["asset_id"])
        ci.video_asset_id = voice_asset_id

    await db.flush()

    success = avatar_result.get("success", False) or voice_result.get("success", False)
    return {
        "success": success,
        "content_item_id": str(content_item_id),
        "video_url": avatar_result.get("video_url", ""),
        "voice_provider": voice_result.get("provider", ""),
        "avatar_provider": avatar_result.get("provider", ""),
        "broll_count": len([b for b in results["broll"] if b.get("success")]),
        "tier": tier,
    }
