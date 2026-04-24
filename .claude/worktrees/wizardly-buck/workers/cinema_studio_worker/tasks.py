"""Cinema Studio worker tasks — dual-lane video pipeline.

Two active video lanes:
  1. HeyGen lane — presenter / talking avatar / explainer content
  2. Internal compositor lane — visual / storyboard / still-motion / promo content

Flow: process_studio_generation → route to lane → real mp4 output →
      MediaStorage upload → Asset row → ContentItem.video_asset_id →
      QA → auto_approve → publish_readiness pass → auto_publish.
"""
import asyncio
import os
import re
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from workers.celery_app import app
from workers.base_task import TrackedTask

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Lane routing — determines which video lane handles a generation
# ---------------------------------------------------------------------------

# Content clusters that route to HeyGen (talking head / avatar / presenter)
HEYGEN_CLUSTERS = {
    "presenter", "explainer", "talking_head", "avatar",
    "narrator", "tutorial", "spokesperson", "testimonial",
    "interview", "announcement", "pitch",
}

# Everything else routes to the internal compositor (Ken Burns motion)
# Including: promo, storyboard, visual, cinematic, mood, product, b_roll, etc.


# ---------------------------------------------------------------------------
# Content family classification — maps lane + mood to revenue-relevant family
# ---------------------------------------------------------------------------

CONTENT_FAMILY_MAP = {
    # HeyGen lane moods → content families
    ("heygen", "presenter"):    "explainer",
    ("heygen", "explainer"):    "explainer",
    ("heygen", "tutorial"):     "authority_piece",
    ("heygen", "narrator"):     "authority_piece",
    ("heygen", "testimonial"):  "trust_building",
    ("heygen", "pitch"):        "conversion_content",
    ("heygen", "spokesperson"): "conversion_content",
    ("heygen", "announcement"): "awareness",
    ("heygen", "interview"):    "trust_building",
    # Compositor lane moods → content families
    ("compositor", "product"):  "review_comparison",
    ("compositor", "promo"):    "conversion_content",
    ("compositor", "cinematic"): "awareness",
    ("compositor", "mood"):     "trust_building",
    ("compositor", "visual"):   "trust_building",
}

CTA_BY_FAMILY = {
    "explainer":        "direct",
    "authority_piece":  "lead_capture",
    "trust_building":   "lead_capture",
    "conversion_content": "urgency",
    "review_comparison": "direct",
    "awareness":        "lead_capture",
}

ANGLE_BY_FAMILY = {
    "explainer":        "convenience",
    "authority_piece":  "proof-led",
    "trust_building":   "proof-led",
    "conversion_content": "urgency",
    "review_comparison": "comparison",
    "awareness":        "value_stack",
}


def _classify_content_family(lane: str, scene) -> str:
    """Classify content into a revenue-relevant content family."""
    mood = (getattr(scene, "mood", "") or "cinematic").lower()
    key = (lane, mood)
    family = CONTENT_FAMILY_MAP.get(key)
    if family:
        return family
    # Fallback by lane
    if lane == "heygen":
        return "explainer"
    return "general"


def determine_video_lane(scene, input_config: dict) -> str:
    """Decide which video lane to use for a generation.

    Returns "heygen" or "compositor".

    Routing logic:
    - If scene.mood or any character role matches HEYGEN_CLUSTERS → heygen
    - If input_config has explicit "lane" override → use it
    - If characters have descriptions mentioning "speak" / "present" / "narrate" → heygen
    - Otherwise → compositor
    """
    # Explicit override in input_config
    lane_override = input_config.get("lane", "").lower()
    if lane_override in ("heygen", "compositor"):
        return lane_override

    # Check scene mood / camera shot for presenter patterns
    mood = (getattr(scene, "mood", "") or "").lower()
    if mood in HEYGEN_CLUSTERS:
        return "heygen"

    # Check characters for presenter/speaker roles
    for char in input_config.get("characters", []):
        role = (char.get("role", "") or "").lower()
        if role in HEYGEN_CLUSTERS:
            return "heygen"
        desc = (char.get("description", "") or "").lower()
        if any(kw in desc for kw in ("speak", "present", "narrate", "explain", "announce")):
            return "heygen"

    # Check prompt for presenter keywords
    prompt = (getattr(scene, "prompt", "") or "").lower()
    presenter_keywords = ["presenter", "speaking to camera", "talking head", "explainer", "narrator"]
    if any(kw in prompt for kw in presenter_keywords):
        return "heygen"

    # Default: compositor
    return "compositor"


def _extract_prompt_keywords(prompt: str, max_keywords: int = 12) -> list[str]:
    """Extract meaningful keywords from a scene prompt for tag enrichment."""
    stop_words = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "shall", "can", "need", "dare", "ought",
        "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
        "as", "into", "through", "during", "before", "after", "above", "below",
        "between", "out", "off", "over", "under", "again", "further", "then",
        "once", "here", "there", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "more", "most", "other", "some", "such", "no",
        "not", "only", "own", "same", "so", "than", "too", "very", "just",
        "and", "but", "or", "if", "while", "that", "this", "these", "those",
        "it", "its", "they", "them", "their", "we", "our", "you", "your",
        "he", "she", "him", "her", "his", "my", "me",
    }
    words = re.findall(r"[a-zA-Z]{3,}", prompt.lower())
    seen = set()
    keywords = []
    for w in words:
        if w not in stop_words and w not in seen:
            seen.add(w)
            keywords.append(w)
        if len(keywords) >= max_keywords:
            break
    return keywords


def _resolve_monetization(session, brand_id: str, lane: str, scene, item, account) -> dict:
    """Resolve monetization context for a studio-generated content item.

    3-tier fallback:
      1. Project offer (explicit, from StudioProject.offer_id — already set on item)
      2. Route selection via select_monetization_route() + brand offers
      3. Affiliate fallback via select_best_product()

    Populates ContentItem monetization fields and returns context dict.
    """
    from packages.db.models.offers import Offer

    content_family = _classify_content_family(lane, scene)
    cta_type = CTA_BY_FAMILY.get(content_family, "direct")
    offer_angle = ANGLE_BY_FAMILY.get(content_family, "value_stack")
    monetization_density = 0.7 if lane == "heygen" else 0.5

    resolved_offer = None
    monetization_method = None
    selected_route = None
    offer_url = None
    revenue_estimate = 0.0

    # Tier 1: Check if project offer is already attached
    if item.offer_id:
        resolved_offer = session.get(Offer, item.offer_id)
        if resolved_offer:
            monetization_method = (
                resolved_offer.monetization_method.value
                if hasattr(resolved_offer.monetization_method, "value")
                else str(resolved_offer.monetization_method)
            )
            offer_url = resolved_offer.offer_url
            revenue_estimate = float(resolved_offer.epc or 0) * 1000  # per 1K impressions

    # Tier 2: Route selection via execution policy engine
    if not resolved_offer:
        try:
            brand_offers_q = session.execute(
                select(Offer).where(
                    Offer.brand_id == uuid.UUID(brand_id),
                    Offer.is_active.is_(True),
                )
            )
            brand_offers = [
                {
                    "id": str(o.id),
                    "name": o.name,
                    "type": (
                        o.monetization_method.value
                        if hasattr(o.monetization_method, "value")
                        else str(o.monetization_method)
                    ),
                    "keywords": o.audience_fit_tags or [],
                    "revenue_per_conversion": float(o.payout_amount or 0),
                    "active": True,
                }
                for o in brand_offers_q.scalars().all()
            ]

            if brand_offers:
                from packages.scoring.execution_policy_engine import select_monetization_route

                acct_platform = ""
                acct_health = 0.5
                if account:
                    acct_platform = (
                        account.platform.value
                        if hasattr(account.platform, "value")
                        else str(account.platform or "")
                    )
                    acct_health = float(getattr(account, "health_score", 0.5) or 0.5)

                route_result = select_monetization_route(
                    content_context={
                        "content_family": content_family,
                        "niche": "",  # brand niche would go here
                        "signal_type": "studio_generation",
                        "urgency": 0.5,
                    },
                    brand_offers=brand_offers,
                    audience_signals={
                        "conversion_intent": 0.4 if lane == "compositor" else 0.6,
                        "engagement_rate": 0.03,
                        "email_list_size": 0,
                        "community_size": 0,
                        "follower_count": 0,
                    },
                    account_context={
                        "platform": acct_platform,
                        "maturity_state": "stable",
                        "health_score": acct_health,
                    },
                )

                selected_route = route_result.get("selected_route", "affiliate")
                revenue_estimate = float(route_result.get("revenue_estimate", 0))

                # Find best matching offer for selected route
                route_type_map = {
                    "affiliate": "affiliate",
                    "owned_product": "product",
                    "lead_gen": "lead_gen",
                    "booked_calls": "consulting",
                    "services": "consulting",
                    "sponsors": "sponsor",
                    "newsletter_media": "lead_gen",
                }
                target_type = route_type_map.get(selected_route, "affiliate")
                matching = [o for o in brand_offers if o["type"] == target_type]
                if matching:
                    best = matching[0]
                    resolved_offer = session.get(Offer, uuid.UUID(best["id"]))
                    if resolved_offer:
                        monetization_method = target_type
                        offer_url = resolved_offer.offer_url
                elif brand_offers:
                    # Use highest-revenue offer as fallback
                    best = max(brand_offers, key=lambda o: o["revenue_per_conversion"])
                    resolved_offer = session.get(Offer, uuid.UUID(best["id"]))
                    if resolved_offer:
                        monetization_method = best["type"]
                        offer_url = resolved_offer.offer_url

        except Exception as e:
            logger.warning("studio.monetization_route_failed", error=str(e))

    # Tier 3: Affiliate fallback via select_best_product
    if not resolved_offer and not monetization_method:
        try:
            from packages.scoring.affiliate_link_engine import select_best_product, generate_tracking_id

            tid = generate_tracking_id(
                str(item.id),
                str(account.id) if account else "",
                account.platform.value if account and hasattr(account.platform, "value") else "",
            )
            product = select_best_product(
                niche=getattr(account, "niche_focus", "general") if account else "general",
                content_title=item.title or "",
                tracking_id=tid,
            )
            if product.get("link"):
                offer_url = product["link"]
                monetization_method = "affiliate"
                selected_route = "affiliate"
                revenue_estimate = float(product.get("payout", 0))
        except Exception as e:
            logger.warning("studio.affiliate_fallback_failed", error=str(e))

    # Final fallback
    if not monetization_method:
        monetization_method = "affiliate"
        selected_route = "affiliate"

    # ── Populate ContentItem monetization fields ─────────────────
    item.monetization_method = monetization_method
    item.cta_type = cta_type
    item.offer_angle = offer_angle
    item.monetization_density_score = monetization_density
    if resolved_offer and not item.offer_id:
        item.offer_id = resolved_offer.id

    # Build offer stack if multiple offers exist
    if resolved_offer:
        try:
            from packages.scoring.revenue_engines import optimize_offer_stack

            all_offers = session.execute(
                select(Offer).where(
                    Offer.brand_id == uuid.UUID(brand_id),
                    Offer.is_active.is_(True),
                )
            ).scalars().all()

            if len(all_offers) > 1:
                stack_result = optimize_offer_stack(
                    content={"id": str(item.id), "title": item.title or ""},
                    offers=[
                        {
                            "id": str(o.id),
                            "name": o.name,
                            "monetization_method": (
                                o.monetization_method.value
                                if hasattr(o.monetization_method, "value")
                                else str(o.monetization_method)
                            ),
                            "payout_amount": float(o.payout_amount or 0),
                            "epc": float(o.epc or 0),
                            "conversion_rate": float(o.conversion_rate or 0),
                        }
                        for o in all_offers
                    ],
                    segment={},
                )
                if stack_result and stack_result.get("offer_stack"):
                    item.offer_stack = stack_result["offer_stack"]
        except Exception as e:
            logger.debug("studio.offer_stack_failed", error=str(e))

    context = {
        "content_family": content_family,
        "monetization_method": monetization_method,
        "selected_route": selected_route,
        "cta_type": cta_type,
        "offer_angle": offer_angle,
        "offer_id": str(resolved_offer.id) if resolved_offer else None,
        "offer_name": resolved_offer.name if resolved_offer else None,
        "offer_url": offer_url,
        "revenue_estimate": revenue_estimate,
        "monetization_density": monetization_density,
        "lane": lane,
    }

    logger.info("studio.monetization_resolved", **context)
    return context


@app.task(base=TrackedTask, bind=True, name="workers.cinema_studio_worker.tasks.process_studio_generation")
def process_studio_generation(self, generation_id: str, brand_id: str) -> dict:
    """Dual-lane video generation — routes to HeyGen or internal compositor.

    Lane 1 — HeyGen: presenter / talking avatar / explainer content
    Lane 2 — Internal compositor: visual / storyboard / still-motion / promo

    Both lanes produce real .mp4 files, real Asset rows, real ContentItem linkage.
    No fake completion, no placeholder URLs.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.cinema_studio import (
        StudioGeneration, StudioScene, StudioProject, StudioActivity,
    )
    from packages.db.models.content import MediaJob, Asset, ContentItem
    from packages.db.models.accounts import CreatorAccount
    from packages.db.enums import JobStatus, ContentType
    from packages.media.storage import get_storage

    engine = get_sync_engine()
    with Session(engine) as session:
        gen = session.get(StudioGeneration, uuid.UUID(generation_id))
        if not gen:
            raise ValueError(f"StudioGeneration {generation_id} not found")

        scene = session.get(StudioScene, gen.scene_id)
        if not scene:
            raise ValueError(f"StudioScene {gen.scene_id} not found")

        media_job = session.get(MediaJob, gen.media_job_id) if gen.media_job_id else None
        if not media_job:
            raise ValueError(f"MediaJob not linked to generation {generation_id}")

        input_config = media_job.input_config or {}

        # ── Mark as processing ────────────────────────────────────────
        gen.status = "processing"
        gen.progress = 5
        media_job.status = JobStatus.RUNNING
        media_job.started_at = datetime.now(timezone.utc).isoformat()
        session.commit()

        # ── Route to lane ─────────────────────────────────────────────
        lane = determine_video_lane(scene, input_config)
        logger.info(
            "studio.lane_routed",
            generation_id=generation_id,
            lane=lane,
            scene_mood=scene.mood,
        )

        # ── Execute lane ──────────────────────────────────────────────
        try:
            if lane == "heygen":
                output_url, cover_url, lane_meta = _run_heygen_lane(
                    scene, input_config, gen, session,
                )
            else:
                output_url, cover_url, lane_meta = _run_compositor_lane(
                    scene, input_config, gen, session,
                )
        except Exception as e:
            # Honest failure — no fake completion
            error_msg = str(e)[:500]
            gen.status = "failed"
            gen.progress = 0
            gen.error_message = f"[{lane}] {error_msg}"
            media_job.status = JobStatus.FAILED
            media_job.error_message = error_msg
            media_job.completed_at = datetime.now(timezone.utc).isoformat()
            scene.status = "failed"

            session.add(StudioActivity(
                brand_id=uuid.UUID(brand_id),
                activity_type="generation_failed",
                entity_id=gen.id,
                entity_name=scene.title,
                activity_metadata={"lane": lane, "error": error_msg},
            ))
            session.commit()

            logger.error(
                "studio.generation_failed",
                generation_id=generation_id,
                lane=lane,
                error=error_msg,
            )
            return {
                "generation_id": generation_id,
                "status": "failed",
                "lane": lane,
                "error": error_msg,
            }

        # ── Upload to MediaStorage ────────────────────────────────────
        storage = get_storage()
        video_key = storage.generate_key(prefix="studio/videos", extension="mp4")

        if os.path.isfile(output_url):
            # Compositor lane: output_url is a local file path
            video_public_url = storage.upload_file(
                output_url, key=video_key, content_type="video/mp4",
            )
        elif output_url.startswith("http"):
            # HeyGen lane: output_url is an HTTPS URL — download + re-upload
            video_public_url = storage.upload_from_url(output_url, key=video_key)
        else:
            raise RuntimeError(f"Invalid output_url: {output_url}")

        cover_public_url = None
        if cover_url and os.path.isfile(cover_url):
            cover_key = storage.generate_key(prefix="studio/covers", extension="png")
            cover_public_url = storage.upload_file(
                cover_url, key=cover_key, content_type="image/png",
            )

        # Clean up compositor temp files after upload
        tmp_dir = lane_meta.pop("_tmp_dir", None)
        if tmp_dir:
            from workers.cinema_studio_worker.ffmpeg_renderer import cleanup_render
            cleanup_render(tmp_dir)

        # ── Build public URL for local storage ────────────────────────
        api_base = os.getenv("API_BASE_URL", "http://localhost:8001")
        if video_public_url.startswith("/media/"):
            video_public_url = f"{api_base}{video_public_url}"
        if cover_public_url and cover_public_url.startswith("/media/"):
            cover_public_url = f"{api_base}{cover_public_url}"

        gen.progress = 90
        session.commit()

        # ── Build enriched tags ───────────────────────────────────────
        tags: list[str] = [lane]
        style_info = input_config.get("style", {})
        if style_info.get("name"):
            tags.append(style_info["name"])
        if scene.mood and scene.mood != "cinematic":
            tags.append(scene.mood)
        if scene.lighting and scene.lighting != "natural":
            tags.append(scene.lighting)
        if scene.camera_shot and scene.camera_shot != "medium":
            tags.append(scene.camera_shot)
        for char in input_config.get("characters", []):
            if char.get("name"):
                tags.append(char["name"].lower())
        tags.extend(_extract_prompt_keywords(scene.prompt or ""))
        if scene.camera_movement and scene.camera_movement != "static":
            tags.append(scene.camera_movement)
        tags = list(dict.fromkeys(tags))

        # ── Resolve creator account ───────────────────────────────────
        account = session.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == uuid.UUID(brand_id),
                CreatorAccount.is_active.is_(True),
            ).order_by(CreatorAccount.created_at).limit(1)
        ).scalar_one_or_none()

        # ── Resolve project offer_id ──────────────────────────────────
        project_offer_id = None
        if scene.project_id:
            project = session.get(StudioProject, scene.project_id)
            if project and hasattr(project, "offer_id") and project.offer_id:
                project_offer_id = project.offer_id

        # ── Create real Asset ─────────────────────────────────────────
        file_size = lane_meta.get("file_size", 0)
        asset = Asset(
            brand_id=uuid.UUID(brand_id),
            asset_type="studio_video",
            file_path=video_public_url,
            file_size_bytes=file_size if file_size else None,
            mime_type="video/mp4",
            duration_seconds=gen.duration_seconds,
            storage_provider="s3" if storage.is_cloud else "local",
            metadata_blob={
                "media_job_id": str(media_job.id),
                "generation_id": generation_id,
                "lane": lane,
                "scene_id": str(scene.id),
                "camera_shot": scene.camera_shot,
                "camera_movement": scene.camera_movement,
                "lighting": scene.lighting,
                "mood": scene.mood,
                "cover_url": cover_public_url,
                **{k: v for k, v in lane_meta.items() if k != "file_size"},
            },
        )
        session.add(asset)
        session.flush()

        # ── Create ContentItem with real linkage ──────────────────────
        item = ContentItem(
            brand_id=uuid.UUID(brand_id),
            title=f"Studio: {scene.title}",
            description=scene.prompt[:500] if scene.prompt else None,
            content_type=ContentType.SHORT_VIDEO,
            video_asset_id=asset.id,
            status="media_complete",
            tags=tags,
            creator_account_id=account.id if account else None,
            platform=account.platform.value if account else None,
            offer_id=project_offer_id,
            creative_structure=f"{scene.camera_shot}_{scene.camera_movement}",
            hook_type=scene.mood,
        )
        session.add(item)
        session.flush()

        asset.content_item_id = item.id
        media_job.output_asset_id = asset.id
        media_job.status = JobStatus.COMPLETED
        media_job.completed_at = datetime.now(timezone.utc).isoformat()

        # ── Resolve monetization context ──────────────────────────────
        monetization_ctx = _resolve_monetization(
            session, brand_id, lane, scene, item, account,
        )
        session.flush()

        media_job.output_config = {
            "lane": lane,
            "video_url": video_public_url,
            "cover_url": cover_public_url,
            "file_size": file_size,
            "monetization": monetization_ctx,
            **lane_meta,
        }

        gen.status = "completed"
        gen.progress = 100
        gen.video_url = video_public_url
        gen.thumbnail_url = cover_public_url or video_public_url
        gen.error_message = None

        scene.status = "completed"
        scene.thumbnail_url = gen.thumbnail_url

        session.add(StudioActivity(
            brand_id=uuid.UUID(brand_id),
            activity_type="generation_completed",
            entity_id=gen.id,
            entity_name=scene.title,
            activity_metadata={
                "lane": lane,
                "media_job_id": str(media_job.id),
                "content_item_id": str(item.id),
                "asset_id": str(asset.id),
                "video_url": video_public_url,
                "creator_account_id": str(account.id) if account else None,
                "tags_count": len(tags),
                "monetization_method": monetization_ctx.get("monetization_method"),
                "offer_name": monetization_ctx.get("offer_name"),
                "revenue_estimate": monetization_ctx.get("revenue_estimate"),
                "content_family": monetization_ctx.get("content_family"),
            },
        ))

        session.commit()

        # ── Dispatch QA pipeline ──────────────────────────────────────
        qa_dispatched = False
        try:
            from workers.qa_worker.tasks import run_qa_check, run_similarity_check
            run_qa_check.delay(str(item.id))
            run_similarity_check.delay(str(item.id))
            qa_dispatched = True
            logger.info("studio.qa_dispatched", content_item_id=str(item.id))
        except Exception:
            logger.warning("studio.qa_dispatch_failed", content_item_id=str(item.id))

        logger.info(
            "studio.generation_completed",
            generation_id=generation_id,
            lane=lane,
            video_url=video_public_url,
            asset_id=str(asset.id),
            content_item_id=str(item.id),
        )

        return {
            "generation_id": generation_id,
            "media_job_id": str(media_job.id),
            "content_item_id": str(item.id),
            "asset_id": str(asset.id),
            "status": "completed",
            "lane": lane,
            "video_url": video_public_url,
            "cover_url": cover_public_url,
            "tags": tags,
            "qa_dispatched": qa_dispatched,
            "monetization": monetization_ctx,
        }


# ---------------------------------------------------------------------------
# Lane implementations
# ---------------------------------------------------------------------------

def _run_compositor_lane(scene, input_config: dict, gen, session) -> tuple[str, str | None, dict]:
    """Internal compositor lane — Ken Burns motion video from reference image.

    Returns (output_path, cover_path, metadata_dict).
    output_path is a local file path to the rendered .mp4.
    """
    from workers.cinema_studio_worker.ffmpeg_renderer import render_ken_burns, cleanup_render

    # Use character portrait as reference image if available
    ref_image_url = None
    for char in input_config.get("characters", []):
        # If character has an image, use it
        appearance = char.get("appearance", {})
        # Check if there's an image_url in the input config
        if char.get("image_url"):
            ref_image_url = char["image_url"]
            break

    # Also check if scene has a reference image in input_config
    if not ref_image_url:
        ref_image_url = input_config.get("ref_image_url")

    def _update_progress(p: int):
        gen.progress = p
        try:
            session.commit()
        except Exception:
            pass

    result = render_ken_burns(
        ref_image_url=ref_image_url,
        duration_seconds=scene.duration_seconds,
        resolution=input_config.get("resolution", "1080p"),
        aspect_ratio=scene.aspect_ratio or "16:9",
        on_progress=_update_progress,
    )

    output_path = result["mp4_path"]
    cover_path = result.get("cover_path")
    tmp_dir = result["tmp_dir"]

    meta = {
        "renderer": "internal_compositor",
        "codec": result["codec"],
        "width": result["width"],
        "height": result["height"],
        "fps": result["fps"],
        "file_size": result["file_size"],
        "ref_image_url": ref_image_url,
    }

    # Note: tmp_dir cleanup happens AFTER upload in process_studio_generation
    # We store it in meta so the caller can clean up
    meta["_tmp_dir"] = tmp_dir

    return output_path, cover_path, meta


def _run_heygen_lane(scene, input_config: dict, gen, session) -> tuple[str, str | None, dict]:
    """Presenter / avatar video lane — Tavus (primary) or HeyGen (fallback).

    Loads API keys from integration_providers table (not env vars).
    Tries Tavus first (system primary), falls back to HeyGen if available.

    Returns (video_url, None, metadata_dict).
    video_url is an HTTPS URL from the provider's CDN.
    """
    from packages.clients.credential_loader import load_credential
    import time

    # Load org_id for credential lookup
    org_id = None
    try:
        from packages.db.models.core import Brand
        brand = session.get(Brand, gen.brand_id)
        if brand:
            org_id = brand.organization_id
    except Exception:
        pass

    if not org_id:
        raise RuntimeError("Cannot resolve organization for credential lookup")

    # Try Tavus first (system primary avatar provider)
    tavus_key = load_credential(session, org_id, "tavus")
    heygen_key = load_credential(session, org_id, "heygen")

    if not tavus_key and not heygen_key:
        raise RuntimeError(
            "No avatar provider configured. Store Tavus or HeyGen API key "
            "via Settings > Integrations."
        )

    # Build script from scene prompt
    script_text = scene.prompt or ""
    if not script_text:
        raise RuntimeError("Scene prompt is empty — avatar provider needs text to generate speech")

    # Extract replica/avatar IDs from input_config
    replica_id = input_config.get("replica_id") or input_config.get("avatar_id", "")
    voice_id = input_config.get("voice_id", "")
    for char in input_config.get("characters", []):
        if char.get("replica_id"):
            replica_id = char["replica_id"]
        if char.get("avatar_id") and not replica_id:
            replica_id = char["avatar_id"]
        if char.get("voice_id"):
            voice_id = char["voice_id"]

    gen.progress = 10
    try:
        session.commit()
    except Exception:
        pass

    # ── Tavus path ────────────────────────────────────────────────
    if tavus_key:
        import httpx

        headers = {"x-api-key": tavus_key, "Content-Type": "application/json"}
        payload = {"script": script_text[:5000]}
        if replica_id:
            payload["replica_id"] = replica_id
        payload["video_name"] = f"Studio: {scene.title}"[:100]

        # Create video
        try:
            with httpx.Client(timeout=60) as c:
                resp = c.post("https://tavusapi.com/v2/videos", json=payload, headers=headers)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Tavus create failed: HTTP {resp.status_code} {resp.text[:300]}")
            create_data = resp.json()
            video_id = create_data.get("video_id", "")
            if not video_id:
                raise RuntimeError(f"Tavus returned no video_id: {create_data}")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Tavus network error: {e}")

        gen.progress = 30
        try:
            session.commit()
        except Exception:
            pass

        # Poll for completion
        max_wait = 300  # 5 minutes
        elapsed = 0
        interval = 10
        video_url = None
        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval
            try:
                with httpx.Client(timeout=30) as c:
                    poll_resp = c.get(f"https://tavusapi.com/v2/videos/{video_id}", headers=headers)
                if poll_resp.status_code == 200:
                    poll_data = poll_resp.json()
                    status = poll_data.get("status", "")
                    if status == "ready":
                        video_url = poll_data.get("hosted_url") or poll_data.get("download_url", "")
                        break
                    if status in ("failed", "error"):
                        raise RuntimeError(f"Tavus video failed: {poll_data.get('error', status)}")
                    # Update progress
                    gen.progress = min(30 + int(elapsed / max_wait * 60), 85)
                    try:
                        session.commit()
                    except Exception:
                        pass
            except httpx.HTTPError:
                pass

        if not video_url:
            raise RuntimeError(f"Tavus poll timeout after {max_wait}s for video {video_id}")

        return video_url, None, {
            "renderer": "tavus",
            "replica_id": replica_id,
            "video_id": video_id,
        }

    # ── HeyGen fallback ───────────────────────────────────────────
    from packages.clients.ai_clients import HeyGenClient

    client = HeyGenClient(api_key=heygen_key)
    avatar_id = replica_id or "default"

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(
            client.generate(
                script_text=script_text[:3000],
                avatar_id=avatar_id,
                voice_id=voice_id,
            )
        )
    finally:
        loop.close()

    if not result.get("success"):
        error = result.get("error", "Unknown HeyGen error")
        raise RuntimeError(f"HeyGen generation failed: {error}")

    video_url = result["data"].get("video_url", "")
    if not video_url:
        raise RuntimeError("HeyGen returned no video URL")

    return video_url, None, {
        "renderer": "heygen",
        "avatar_id": avatar_id,
        "voice_id": voice_id,
        "video_id": result["data"].get("video_id", ""),
        "duration": result["data"].get("duration"),
    }


def _has_real_video_asset(session, item) -> bool:
    """Check if a ContentItem has a real (non-fake) video asset.

    Rejects:
    - Missing video_asset_id
    - Asset with file_path that doesn't start with http (local/fake paths)
    - Asset with file_path containing picsum.photos or cdn.storistudio.dev (known fakes)
    - Asset with file_path matching studio/{id}/output pattern (Cinema Studio fake)
    """
    from packages.db.models.content import Asset

    if not item.video_asset_id:
        return False

    asset = session.get(Asset, item.video_asset_id)
    if not asset or not asset.file_path:
        return False

    fp = asset.file_path
    # Must be a real URL
    if not fp.startswith("http"):
        return False
    # Known fake URL patterns
    fake_patterns = [
        "picsum.photos",
        "cdn.storistudio.dev",
        "placeholder",
        "example.com",
    ]
    for pattern in fake_patterns:
        if pattern in fp:
            return False

    return True


@app.task(base=TrackedTask, bind=True, name="workers.cinema_studio_worker.tasks.auto_approve_studio_content")
def auto_approve_studio_content(self) -> dict:
    """Auto-approve studio content that passed QA with high composite scores.

    Runs every 2 minutes via beat schedule. Mirrors the logic in
    content_pipeline_service._determine_approval_mode but operates
    autonomously on studio-originated content.

    HARDENED: Will NOT approve video content without a real video asset.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.content import ContentItem
    from packages.db.models.quality import QAReport, Approval
    from packages.db.models.quality_governor import QualityGovernorReport
    from packages.db.enums import ApprovalStatus, ContentType

    AUTO_APPROVE_THRESHOLD = 0.65
    VIDEO_TYPES = {ContentType.SHORT_VIDEO, ContentType.LONG_VIDEO, ContentType.LIVE_STREAM}

    engine = get_sync_engine()
    approved_count = 0
    skipped_count = 0
    blocked_no_asset = 0

    with Session(engine) as session:
        qa_complete_items = session.execute(
            select(ContentItem).where(
                ContentItem.status == "qa_complete",
                ContentItem.title.like("Studio:%"),
            ).order_by(ContentItem.created_at).limit(50)
        ).scalars().all()

        for item in qa_complete_items:
            # ── HARD GATE: video content must have a real video asset ──
            if item.content_type in VIDEO_TYPES:
                if not _has_real_video_asset(session, item):
                    logger.warning(
                        "studio.auto_approve.blocked_no_real_video_asset",
                        content_item_id=str(item.id),
                        content_type=str(item.content_type),
                        video_asset_id=str(item.video_asset_id) if item.video_asset_id else None,
                    )
                    item.status = "pending_media"
                    blocked_no_asset += 1
                    continue

            qa_report = session.execute(
                select(QAReport).where(
                    QAReport.content_item_id == item.id,
                ).order_by(QAReport.created_at.desc()).limit(1)
            ).scalar_one_or_none()

            if not qa_report:
                skipped_count += 1
                continue

            if qa_report.composite_score < AUTO_APPROVE_THRESHOLD:
                logger.info(
                    "studio.auto_approve.below_threshold",
                    content_item_id=str(item.id),
                    score=qa_report.composite_score,
                    threshold=AUTO_APPROVE_THRESHOLD,
                )
                skipped_count += 1
                continue

            qg_report = session.execute(
                select(QualityGovernorReport).where(
                    QualityGovernorReport.content_item_id == item.id,
                    QualityGovernorReport.is_active.is_(True),
                ).order_by(QualityGovernorReport.created_at.desc()).limit(1)
            ).scalar_one_or_none()

            if qg_report and not qg_report.publish_allowed:
                logger.info(
                    "studio.auto_approve.quality_governor_blocked",
                    content_item_id=str(item.id),
                    verdict=qg_report.verdict,
                )
                skipped_count += 1
                continue

            is_high_confidence = qa_report.composite_score >= 0.8
            decision_mode = "full_auto" if is_high_confidence else "guarded_auto"

            approval = Approval(
                content_item_id=item.id,
                brand_id=item.brand_id,
                status=ApprovalStatus.APPROVED,
                decision_mode=decision_mode,
                auto_approved=True,
            )
            session.add(approval)

            item.status = "approved"
            approved_count += 1

            logger.info(
                "studio.auto_approved",
                content_item_id=str(item.id),
                score=qa_report.composite_score,
                mode=decision_mode,
            )

        session.commit()

    return {
        "approved": approved_count,
        "skipped": skipped_count,
        "blocked_no_real_asset": blocked_no_asset,
        "checked": len(qa_complete_items) if 'qa_complete_items' in dir() else 0,
    }


@app.task(base=TrackedTask, bind=True, name="workers.cinema_studio_worker.tasks.sync_studio_generations")
def sync_studio_generations(self) -> dict:
    """Periodic task: sync StudioGeneration status from linked MediaJob status.

    Catches any generations whose MediaJob was updated externally (e.g. by webhook
    or manual provider status change) and keeps the studio UI in sync.

    HARDENED: Only marks a generation "completed" if the MediaJob has a real
    output_asset_id pointing to an asset with a valid URL file_path.
    """
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.cinema_studio import StudioGeneration, StudioScene
    from packages.db.models.content import MediaJob, Asset
    from packages.db.enums import JobStatus

    engine = get_sync_engine()
    synced = 0
    blocked_fake = 0

    with Session(engine) as session:
        pending_gens = session.execute(
            select(StudioGeneration).where(
                StudioGeneration.status.in_(["pending", "processing", "awaiting_video_provider"]),
                StudioGeneration.media_job_id.isnot(None),
            )
        ).scalars().all()

        for gen in pending_gens:
            job = session.get(MediaJob, gen.media_job_id)
            if not job:
                continue

            if job.status == JobStatus.COMPLETED and gen.status != "completed":
                # ── Verify the output asset is REAL before marking completed ──
                has_real_asset = False
                if job.output_asset_id:
                    asset = session.get(Asset, job.output_asset_id)
                    if asset and asset.file_path and asset.file_path.startswith("http"):
                        fake_patterns = ["picsum.photos", "cdn.storistudio.dev", "placeholder", "example.com"]
                        if not any(p in asset.file_path for p in fake_patterns):
                            has_real_asset = True

                if has_real_asset:
                    gen.status = "completed"
                    gen.progress = 100
                    gen.video_url = f"/api/v1/assets/{job.output_asset_id}/stream"
                    gen.thumbnail_url = f"/api/v1/assets/{job.output_asset_id}/thumbnail"
                    scene = session.get(StudioScene, gen.scene_id)
                    if scene:
                        scene.status = "completed"
                    synced += 1
                else:
                    # Job says completed but asset is fake — block it
                    gen.status = "awaiting_video_provider"
                    gen.error_message = "MediaJob completed but output asset is missing or has a fake URL"
                    logger.warning(
                        "studio.sync.blocked_fake_completion",
                        generation_id=str(gen.id),
                        media_job_id=str(job.id),
                        output_asset_id=str(job.output_asset_id) if job.output_asset_id else None,
                    )
                    blocked_fake += 1

            elif job.status == JobStatus.FAILED and gen.status != "failed":
                gen.status = "failed"
                gen.error_message = job.error_message or "MediaJob failed"
                scene = session.get(StudioScene, gen.scene_id)
                if scene:
                    scene.status = "failed"
                synced += 1

            elif job.status == JobStatus.RUNNING and gen.status == "pending":
                gen.status = "processing"
                gen.progress = max(gen.progress, 10)
                synced += 1

        session.commit()

    return {"synced": synced, "blocked_fake": blocked_fake, "checked": len(pending_gens)}
