"""Content generation worker tasks."""
import logging
import uuid

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = logging.getLogger(__name__)


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.generate_script")
def generate_script(self, brief_id: str, brand_id: str) -> dict:
    """Generate a script from a content brief using the real pipeline service logic."""
    from sqlalchemy.orm import Session

    from packages.db.models.content import ContentBrief, Script
    from packages.db.models.core import Brand
    from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    with Session(engine) as session:
        brief = session.get(ContentBrief, uuid.UUID(brief_id))
        if not brief:
            raise ValueError(f"Brief {brief_id} not found")

        brand = session.get(Brand, brief.brand_id)
        existing_count = session.query(Script).filter(Script.brief_id == brief.id).count()

        top_wins = (
            session.query(WinningPatternMemory)
            .filter(
                WinningPatternMemory.brand_id == brief.brand_id,
                WinningPatternMemory.is_active.is_(True),
            )
            .order_by(WinningPatternMemory.win_score.desc())
            .limit(5)
            .all()
        )
        top_losses = (
            session.query(LosingPatternMemory)
            .filter(
                LosingPatternMemory.brand_id == brief.brand_id,
                LosingPatternMemory.is_active.is_(True),
            )
            .order_by(LosingPatternMemory.fail_score.desc())
            .limit(3)
            .all()
        )
        meta_pm = dict(brief.brief_metadata or {})
        meta_pm["winning_patterns"] = [
            {"pattern_type": w.pattern_type, "pattern_name": w.pattern_name, "win_score": w.win_score}
            for w in top_wins
        ]
        meta_pm["losing_patterns"] = [
            {"pattern_type": lp.pattern_type, "pattern_name": lp.pattern_name, "win_score": lp.fail_score}
            for lp in top_losses
        ]
        from packages.db.models.promote_winner import PromotedWinnerRule
        promo_rules = session.query(PromotedWinnerRule).filter(
            PromotedWinnerRule.brand_id == brief.brand_id,
            PromotedWinnerRule.is_active.is_(True),
        ).all()
        meta_pm["promoted_winner_rules"] = [
            {"rule_type": r.rule_type, "rule_key": r.rule_key, "rule_value": r.rule_value, "weight_boost": r.weight_boost}
            for r in promo_rules
        ]

        from packages.db.models.capital_allocator import AllocationTarget, CAAllocationDecision
        alloc_target = session.query(AllocationTarget).filter(
            AllocationTarget.brand_id == brief.brand_id,
            AllocationTarget.target_type == "platform",
            AllocationTarget.target_key.contains(brief.target_platform or ""),
            AllocationTarget.is_active.is_(True),
        ).first()
        if alloc_target:
            alloc_dec = session.query(CAAllocationDecision).filter(CAAllocationDecision.target_id == alloc_target.id, CAAllocationDecision.is_active.is_(True)).first()
            if alloc_dec:
                meta_pm["capital_allocation"] = {"provider_tier": alloc_dec.provider_tier, "budget": alloc_dec.allocated_budget, "starved": alloc_dec.starved}

        from packages.db.models.account_state_intel import AccountStateReport as ASR
        if brief.creator_account_id:
            acct_state = session.query(ASR).filter(
                ASR.account_id == brief.creator_account_id, ASR.is_active.is_(True)
            ).order_by(ASR.created_at.desc()).first()
            if acct_state:
                meta_pm["account_state"] = {
                    "state": acct_state.current_state,
                    "monetization_intensity": acct_state.monetization_intensity,
                    "posting_cadence": acct_state.posting_cadence,
                    "suitable_forms": acct_state.suitable_content_forms or [],
                    "blocked_actions": acct_state.blocked_actions or [],
                }

        from packages.db.models.objection_mining import ObjectionCluster
        top_objections = session.query(ObjectionCluster).filter(
            ObjectionCluster.brand_id == brief.brand_id, ObjectionCluster.is_active.is_(True)
        ).order_by(ObjectionCluster.avg_monetization_impact.desc()).limit(3).all()
        if top_objections:
            meta_pm["top_objections"] = [{"type": o.objection_type, "impact": o.avg_monetization_impact, "angle": o.recommended_response_angle} for o in top_objections]

        from packages.db.models.failure_family import SuppressionRule as FFRule
        ff_rules = session.query(FFRule).filter(FFRule.brand_id == brief.brand_id, FFRule.is_active.is_(True)).all()
        if ff_rules:
            meta_pm["suppressed_families"] = [{"type": r.family_type, "key": r.family_key, "mode": r.suppression_mode, "reason": r.reason} for r in ff_rules]

        from packages.db.models.campaigns import Campaign as CampModel
        from packages.db.models.landing_pages import LandingPage as LPModel
        best_camp = session.query(CampModel).filter(CampModel.brand_id == brief.brand_id, CampModel.offer_id == brief.offer_id, CampModel.is_active.is_(True)).order_by(CampModel.confidence.desc()).first() if brief.offer_id else None
        if best_camp:
            meta_pm["campaign"] = {"id": str(best_camp.id), "type": best_camp.campaign_type, "name": best_camp.campaign_name, "truth_label": best_camp.truth_label}
            if best_camp.landing_page_id:
                lp = session.get(LPModel, best_camp.landing_page_id)
                if lp:
                    meta_pm["landing_page"] = {"id": str(lp.id), "type": lp.page_type, "headline": lp.headline, "url": lp.destination_url, "truth_label": lp.truth_label}

        from packages.db.models.brand_governance import BrandGovernanceProfile as BGP
        from packages.db.models.brand_governance import BrandVoiceRule as BVR
        bg_profile = session.query(BGP).filter(BGP.brand_id == brief.brand_id, BGP.is_active.is_(True)).first()
        bg_rules = session.query(BVR).filter(BVR.brand_id == brief.brand_id, BVR.is_active.is_(True)).all()
        if bg_profile or bg_rules:
            meta_pm["brand_governance"] = {
                "tone_profile": bg_profile.tone_profile if bg_profile else None,
                "governance_level": bg_profile.governance_level if bg_profile else "standard",
                "banned_phrases": [r.rule_key for r in bg_rules if r.rule_type == "banned_phrase"],
                "required_phrases": [r.rule_key for r in bg_rules if r.rule_type == "required_phrase"],
            }

        brief.brief_metadata = meta_pm

        from packages.db.models.content_form import ContentFormRecommendation
        from packages.scoring.tiered_routing_engine import classify_task_tier, route_to_provider
        content_form_rec = session.query(ContentFormRecommendation).filter(
            ContentFormRecommendation.brand_id == brief.brand_id,
            ContentFormRecommendation.platform == (brief.target_platform or "youtube"),
            ContentFormRecommendation.is_active.is_(True),
        ).order_by(ContentFormRecommendation.confidence.desc()).first()

        selected_form = None
        selected_tier = classify_task_tier(brief.target_platform or "youtube")
        if content_form_rec:
            selected_form = content_form_rec.recommended_content_form
            meta = brief.brief_metadata or {}
            meta["content_form"] = selected_form
            meta["content_form_confidence"] = content_form_rec.confidence
            meta["avatar_mode"] = content_form_rec.avatar_mode
            meta["quality_tier"] = selected_tier
            meta["routed_text_provider"] = route_to_provider("text", selected_tier)
            brief.brief_metadata = meta

        hook = brief.hook or f"Here's what nobody tells you about {brief.title}"
        body = (
            f"Today we're breaking down: {brief.title}.\n\n"
            f"Angle: {brief.angle or 'Data-driven approach'}\n\n"
        )
        if brief.key_points and isinstance(brief.key_points, list):
            for i, point in enumerate(brief.key_points, 1):
                body += f"Point {i}: {point}\n"
        body += f"\nTone: {brief.tone_guidance or (brand.tone_of_voice if brand else 'professional')}"

        cta = brief.cta_strategy or "Check the link in the description"
        if brief.monetization_integration:
            cta += f" — {brief.monetization_integration}"

        full_script = f"[HOOK]\n{hook}\n\n[BODY]\n{body}\n\n[CTA]\n{cta}"

        import hashlib
        prompt_hash = hashlib.sha256(f"{brief.title}:{brief.angle}:{existing_count}".encode()).hexdigest()[:16]

        script = Script(
            brief_id=brief.id,
            brand_id=brief.brand_id,
            version=existing_count + 1,
            title=f"Script v{existing_count + 1}: {brief.title}",
            hook_text=hook,
            body_text=body,
            cta_text=cta,
            full_script=full_script,
            estimated_duration_seconds=brief.target_duration_seconds or 60,
            word_count=len(full_script.split()),
            generation_model="template_v1",
            generation_prompt_hash=prompt_hash,
            generation_metadata={"source": "template", "brief_id": str(brief.id), "worker": True, "content_form": selected_form, "quality_tier": selected_tier},
            status="generated",
        )
        session.add(script)
        brief.status = "script_generated"
        session.commit()
        session.refresh(script)

        return {"script_id": str(script.id), "status": "generated", "word_count": script.word_count}


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.generate_media")
def generate_media(self, script_id: str, avatar_id: str) -> dict:
    """Generate media from a script. Routes to provider, submits job, polls for completion."""
    from sqlalchemy.orm import Session

    from packages.db.enums import ContentType, JobStatus
    from packages.db.models.content import Asset, ContentBrief, ContentItem, MediaJob, Script
    from packages.db.models.core import Avatar, AvatarProviderProfile
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    with Session(engine) as session:
        script = session.get(Script, uuid.UUID(script_id))
        if not script:
            raise ValueError(f"Script {script_id} not found")

        avatar = session.get(Avatar, uuid.UUID(avatar_id)) if avatar_id and avatar_id != str(uuid.UUID(int=0)) else None
        provider = "fallback"

        if avatar:
            profiles = session.query(AvatarProviderProfile).filter(
                AvatarProviderProfile.avatar_id == avatar.id
            ).all()
            if profiles:
                try:
                    from packages.provider_clients.media_providers import select_provider
                    profile_dicts = [{
                        "provider": p.provider,
                        "capabilities": p.capabilities or {},
                        "health_status": p.health_status.value if hasattr(p.health_status, 'value') else str(p.health_status),
                        "is_primary": p.is_primary,
                        "is_fallback": p.is_fallback,
                        "cost_per_minute": p.cost_per_minute,
                    } for p in profiles]
                    provider = select_provider("async_video", profile_dicts) or "fallback"
                except Exception:
                    logger.debug("provider selection failed, using fallback", exc_info=True)

        existing_job = session.query(MediaJob).filter(
            MediaJob.script_id == script.id,
            MediaJob.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        ).first()

        if existing_job:
            media_job = existing_job
        else:
            media_job = MediaJob(
                brand_id=script.brand_id,
                script_id=script.id,
                job_type="avatar_video",
                status=JobStatus.PENDING,
                provider=provider,
                input_payload={"script_text": script.full_script[:500], "duration_hint": script.estimated_duration_seconds},
                retry_count=0,
            )
            session.add(media_job)
            session.flush()

        media_job.status = JobStatus.RUNNING
        from datetime import datetime, timezone
        media_job.dispatched_at = datetime.now(timezone.utc).isoformat()
        session.commit()

        provider_result = _call_media_provider_sync(provider, script, avatar)

        if provider_result and provider_result.get("success"):
            media_job.status = JobStatus.COMPLETED
            media_job.completed_at = datetime.now(timezone.utc).isoformat()
            media_job.output_payload = {
                "provider": provider,
                "model": provider_result.get("model", provider),
                "output_url": provider_result.get("url", ""),
                "source": "ai_provider",
            }
            media_job.output_url = provider_result.get("url", "")
        elif provider_result and provider_result.get("blocked"):
            media_job.status = JobStatus.FAILED
            media_job.error_message = provider_result.get("error", "Provider not configured")
            media_job.output_payload = {"provider": provider, "blocked": True, "error": provider_result.get("error")}
        else:
            error_msg = provider_result.get("error", "Unknown provider error") if provider_result else "No provider available"
            media_job.status = JobStatus.FAILED
            media_job.error_message = error_msg
            media_job.output_payload = {"provider": provider, "error": error_msg}

        if media_job.status != JobStatus.COMPLETED:
            session.commit()
            return {
                "media_job_id": str(media_job.id),
                "status": "failed",
                "provider": provider,
                "error": media_job.error_message or "Provider unavailable",
            }

        output_url = media_job.output_url or (media_job.output_payload or {}).get("output_url", f"media/{media_job.id}/output")

        brief = None
        if script.brief_id:
            brief = session.get(ContentBrief, script.brief_id)

        asset = Asset(
            brand_id=script.brand_id,
            asset_type="avatar_video",
            file_path=output_url,
            mime_type="video/mp4",
            duration_seconds=script.estimated_duration_seconds,
            storage_provider="external_url" if output_url.startswith("http") else "s3",
            metadata_blob={"media_job_id": str(media_job.id), "provider": provider},
        )
        session.add(asset)
        session.flush()

        item = ContentItem(
            brand_id=script.brand_id,
            brief_id=brief.id if brief else None,
            script_id=script.id,
            creator_account_id=brief.creator_account_id if brief else None,
            title=script.title or f"Content from {script_id}",
            content_type=ContentType.SHORT_VIDEO,
            video_asset_id=asset.id,
            status="media_complete",
            tags=brief.seo_keywords if brief else [],
        )
        session.add(item)
        session.flush()

        asset.content_item_id = item.id
        # Asset linkage tracked via content_item_id
        media_job.content_item_id = item.id

        if brief:
            brief.status = "media_complete"
        script.status = "media_complete"

        session.commit()
        session.refresh(media_job)

        return {
            "media_job_id": str(media_job.id),
            "content_item_id": str(item.id),
            "asset_id": str(asset.id),
            "status": "completed",
            "provider": provider,
        }


async def _call_media_provider(provider: str, script, avatar, cred_keys: dict | None = None) -> dict:
    """Call the appropriate AI media provider. Returns result dict with success/url/error.

    *cred_keys* is an optional dict mapping provider_key -> decrypted api_key,
    loaded by the caller from the encrypted DB via credential_loader.
    """
    from packages.clients.ai_clients import (
        DIDClient,
        ElevenLabsClient,
        FishAudioClient,
        HeyGenClient,
        KlingClient,
        RunwayClient,
    )

    cred_keys = cred_keys or {}
    provider_lower = provider.lower() if provider else ""
    script_text = (script.full_script or "")[:3000]

    if provider_lower in ("heygen", "heygen_avatar"):
        client = HeyGenClient(api_key=cred_keys.get("heygen"))
        if not client._is_configured():
            return {"success": False, "blocked": True, "error": "HEYGEN_API_KEY not configured"}
        avatar_id = "default"
        voice_id = ""
        if avatar and hasattr(avatar, 'heygen_avatar_id') and avatar.heygen_avatar_id:
            avatar_id = avatar.heygen_avatar_id
        result = await client.create_video(script_text, avatar_id=avatar_id, voice_id=voice_id)
        if result.get("success"):
            video_url = result.get("data", {}).get("video_url", "")
            return {"success": True, "url": video_url, "model": "heygen"}
        return result

    if provider_lower in ("d-id", "did"):
        client = DIDClient(api_key=cred_keys.get("did"))
        if not client._is_configured():
            return {"success": False, "blocked": True, "error": "DID_API_KEY not configured"}
        result = await client.generate(script_text)
        if result.get("success"):
            video_url = result.get("data", {}).get("video_url", "")
            return {"success": True, "url": video_url, "model": "d-id"}
        return result

    if provider_lower in ("runway", "runway_gen4"):
        client = RunwayClient(api_key=cred_keys.get("runway"))
        if not client._is_configured():
            return {"success": False, "blocked": True, "error": "RUNWAY_API_KEY not configured"}
        prompt = f"Create a video for: {script_text[:500]}"
        result = await client.generate(prompt)
        if result.get("success"):
            video_url = result.get("data", {}).get("video_url", "")
            return {"success": True, "url": video_url, "model": "gen4_turbo"}
        return result

    if provider_lower in ("kling", "kling_ai"):
        client = KlingClient(api_key=cred_keys.get("kling"))
        if not client._is_configured():
            return {"success": False, "blocked": True, "error": "FAL_API_KEY not configured"}
        prompt = f"Create a video for: {script_text[:500]}"
        result = await client.generate(prompt)
        if result.get("success"):
            video_url = result.get("data", {}).get("video_url", "")
            return {"success": True, "url": video_url, "model": "kling-v2"}
        return result

    if provider_lower in ("elevenlabs", "eleven_labs"):
        client = ElevenLabsClient(api_key=cred_keys.get("elevenlabs"))
        if not client._is_configured():
            return {"success": False, "blocked": True, "error": "ELEVENLABS_API_KEY not configured"}
        result = await client.generate(script_text)
        if result.get("success"):
            return {"success": True, "url": "", "model": "elevenlabs", "audio": True}
        return result

    if provider_lower in ("fish_audio", "fishaudio"):
        client = FishAudioClient(api_key=cred_keys.get("fish_audio"))
        if not client._is_configured():
            return {"success": False, "blocked": True, "error": "FISH_AUDIO_API_KEY not configured"}
        result = await client.generate(script_text)
        if result.get("success"):
            return {"success": True, "url": "", "model": "fish-audio", "audio": True}
        return result

    for ClientClass, key_name, cred_key in [
        (HeyGenClient, "HEYGEN_API_KEY", "heygen"),
        (DIDClient, "DID_API_KEY", "did"),
        (RunwayClient, "RUNWAY_API_KEY", "runway"),
    ]:
        client = ClientClass(api_key=cred_keys.get(cred_key))
        if client._is_configured():
            if isinstance(client, HeyGenClient):
                result = await client.create_video(script_text)
            else:
                result = await client.generate(script_text[:500])
            if result.get("success"):
                video_url = result.get("data", {}).get("video_url", "")
                return {"success": True, "url": video_url, "model": key_name.split("_")[0].lower()}
            return result

    return {"success": False, "blocked": True, "error": "No media provider credentials configured. Add API keys in Settings."}


def _call_media_provider_sync(provider: str, script, avatar) -> dict:
    """Synchronous wrapper for _call_media_provider.

    Loads credentials from the encrypted DB (via credential_loader) and
    passes them to _call_media_provider so every client gets its key from
    the DB rather than .env.
    """
    import asyncio

    # Pre-load all relevant media provider credentials synchronously
    cred_keys: dict[str, str] = {}
    try:
        from sqlalchemy.orm import Session as SyncSession

        from packages.clients.credential_loader import load_credential
        from packages.db.session import get_sync_engine

        engine = get_sync_engine()
        with SyncSession(engine) as cred_session:
            from packages.db.models.core import Brand
            brand = cred_session.get(Brand, script.brand_id) if script.brand_id else None
            if brand and brand.organization_id:
                for pk in ("heygen", "did", "runway", "kling", "elevenlabs", "fish_audio"):
                    key = load_credential(cred_session, brand.organization_id, pk)
                    if key:
                        cred_keys[pk] = key
    except Exception:
        logger.debug("credential_preload_failed_for_media_provider", exc_info=True)

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_call_media_provider(provider, script, avatar, cred_keys=cred_keys))
    finally:
        loop.close()


# ────────────────────────────────────────────────────────────────────────────
# ASYNC DISPATCH PATH — non-blocking media generation via submit_async +
# webhook/poll pattern.  The above synchronous tasks remain for backward
# compatibility; these new tasks are the primary path going forward.
# ────────────────────────────────────────────────────────────────────────────

# Maps provider_key → (ClientClass, category) for async dispatch routing.
_PROVIDER_CLIENT_MAP: dict[str, tuple[type, str]] = {}


def _build_provider_client_map() -> dict[str, tuple[type, str]]:
    """Lazy-build mapping so we don't import at module level."""
    if _PROVIDER_CLIENT_MAP:
        return _PROVIDER_CLIENT_MAP
    from packages.clients.ai_clients import (
        DIDClient,
        ElevenLabsClient,
        FishAudioClient,
        FluxClient,
        GPTImageClient,
        HeyGenClient,
        HiggsFieldClient,
        Imagen4Client,
        KlingClient,
        RunwayClient,
        SynthesiaClient,
        VoxtralClient,
        WanClient,
    )
    mapping = {
        "heygen": (HeyGenClient, "avatar"),
        "did": (DIDClient, "avatar"),
        "synthesia": (SynthesiaClient, "avatar"),
        "runway": (RunwayClient, "video"),
        "kling": (KlingClient, "video"),
        "higgsfield": (HiggsFieldClient, "video"),
        "wan": (WanClient, "video"),
        "elevenlabs": (ElevenLabsClient, "voice"),
        "fish_audio": (FishAudioClient, "voice"),
        "voxtral": (VoxtralClient, "voice"),
        "flux": (FluxClient, "image"),
        "openai_image": (GPTImageClient, "image"),
        "imagen4": (Imagen4Client, "image"),
    }
    _PROVIDER_CLIENT_MAP.update(mapping)
    return _PROVIDER_CLIENT_MAP


def _resolve_provider_and_credential(
    session, org_id, brand_id, job_type: str, quality_tier: str = "standard",
    preferred_provider: str | None = None,
) -> tuple[str, str | None]:
    """Synchronous provider + credential resolution.

    1. If *preferred_provider* is given and has a credential, use it.
    2. Otherwise use load_credential_for_task (DB routing).
    3. Fall back to .env for the first configured provider in the category.

    Returns (provider_key, api_key | None).
    """
    from packages.clients.credential_loader import load_credential, load_credential_for_task

    # Attempt 1: explicit provider
    if preferred_provider:
        key = load_credential(session, org_id, preferred_provider)
        if key:
            return preferred_provider, key

    # Attempt 2: DB-routed best provider for category
    category_map = {
        "avatar_video": "avatar", "avatar": "avatar",
        "video": "video", "voice": "voice", "image": "image",
    }
    category = category_map.get(job_type, job_type)
    routed = load_credential_for_task(session, org_id, category, quality_tier)
    if routed and routed.get("api_key"):
        return routed["provider_key"], routed["api_key"]

    # Attempt 3: iterate known providers for the category via credential_loader
    # (load_credential handles DB-first with .env fallback internally)
    client_map = _build_provider_client_map()
    for pkey, (_cls, cat) in client_map.items():
        if cat == category:
            cred = load_credential(session, org_id, pkey)
            if cred:
                return pkey, cred

    return preferred_provider or "fallback", None


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.generate_media_async")
def generate_media_async(
    self,
    script_id: str,
    avatar_id: str | None = None,
    job_type: str = "avatar_video",
    quality_tier: str = "standard",
    preferred_provider: str | None = None,
    next_pipeline_task: str | None = None,
    next_pipeline_args: dict | None = None,
    webhook_url: str | None = None,
) -> dict:
    """Async-dispatch media generation: submit to provider, return immediately.

    Instead of blocking until the provider finishes, this task:
    1. Resolves provider + credential (DB first, .env fallback).
    2. Creates a MediaJob row with status='dispatched'.
    3. Calls client.submit_async() with a webhook URL.
    4. Stores provider_job_id.
    5. If the provider requires polling (no webhook), schedules poll_media_job.
    6. Returns immediately with the media_job_id.
    """
    import asyncio
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

    from packages.db.models.content import Script
    from packages.db.models.core import Brand
    from packages.db.models.media_jobs import MediaJob as AsyncMediaJob
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    with Session(engine) as session:
        script = session.get(Script, uuid.UUID(script_id))
        if not script:
            raise ValueError(f"Script {script_id} not found")

        brand = session.get(Brand, script.brand_id) if script.brand_id else None
        org_id = brand.organization_id if brand else None
        if not org_id:
            raise ValueError(f"Cannot resolve org_id for script {script_id}")

        # ── Resolve provider + credential ──────────────────────────────
        provider_key, api_key = _resolve_provider_and_credential(
            session, org_id, script.brand_id,
            job_type=job_type,
            quality_tier=quality_tier,
            preferred_provider=preferred_provider,
        )

        if not api_key:
            logger.warning("generate_media_async.no_credential", provider=provider_key, org_id=str(org_id))
            # Still create the job so the caller has a reference
            media_job = AsyncMediaJob(
                org_id=org_id,
                brand_id=script.brand_id,
                script_id=script.id,
                job_type=job_type,
                provider=provider_key,
                quality_tier=quality_tier,
                status="failed",
                error_message=f"No API key available for provider '{provider_key}'. Configure in Settings > Integrations.",
                dispatched_at=datetime.now(timezone.utc),
                next_pipeline_task=next_pipeline_task,
                next_pipeline_args=next_pipeline_args,
            )
            session.add(media_job)
            session.commit()
            session.refresh(media_job)
            return {"media_job_id": str(media_job.id), "status": "failed", "error": media_job.error_message}

        # ── Create MediaJob ────────────────────────────────────────────
        script_text = (script.full_script or "")[:3000]
        media_job = AsyncMediaJob(
            org_id=org_id,
            brand_id=script.brand_id,
            script_id=script.id,
            job_type=job_type,
            provider=provider_key,
            quality_tier=quality_tier,
            status="dispatched",
            dispatched_at=datetime.now(timezone.utc),
            input_payload={
                "script_text": script_text,
                "avatar_id": avatar_id,
                "duration_hint": script.estimated_duration_seconds,
            },
            next_pipeline_task=next_pipeline_task,
            next_pipeline_args=next_pipeline_args,
        )
        session.add(media_job)
        session.flush()
        media_job_id = media_job.id  # capture before commit

        # ── Call client.submit_async() ─────────────────────────────────
        client_map = _build_provider_client_map()
        client_info = client_map.get(provider_key)
        if not client_info:
            media_job.status = "failed"
            media_job.error_message = f"No async client registered for provider '{provider_key}'"
            session.commit()
            return {"media_job_id": str(media_job_id), "status": "failed", "error": media_job.error_message}

        ClientClass, _cat = client_info
        client = ClientClass(api_key=api_key)

        # Build kwargs for submit_async
        submit_kwargs: dict = {}
        if avatar_id:
            submit_kwargs["avatar_id"] = avatar_id

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                client.submit_async(script_text, webhook_url=webhook_url, **submit_kwargs)
            )
        except Exception as exc:
            media_job.status = "failed"
            media_job.error_message = f"submit_async raised: {exc}"
            session.commit()
            return {"media_job_id": str(media_job_id), "status": "failed", "error": str(exc)}
        finally:
            loop.close()

        if not result.get("success"):
            media_job.status = "failed"
            media_job.error_message = result.get("error", "submit_async returned failure")
            session.commit()
            return {"media_job_id": str(media_job_id), "status": "failed", "error": media_job.error_message}

        data = result.get("data", {})
        provider_job_id = data.get("provider_job_id", "")
        requires_polling = data.get("requires_polling", True)

        # Some providers return the asset URL synchronously
        output_url = data.get("image_url") or data.get("video_url") or data.get("output_url") or ""

        media_job.provider_job_id = provider_job_id or None

        if output_url:
            # Provider completed synchronously (e.g. GPT Image, Imagen, sync TTS)
            media_job.status = "completed"
            media_job.output_url = output_url
            media_job.output_payload = data
            media_job.completed_at = datetime.now(timezone.utc)
        else:
            media_job.status = "processing"

        session.commit()

        # ── Schedule poll task if provider needs polling ───────────────
        if not output_url and requires_polling and provider_job_id:
            poll_media_job.apply_async(
                kwargs={
                    "media_job_id": str(media_job_id),
                    "backoff_seconds": 5,
                },
                countdown=5,
            )

        # ── If already completed, dispatch next pipeline task ─────────
        if media_job.status == "completed" and next_pipeline_task:
            app.send_task(
                next_pipeline_task,
                kwargs={
                    **(next_pipeline_args or {}),
                    "media_job_id": str(media_job_id),
                },
            )

        return {"media_job_id": str(media_job_id), "status": media_job.status}


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.poll_media_job")
def poll_media_job(self, media_job_id: str, backoff_seconds: float = 5) -> dict:
    """Poll a provider for job completion status.

    For providers that don't support webhooks this task polls in a loop
    with exponential backoff.  There is NO ceiling on the backoff interval
    — it grows without bound (2x each iteration) until the job resolves.

    Statuses from poll_status():
        - completed: update MediaJob, dispatch next_pipeline_task
        - processing: re-schedule with doubled backoff
        - failed (permanent): mark MediaJob failed, emit event
        - failed (transient / network): re-schedule with doubled backoff
    """
    import asyncio
    from datetime import datetime, timezone

    from sqlalchemy.orm import Session

    from packages.db.models.media_jobs import MediaJob as AsyncMediaJob
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    with Session(engine) as session:
        media_job = session.get(AsyncMediaJob, uuid.UUID(media_job_id))
        if not media_job:
            logger.error("poll_media_job.not_found", media_job_id=media_job_id)
            return {"media_job_id": media_job_id, "status": "not_found"}

        # Already terminal — nothing to do
        if media_job.status in ("completed", "failed"):
            return {"media_job_id": media_job_id, "status": media_job.status}

        provider_key = media_job.provider
        provider_job_id = media_job.provider_job_id
        if not provider_job_id:
            media_job.status = "failed"
            media_job.error_message = "No provider_job_id to poll"
            session.commit()
            return {"media_job_id": media_job_id, "status": "failed", "error": "no provider_job_id"}

        # ── Load credential (DB-first, .env fallback handled by credential_loader)
        from packages.clients.credential_loader import load_credential
        api_key = load_credential(session, media_job.org_id, provider_key)

        client_map = _build_provider_client_map()
        client_info = client_map.get(provider_key)
        if not client_info or not api_key:
            media_job.status = "failed"
            media_job.error_message = f"Cannot poll: no client or credential for '{provider_key}'"
            session.commit()
            return {"media_job_id": media_job_id, "status": "failed", "error": media_job.error_message}

        ClientClass, _cat = client_info
        client = ClientClass(api_key=api_key)

        # ── Call poll_status ───────────────────────────────────────────
        if not hasattr(client, "poll_status"):
            media_job.status = "failed"
            media_job.error_message = f"Provider '{provider_key}' client has no poll_status method"
            session.commit()
            return {"media_job_id": media_job_id, "status": "failed", "error": media_job.error_message}

        loop = asyncio.new_event_loop()
        try:
            poll_result = loop.run_until_complete(client.poll_status(provider_job_id))
        except Exception as exc:
            # Transient error — reschedule with backoff
            logger.warning("poll_media_job.exception", media_job_id=media_job_id, error=str(exc))
            next_backoff = backoff_seconds * 2  # NO ceiling
            media_job.retry_count += 1
            session.commit()
            poll_media_job.apply_async(
                kwargs={"media_job_id": media_job_id, "backoff_seconds": next_backoff},
                countdown=next_backoff,
            )
            return {"media_job_id": media_job_id, "status": "retrying", "next_poll_in": next_backoff}
        finally:
            loop.close()

        if not poll_result.get("success"):
            # Provider returned an error — treat as transient, reschedule
            logger.warning("poll_media_job.provider_error", media_job_id=media_job_id, error=poll_result.get("error"))
            next_backoff = backoff_seconds * 2
            media_job.retry_count += 1
            session.commit()
            poll_media_job.apply_async(
                kwargs={"media_job_id": media_job_id, "backoff_seconds": next_backoff},
                countdown=next_backoff,
            )
            return {"media_job_id": media_job_id, "status": "retrying", "next_poll_in": next_backoff}

        data = poll_result.get("data", {})
        poll_status_value = data.get("status", "processing")

        if poll_status_value == "completed":
            output_url = data.get("output_url", "")
            media_job.status = "completed"
            media_job.output_url = output_url
            media_job.output_payload = data
            media_job.completed_at = datetime.now(timezone.utc)
            session.commit()

            # Dispatch next pipeline task
            if media_job.next_pipeline_task:
                app.send_task(
                    media_job.next_pipeline_task,
                    kwargs={
                        **(media_job.next_pipeline_args or {}),
                        "media_job_id": str(media_job.id),
                    },
                )

            return {"media_job_id": media_job_id, "status": "completed", "output_url": output_url}

        if poll_status_value == "failed":
            error_msg = data.get("error", "Provider reported failure")
            # Distinguish permanent vs transient by checking for known transient patterns
            transient_patterns = ("timeout", "rate limit", "429", "503", "502", "retry", "temporary", "overloaded")
            is_transient = any(p in error_msg.lower() for p in transient_patterns)

            if is_transient:
                next_backoff = backoff_seconds * 2
                media_job.retry_count += 1
                session.commit()
                poll_media_job.apply_async(
                    kwargs={"media_job_id": media_job_id, "backoff_seconds": next_backoff},
                    countdown=next_backoff,
                )
                return {"media_job_id": media_job_id, "status": "retrying", "next_poll_in": next_backoff}

            # Permanent failure
            media_job.status = "failed"
            media_job.error_message = error_msg
            media_job.completed_at = datetime.now(timezone.utc)
            session.commit()
            return {"media_job_id": media_job_id, "status": "failed", "error": error_msg}

        # Still processing — reschedule with backoff (NO ceiling)
        next_backoff = backoff_seconds * 2
        media_job.retry_count += 1
        session.commit()
        poll_media_job.apply_async(
            kwargs={"media_job_id": media_job_id, "backoff_seconds": next_backoff},
            countdown=next_backoff,
        )
        return {"media_job_id": media_job_id, "status": "processing", "next_poll_in": next_backoff}


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.check_stale_jobs")
def check_stale_jobs(self) -> dict:
    """Periodic sweep for media jobs stuck in dispatched/processing state.

    Finds MediaJobs that have been in a non-terminal state longer than
    expected, attempts to poll the provider for a status update, and
    processes any jobs whose webhook was missed.
    """
    import asyncio
    from datetime import datetime, timedelta, timezone

    from sqlalchemy.orm import Session

    from packages.db.models.media_jobs import MediaJob as AsyncMediaJob
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    stale_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)
    recovered = 0
    failed = 0
    still_processing = 0

    with Session(engine) as session:
        stale_jobs = (
            session.query(AsyncMediaJob)
            .filter(
                AsyncMediaJob.status.in_(["dispatched", "processing"]),
                AsyncMediaJob.dispatched_at < stale_threshold,
            )
            .all()
        )

        if not stale_jobs:
            return {"checked": 0, "recovered": 0, "failed": 0, "still_processing": 0}

        for job in stale_jobs:
            if not job.provider_job_id:
                # No provider_job_id means dispatch never reached the provider
                job.status = "failed"
                job.error_message = "Stale: no provider_job_id — dispatch likely failed"
                job.completed_at = datetime.now(timezone.utc)
                failed += 1
                continue

            # Try to poll provider for current status
            from packages.clients.credential_loader import load_credential
            api_key = load_credential(session, job.org_id, job.provider)


            client_map = _build_provider_client_map()
            client_info = client_map.get(job.provider)

            if not client_info or not api_key or not hasattr(client_info[0](api_key=api_key), "poll_status"):
                # Can't poll — mark as failed if very old (>4 hours)
                age = datetime.now(timezone.utc) - (job.dispatched_at or stale_threshold)
                if age > timedelta(hours=4):
                    job.status = "failed"
                    job.error_message = f"Stale for {age}: cannot poll provider '{job.provider}'"
                    job.completed_at = datetime.now(timezone.utc)
                    failed += 1
                else:
                    still_processing += 1
                continue

            ClientClass, _cat = client_info
            client = ClientClass(api_key=api_key)

            loop = asyncio.new_event_loop()
            try:
                poll_result = loop.run_until_complete(client.poll_status(job.provider_job_id))
            except Exception:
                logger.debug("check_stale_jobs.poll_exception", media_job_id=str(job.id), exc_info=True)
                still_processing += 1
                continue
            finally:
                loop.close()

            if not poll_result.get("success"):
                still_processing += 1
                continue

            data = poll_result.get("data", {})
            status = data.get("status", "processing")

            if status == "completed":
                job.status = "completed"
                job.output_url = data.get("output_url", "")
                job.output_payload = data
                job.completed_at = datetime.now(timezone.utc)
                recovered += 1

                # Fire next pipeline task for recovered jobs
                if job.next_pipeline_task:
                    app.send_task(
                        job.next_pipeline_task,
                        kwargs={
                            **(job.next_pipeline_args or {}),
                            "media_job_id": str(job.id),
                        },
                    )

            elif status == "failed":
                job.status = "failed"
                job.error_message = data.get("error", "Provider reported failure (stale check)")
                job.completed_at = datetime.now(timezone.utc)
                failed += 1
            else:
                still_processing += 1
                # Re-enqueue a poll task to keep tracking this job
                poll_media_job.apply_async(
                    kwargs={"media_job_id": str(job.id), "backoff_seconds": 30},
                    countdown=30,
                )

        session.commit()

    return {
        "checked": len(stale_jobs),
        "recovered": recovered,
        "failed": failed,
        "still_processing": still_processing,
    }
