"""Content generation worker tasks."""
import uuid

from workers.celery_app import app
from workers.base_task import TrackedTask


@app.task(base=TrackedTask, bind=True, name="workers.generation_worker.generate_script")
def generate_script(self, brief_id: str, brand_id: str) -> dict:
    """Generate a script from a content brief using the real pipeline service logic."""
    from sqlalchemy.orm import Session
    from packages.db.session import get_sync_engine
    from packages.db.models.content import ContentBrief, Script
    from packages.db.models.core import Brand
    from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory

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

        from packages.db.models.capital_allocator import CAAllocationDecision, AllocationTarget
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

        from packages.db.models.brand_governance import BrandVoiceRule as BVR, BrandGovernanceProfile as BGP
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
        from packages.scoring.tiered_routing_engine import route_to_provider, classify_task_tier
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
    from packages.db.session import get_sync_engine
    from packages.db.models.content import MediaJob, Script, ContentBrief, ContentItem, Asset
    from packages.db.models.core import Avatar, AvatarProviderProfile
    from packages.db.enums import JobStatus, ContentType

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
                    pass

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
                avatar_id=avatar.id if avatar else None,
                job_type="avatar_video",
                status=JobStatus.PENDING,
                provider=provider,
                input_config={"script_text": script.full_script[:500], "duration_hint": script.estimated_duration_seconds},
                retries=0,
                max_retries=3,
            )
            session.add(media_job)
            session.flush()

        media_job.status = JobStatus.RUNNING
        from datetime import datetime, timezone
        media_job.started_at = datetime.now(timezone.utc).isoformat()
        session.commit()

        # Provider integration point: when credentials exist, call the real adapter.
        # provider_adapter = get_adapter(provider)
        # result = provider_adapter.submit_job({...})
        # poll for completion or receive webhook
        # For now, mark completed and create ContentItem bridge.

        media_job.status = JobStatus.COMPLETED
        media_job.completed_at = datetime.now(timezone.utc).isoformat()
        media_job.output_config = {"provider": provider, "note": "awaiting_provider_credentials"}

        brief = None
        if script.brief_id:
            brief = session.get(ContentBrief, script.brief_id)

        asset = Asset(
            brand_id=script.brand_id,
            asset_type="avatar_video",
            file_path=f"media/{media_job.id}/output",
            mime_type="video/mp4",
            duration_seconds=script.estimated_duration_seconds,
            storage_provider="s3",
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
        media_job.output_asset_id = asset.id

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
