"""Cinema Studio service: CRUD for projects, scenes, characters, styles, generations.

Generation trigger bridges into the existing MediaJob pipeline so scene metadata
flows to real providers (Runway, HeyGen, D-ID, etc.).
"""
import uuid
from typing import Optional

import structlog
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.enums import JobStatus
from packages.db.models.cinema_studio import (
    CharacterBible,
    StudioActivity,
    StudioGeneration,
    StudioProject,
    StudioScene,
    StylePreset,
)
from packages.db.models.content import MediaJob


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _log_activity(
    db: AsyncSession,
    brand_id: uuid.UUID,
    activity_type: str,
    entity_id: uuid.UUID,
    entity_name: str,
    metadata: dict | None = None,
) -> StudioActivity:
    activity = StudioActivity(
        brand_id=brand_id,
        activity_type=activity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        activity_metadata=metadata or {},
    )
    db.add(activity)
    await db.flush()
    return activity


class NotFoundError(ValueError):
    """Raised when a record is not found — maps to HTTP 404."""


class AccessDeniedError(ValueError):
    """Raised when a record belongs to a different brand — maps to HTTP 403."""


async def _get_or_404(
    db: AsyncSession,
    model,
    record_id: uuid.UUID,
    label: str = "Record",
    brand_id: uuid.UUID | None = None,
):
    result = await db.execute(select(model).where(model.id == record_id))
    obj = result.scalar_one_or_none()
    if not obj:
        raise NotFoundError(f"{label} {record_id} not found")
    if brand_id is not None and hasattr(obj, "brand_id") and obj.brand_id is not None:
        if obj.brand_id != brand_id:
            raise AccessDeniedError(f"{label} {record_id} does not belong to this brand")
    return obj


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

async def list_projects(
    db: AsyncSession, brand_id: uuid.UUID, status: Optional[str] = None, page: int = 1,
) -> list[StudioProject]:
    q = select(StudioProject).where(StudioProject.brand_id == brand_id)
    if status:
        q = q.where(StudioProject.status == status)
    q = q.order_by(desc(StudioProject.updated_at)).offset((page - 1) * 50).limit(50)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_project(db: AsyncSession, project_id: uuid.UUID, brand_id: uuid.UUID | None = None) -> StudioProject:
    return await _get_or_404(db, StudioProject, project_id, "Project", brand_id=brand_id)


async def create_project(db: AsyncSession, brand_id: uuid.UUID, **kwargs) -> StudioProject:
    project = StudioProject(brand_id=brand_id, **kwargs)
    db.add(project)
    await db.flush()
    await db.refresh(project)
    await _log_activity(db, brand_id, "project_created", project.id, project.title)
    return project


async def update_project(db: AsyncSession, project_id: uuid.UUID, brand_id: uuid.UUID, **kwargs) -> StudioProject:
    project = await get_project(db, project_id, brand_id=brand_id)
    for k, v in kwargs.items():
        if hasattr(project, k):
            setattr(project, k, v)
    await db.flush()
    await db.refresh(project)
    return project


async def delete_project(db: AsyncSession, project_id: uuid.UUID, brand_id: uuid.UUID) -> None:
    project = await get_project(db, project_id, brand_id=brand_id)
    await db.delete(project)
    await db.flush()


# ---------------------------------------------------------------------------
# Scenes
# ---------------------------------------------------------------------------

async def list_scenes(
    db: AsyncSession, brand_id: uuid.UUID, project_id: Optional[uuid.UUID] = None, page: int = 1,
) -> list[StudioScene]:
    q = select(StudioScene).where(StudioScene.brand_id == brand_id)
    if project_id:
        q = q.where(StudioScene.project_id == project_id)
    q = q.order_by(StudioScene.order_index, StudioScene.created_at).offset((page - 1) * 50).limit(50)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_scene(db: AsyncSession, scene_id: uuid.UUID, brand_id: uuid.UUID | None = None) -> StudioScene:
    return await _get_or_404(db, StudioScene, scene_id, "Scene", brand_id=brand_id)


async def create_scene(db: AsyncSession, brand_id: uuid.UUID, **kwargs) -> StudioScene:
    scene = StudioScene(brand_id=brand_id, **kwargs)
    db.add(scene)
    await db.flush()
    await db.refresh(scene)
    await _log_activity(db, brand_id, "scene_created", scene.id, scene.title)
    return scene


async def update_scene(db: AsyncSession, scene_id: uuid.UUID, brand_id: uuid.UUID, **kwargs) -> StudioScene:
    scene = await get_scene(db, scene_id, brand_id=brand_id)
    for k, v in kwargs.items():
        if hasattr(scene, k):
            setattr(scene, k, v)
    await db.flush()
    await db.refresh(scene)
    return scene


async def delete_scene(db: AsyncSession, scene_id: uuid.UUID, brand_id: uuid.UUID) -> None:
    scene = await get_scene(db, scene_id, brand_id=brand_id)
    await db.delete(scene)
    await db.flush()


# ---------------------------------------------------------------------------
# Characters
# ---------------------------------------------------------------------------

async def list_characters(db: AsyncSession, brand_id: uuid.UUID, page: int = 1) -> list[CharacterBible]:
    q = (
        select(CharacterBible)
        .where(CharacterBible.brand_id == brand_id)
        .order_by(desc(CharacterBible.updated_at))
        .offset((page - 1) * 50)
        .limit(50)
    )
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_character(db: AsyncSession, character_id: uuid.UUID, brand_id: uuid.UUID | None = None) -> CharacterBible:
    return await _get_or_404(db, CharacterBible, character_id, "Character", brand_id=brand_id)


async def create_character(db: AsyncSession, brand_id: uuid.UUID, **kwargs) -> CharacterBible:
    char = CharacterBible(brand_id=brand_id, **kwargs)
    db.add(char)
    await db.flush()
    await db.refresh(char)
    await _log_activity(db, brand_id, "character_created", char.id, char.name)
    return char


async def update_character(db: AsyncSession, character_id: uuid.UUID, brand_id: uuid.UUID, **kwargs) -> CharacterBible:
    char = await get_character(db, character_id, brand_id=brand_id)
    for k, v in kwargs.items():
        if hasattr(char, k):
            setattr(char, k, v)
    await db.flush()
    await db.refresh(char)
    return char


async def delete_character(db: AsyncSession, character_id: uuid.UUID, brand_id: uuid.UUID) -> None:
    char = await get_character(db, character_id, brand_id=brand_id)
    await db.delete(char)
    await db.flush()


# ---------------------------------------------------------------------------
# Style Presets
# ---------------------------------------------------------------------------

async def list_styles(
    db: AsyncSession, brand_id: uuid.UUID, category: Optional[str] = None,
) -> list[StylePreset]:
    q = select(StylePreset).where(
        (StylePreset.brand_id == brand_id) | (StylePreset.brand_id.is_(None))
    )
    if category:
        q = q.where(StylePreset.category == category)
    q = q.order_by(desc(StylePreset.is_popular), StylePreset.name)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_style(db: AsyncSession, style_id: uuid.UUID, brand_id: uuid.UUID | None = None) -> StylePreset:
    return await _get_or_404(db, StylePreset, style_id, "Style Preset", brand_id=brand_id)


async def create_style(db: AsyncSession, brand_id: uuid.UUID, **kwargs) -> StylePreset:
    style = StylePreset(brand_id=brand_id, **kwargs)
    db.add(style)
    await db.flush()
    await db.refresh(style)
    await _log_activity(db, brand_id, "style_created", style.id, style.name)
    return style


async def update_style(db: AsyncSession, style_id: uuid.UUID, brand_id: uuid.UUID, **kwargs) -> StylePreset:
    style = await get_style(db, style_id, brand_id=brand_id)
    for k, v in kwargs.items():
        if hasattr(style, k):
            setattr(style, k, v)
    await db.flush()
    await db.refresh(style)
    return style


async def delete_style(db: AsyncSession, style_id: uuid.UUID, brand_id: uuid.UUID) -> None:
    style = await get_style(db, style_id, brand_id=brand_id)
    await db.delete(style)
    await db.flush()


# ---------------------------------------------------------------------------
# Generations — the bridge to MediaJob
# ---------------------------------------------------------------------------

async def list_generations(
    db: AsyncSession,
    brand_id: uuid.UUID,
    scene_id: Optional[uuid.UUID] = None,
    status: Optional[str] = None,
    page: int = 1,
) -> list[StudioGeneration]:
    q = select(StudioGeneration).where(StudioGeneration.brand_id == brand_id)
    if scene_id:
        q = q.where(StudioGeneration.scene_id == scene_id)
    if status:
        q = q.where(StudioGeneration.status == status)
    q = q.order_by(desc(StudioGeneration.created_at)).offset((page - 1) * 50).limit(50)
    result = await db.execute(q)
    return list(result.scalars().all())


async def get_generation(db: AsyncSession, generation_id: uuid.UUID, brand_id: uuid.UUID | None = None) -> StudioGeneration:
    return await _get_or_404(db, StudioGeneration, generation_id, "Generation", brand_id=brand_id)


def _build_input_config(scene: StudioScene, characters: list[CharacterBible], style: StylePreset | None) -> dict:
    """Assemble the input_config payload that a MediaProviderAdapter will consume."""
    config: dict = {
        "prompt": scene.prompt,
        "negative_prompt": scene.negative_prompt,
        "camera_shot": scene.camera_shot,
        "camera_movement": scene.camera_movement,
        "lighting": scene.lighting,
        "mood": scene.mood,
        "duration_seconds": scene.duration_seconds,
        "aspect_ratio": scene.aspect_ratio,
    }
    if characters:
        config["characters"] = [
            {
                "name": c.name,
                "description": c.description,
                "appearance": {
                    "gender": c.gender,
                    "age": c.age,
                    "ethnicity": c.ethnicity,
                    "hair_color": c.hair_color,
                    "hair_style": c.hair_style,
                    "eye_color": c.eye_color,
                    "build": c.build,
                },
                "role": c.role,
            }
            for c in characters
        ]
    if style:
        config["style"] = {
            "name": style.name,
            "category": style.category,
            "description": style.description,
        }
    return config


async def trigger_generation(
    db: AsyncSession,
    brand_id: uuid.UUID,
    scene_id: uuid.UUID,
    model: str = "runway",
    seed: int | None = None,
    steps: int = 50,
    guidance: float = 7.5,
) -> StudioGeneration:
    """Create a StudioGeneration + MediaJob from scene metadata."""
    scene = await get_scene(db, scene_id, brand_id=brand_id)

    # Resolve characters referenced by the scene
    characters: list[CharacterBible] = []
    char_ids = scene.character_ids or []
    if char_ids:
        result = await db.execute(
            select(CharacterBible).where(CharacterBible.id.in_(char_ids))
        )
        characters = list(result.scalars().all())

    # Resolve style preset
    style: StylePreset | None = None
    if scene.style_preset_id:
        style = (await db.execute(
            select(StylePreset).where(StylePreset.id == scene.style_preset_id)
        )).scalar_one_or_none()

    input_config = _build_input_config(scene, characters, style)

    media_job = MediaJob(
        brand_id=brand_id,
        script_id=None,
        avatar_id=None,
        job_type="studio_video",
        status=JobStatus.PENDING,
        provider=model,
        input_config=input_config,
        output_config={},
    )
    db.add(media_job)
    await db.flush()

    generation = StudioGeneration(
        scene_id=scene_id,
        brand_id=brand_id,
        media_job_id=media_job.id,
        status="pending",
        progress=0,
        model=model,
        seed=seed,
        steps=steps,
        guidance=guidance,
        duration_seconds=scene.duration_seconds,
    )
    db.add(generation)

    scene.status = "generating"
    await db.flush()
    await db.refresh(generation)

    await _log_activity(
        db, brand_id, "generation_started", generation.id, scene.title,
        metadata={"scene_id": str(scene_id), "model": model},
    )

    try:
        from workers.cinema_studio_worker.tasks import process_studio_generation
        process_studio_generation.delay(str(generation.id), str(brand_id))
    except Exception:
        logger.warning("studio_generation_task_dispatch_failed", exc_info=True)

    return generation


# ---------------------------------------------------------------------------
# Portrait Generation — real, uses GPTImageClient (gpt-image-1)
# ---------------------------------------------------------------------------

def _build_portrait_prompt(char: CharacterBible) -> str:
    """Build a photorealistic DSLR portrait prompt from character bible fields.

    Ported from Stori Studio portrait.ts — identical prompt engineering,
    same negative prompt list, same quality ceiling (gpt-image-1 8K).
    """
    parts: list[str] = [
        "RAW photo",
        "DSLR portrait photography",
        "Sony A7R IV",
        "85mm f/1.4 prime lens",
        "photorealistic",
        "hyperrealistic skin texture",
        "natural pores and subsurface scattering",
        "professional studio headshot",
    ]

    gender = getattr(char, "gender", "other") or "other"
    if gender == "non_binary":
        parts.append("non-binary person")
    elif gender == "male":
        parts.append("man")
    elif gender == "female":
        parts.append("woman")
    else:
        parts.append("person")

    if char.age:
        parts.append(f"{char.age} years old")
    if char.ethnicity:
        parts.append(f"{char.ethnicity} ethnicity")
    if char.hair_color and char.hair_style:
        parts.append(f"{char.hair_color} {char.hair_style} hair")
    elif char.hair_color:
        parts.append(f"{char.hair_color} hair")
    elif char.hair_style:
        parts.append(f"{char.hair_style} hair")
    if char.eye_color:
        parts.append(f"{char.eye_color} eyes")
    if char.build:
        parts.append(f"{char.build} build")
    if char.description:
        parts.append(char.description[:180])
    if char.personality:
        parts.append(f"natural expression conveying {char.personality[:80]}")

    role = getattr(char, "role", "supporting") or "supporting"
    if role == "protagonist":
        parts.append("confident heroic presence, warm approachable expression")
    elif role == "antagonist":
        parts.append("commanding intense gaze, cool composed authority")
    elif role == "supporting":
        parts.append("genuine warm expression, trustworthy presence")

    parts.extend([
        "Rembrandt three-point lighting",
        "key light at 45 degrees",
        "subtle fill light",
        "gentle rim light for depth",
        "sharp focus on eyes with natural catchlights",
        "soft bokeh background",
        "neutral gradient studio backdrop",
        "chest-up framing",
        "8K ultra-detailed",
        "editorial photography quality",
        "no text",
        "no watermarks",
        "no logos",
    ])

    negative = [
        "cartoon", "anime", "illustration", "3D render", "CGI",
        "plastic skin", "fake", "artificial", "blurry", "low quality",
        "overexposed", "underexposed", "oversaturated", "deformed",
        "distorted", "ugly", "bad anatomy", "watermark", "text",
        "logo", "uncanny valley",
    ]

    return f"{', '.join(parts)}. Avoid: {', '.join(negative)}."


async def generate_character_portrait(
    db: AsyncSession,
    character_id: uuid.UUID,
    brand_id: uuid.UUID,
) -> CharacterBible:
    """Generate a photorealistic portrait for a character using GPT Image 1.

    Uses the same prompt-engineering technique as Stori Studio's portrait.ts
    but calls through our existing GPTImageClient (packages/clients/ai_clients.py).
    """
    from packages.clients.ai_clients import GPTImageClient

    char = await get_character(db, character_id, brand_id=brand_id)
    prompt = _build_portrait_prompt(char)

    client = GPTImageClient()
    result = await client.generate(prompt, size="1024x1536", quality="high")

    if not result.get("success"):
        error = result.get("error", "Unknown portrait generation error")
        logger.error("portrait_generation_failed", character_id=str(character_id), error=error)
        raise ValueError(f"Portrait generation failed: {error}")

    image_url = result["data"]["image_url"]
    char.image_url = image_url
    await db.flush()
    await db.refresh(char)

    await _log_activity(
        db, brand_id, "portrait_generated", char.id, char.name,
        metadata={"provider": "gpt-image-1", "size": "1024x1536"},
    )

    logger.info(
        "portrait_generated",
        character_id=str(character_id),
        brand_id=str(brand_id),
        provider="gpt-image-1",
    )
    return char


# ---------------------------------------------------------------------------
# Voice Generation — real, uses ElevenLabsClient
# ---------------------------------------------------------------------------

async def generate_character_voice(
    db: AsyncSession,
    character_id: uuid.UUID,
    brand_id: uuid.UUID,
    text: str,
    voice_id: str = "21m00Tcm4TlvDq8ikWAM",
) -> dict:
    """Generate speech audio for a character using ElevenLabs TTS.

    Returns the audio bytes and metadata. The caller (router) is responsible
    for streaming them back or persisting as an Asset.
    """
    from packages.clients.ai_clients import ElevenLabsClient

    char = await get_character(db, character_id, brand_id=brand_id)

    client = ElevenLabsClient()
    result = await client.generate(text=text, voice_id=voice_id)

    if not result.get("success"):
        error = result.get("error", "Unknown voice generation error")
        logger.error("voice_generation_failed", character_id=str(character_id), error=error)
        raise ValueError(f"Voice generation failed: {error}")

    await _log_activity(
        db, brand_id, "voice_generated", char.id, char.name,
        metadata={
            "provider": "elevenlabs",
            "voice_id": voice_id,
            "char_count": len(text),
        },
    )

    logger.info(
        "voice_generated",
        character_id=str(character_id),
        brand_id=str(brand_id),
        voice_id=voice_id,
    )

    return {
        "audio_bytes": result["data"]["audio_bytes"],
        "content_type": result["data"]["content_type"],
        "voice_id": voice_id,
        "character_name": char.name,
        "char_count": len(text),
    }


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

async def dashboard_stats(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    total_projects = (await db.execute(
        select(func.count()).select_from(StudioProject).where(StudioProject.brand_id == brand_id)
    )).scalar() or 0

    total_scenes = (await db.execute(
        select(func.count()).select_from(StudioScene).where(StudioScene.brand_id == brand_id)
    )).scalar() or 0

    total_characters = (await db.execute(
        select(func.count()).select_from(CharacterBible).where(CharacterBible.brand_id == brand_id)
    )).scalar() or 0

    total_generations = (await db.execute(
        select(func.count()).select_from(StudioGeneration).where(StudioGeneration.brand_id == brand_id)
    )).scalar() or 0

    completed_generations = (await db.execute(
        select(func.count()).select_from(StudioGeneration)
        .where(StudioGeneration.brand_id == brand_id, StudioGeneration.status == "completed")
    )).scalar() or 0

    processing_generations = (await db.execute(
        select(func.count()).select_from(StudioGeneration)
        .where(StudioGeneration.brand_id == brand_id, StudioGeneration.status == "processing")
    )).scalar() or 0

    failed_generations = (await db.execute(
        select(func.count()).select_from(StudioGeneration)
        .where(StudioGeneration.brand_id == brand_id, StudioGeneration.status == "failed")
    )).scalar() or 0

    recent = (await db.execute(
        select(StudioActivity)
        .where(StudioActivity.brand_id == brand_id)
        .order_by(desc(StudioActivity.created_at))
        .limit(20)
    )).scalars().all()

    # ── Revenue path distribution from completed generations ──────
    from packages.db.models.content import ContentItem, MediaJob
    completed_jobs = (await db.execute(
        select(MediaJob)
        .where(
            MediaJob.brand_id == brand_id,
            MediaJob.job_type == "studio_video",
            MediaJob.status == "completed",
        )
        .order_by(desc(MediaJob.completed_at))
        .limit(100)
    )).scalars().all()

    lane_counts = {"heygen": 0, "compositor": 0, "unknown": 0}
    monetization_counts: dict = {}
    revenue_items = []

    for job in completed_jobs:
        out = job.output_config or {}
        lane = out.get("lane", "unknown")
        lane_counts[lane] = lane_counts.get(lane, 0) + 1

        mon = out.get("monetization", {})
        method = mon.get("monetization_method", "none")
        monetization_counts[method] = monetization_counts.get(method, 0) + 1

        if mon.get("offer_name") or mon.get("monetization_method"):
            revenue_items.append({
                "media_job_id": str(job.id),
                "lane": lane,
                "monetization_method": method,
                "offer_name": mon.get("offer_name"),
                "offer_url": mon.get("offer_url"),
                "revenue_estimate": mon.get("revenue_estimate", 0),
                "content_family": mon.get("content_family"),
            })

    # ── Publish truth — real status from content items + publish jobs ─
    from packages.db.models.buffer_distribution import BufferPublishJob

    content_statuses = (await db.execute(
        select(ContentItem.status, func.count())
        .where(ContentItem.brand_id == brand_id)
        .group_by(ContentItem.status)
    )).all()
    content_status_map = {row[0]: row[1] for row in content_statuses}

    publish_statuses = (await db.execute(
        select(BufferPublishJob.status, func.count())
        .where(BufferPublishJob.brand_id == brand_id)
        .group_by(BufferPublishJob.status)
    )).all()
    publish_status_map = {row[0]: row[1] for row in publish_statuses}

    publish_truth = {
        "content_approved": content_status_map.get("approved", 0),
        "content_published": content_status_map.get("published", 0),
        "content_pending_media": content_status_map.get("pending_media", 0),
        "content_media_complete": content_status_map.get("media_complete", 0),
        "content_qa_complete": content_status_map.get("qa_complete", 0),
        "content_draft": content_status_map.get("draft", 0),
        "publish_jobs_pending": publish_status_map.get("pending", 0),
        "publish_jobs_submitted": publish_status_map.get("submitted", 0),
        "publish_jobs_queued": publish_status_map.get("queued", 0),
        "publish_jobs_published": publish_status_map.get("published", 0),
        "publish_jobs_failed": publish_status_map.get("failed", 0),
        "publish_jobs_scheduled": publish_status_map.get("scheduled", 0),
    }

    return {
        "total_projects": total_projects,
        "total_scenes": total_scenes,
        "total_characters": total_characters,
        "total_generations": total_generations,
        "completed_generations": completed_generations,
        "processing_generations": processing_generations,
        "failed_generations": failed_generations,
        "recent_activity": list(recent),
        "lane_distribution": lane_counts,
        "monetization_distribution": monetization_counts,
        "revenue_items": revenue_items[:20],
        "publish_truth": publish_truth,
    }
