"""Autonomous Content Generation Service.

Closes the core loop: brief → AI-generated script → quality score → approved → publish.
Uses the tiered routing engine to select the right AI provider.
Zero human input required once a brief exists.
"""
from __future__ import annotations
import asyncio
import hashlib
import logging
import uuid
from typing import Any, Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.content import ContentBrief, Script, ContentItem
from packages.db.models.core import Brand
from packages.db.models.accounts import CreatorAccount
from packages.db.models.pattern_memory import WinningPatternMemory, LosingPatternMemory
from packages.db.models.promote_winner import PromotedWinnerRule
from packages.db.models.failure_family import SuppressionRule
from packages.db.models.objection_mining import ObjectionCluster
from packages.db.enums import ContentType
from packages.scoring.tiered_routing_engine import classify_task_tier, route_to_provider

logger = logging.getLogger(__name__)

SCRIPT_SYSTEM_PROMPT = """\
You are an elite content writer for social media monetization. You write scripts that \
hook attention in the first 2 seconds, deliver real value, and drive action.

RULES:
1. The HOOK must be emotionally compelling — a bold claim, surprising fact, or direct pain point.
2. The BODY must deliver genuine value — not filler. Every sentence earns the next.
3. The CTA must feel natural, not salesy. It should flow from the value delivered.
4. Match the TONE and PLATFORM style exactly. TikTok is casual/fast. YouTube is deeper. LinkedIn is professional.
5. If WINNING PATTERNS are provided, weave them into the structure naturally.
6. If LOSING PATTERNS are provided, actively avoid those approaches.
7. If an OFFER is attached, integrate it seamlessly — never feel forced.
8. Keep to the TARGET DURATION. Short-form = 30-90 seconds of spoken text. Long-form = 5-15 minutes.
9. Output ONLY the script in this exact format:

[HOOK]
(opening hook text)

[BODY]
(main content)

[CTA]
(call to action)

Do NOT include any meta-commentary, instructions, or notes. Just the script."""

CAPTION_SYSTEM_PROMPT = """\
You are an elite social media copywriter. Write a caption/post that stops the scroll, \
delivers value, and drives engagement.

RULES:
1. Open with a hook that creates curiosity or urgency.
2. Deliver the core message in a scannable format (short paragraphs, line breaks).
3. Include a clear call-to-action.
4. Add relevant hashtags at the end (5-10 for Instagram/TikTok, 3-5 for LinkedIn, 1-3 for X).
5. Match the platform's native voice and formatting conventions.
6. If an affiliate link or offer is mentioned, integrate it naturally.
7. Output ONLY the caption text. No meta-commentary."""


def _build_generation_prompt(brief: ContentBrief, brand: Optional[Brand], metadata: dict) -> str:
    """Build the full prompt for the AI provider from brief + enriched metadata."""
    parts = [f"TOPIC: {brief.title}"]

    if brief.target_platform:
        parts.append(f"PLATFORM: {brief.target_platform}")
    if brief.content_type:
        ct = brief.content_type.value if hasattr(brief.content_type, 'value') else str(brief.content_type)
        parts.append(f"CONTENT TYPE: {ct}")
    if brief.hook:
        parts.append(f"HOOK ANGLE: {brief.hook}")
    if brief.angle:
        parts.append(f"ANGLE: {brief.angle}")
    if brief.key_points and isinstance(brief.key_points, list):
        parts.append(f"KEY POINTS: {', '.join(str(p) for p in brief.key_points)}")
    if brief.tone_guidance:
        parts.append(f"TONE: {brief.tone_guidance}")
    elif brand and hasattr(brand, 'tone_of_voice') and brand.tone_of_voice:
        parts.append(f"TONE: {brand.tone_of_voice}")
    if brief.target_duration_seconds:
        parts.append(f"TARGET DURATION: {brief.target_duration_seconds} seconds")
    try:
        from packages.scoring.cta_engine import select_cta
        platform = brief.target_platform or "youtube"
        has_offer = bool(metadata.get("offer_url"))
        has_lead_magnet = bool(metadata.get("lead_magnet_url"))
        cta = select_cta(platform, has_offer=has_offer, has_lead_magnet=has_lead_magnet)
        parts.append(f"CTA STRATEGY: {cta['text']}")
        if brief.cta_strategy and brief.cta_strategy != cta["text"]:
            parts.append(f"ALTERNATIVE CTA: {brief.cta_strategy}")
    except Exception:
        if brief.cta_strategy:
            parts.append(f"CTA STRATEGY: {brief.cta_strategy}")
    if brief.monetization_integration:
        parts.append(f"MONETIZATION: {brief.monetization_integration}")

    offer_url = metadata.get("offer_url", "")
    offer_name = metadata.get("offer_name", "")
    if offer_url:
        parts.append(f"AFFILIATE OFFER: {offer_name}")
        parts.append(f"AFFILIATE LINK: {offer_url}")
        parts.append("IMPORTANT: Mention this offer/link naturally in the CTA. Do NOT make it feel forced.")

    if not offer_url:
        try:
            from packages.scoring.affiliate_link_engine import select_best_product, generate_tracking_id
            niche = metadata.get("niche") or (brand.niche if brand else "general")
            content_id = str(brief.id)
            acct_id = str(brief.creator_account_id) if brief.creator_account_id else ""
            tid = generate_tracking_id(content_id, acct_id, brief.target_platform or "")
            product = select_best_product(niche, brief.title, tid)
            if product.get("link"):
                parts.append(f"\nAFFILIATE PRODUCT: {product['name']} (${product['payout']} commission)")
                parts.append(f"AFFILIATE LINK: {product['link']}")
                parts.append(f"TRACKING ID: {tid}")
                try:
                    from packages.scoring.affiliate_placement_engine import select_placement, build_placement_instruction
                    platform = brief.target_platform or "youtube"
                    placement = select_placement(platform)
                    instruction = build_placement_instruction(placement, product["link"], product["name"])
                    parts.append(f"PLACEMENT STRATEGY: {instruction}")
                    metadata["affiliate_placement"] = placement
                except Exception:
                    parts.append("IMPORTANT: Recommend this specific product naturally. Include the link in the CTA.")
                metadata["affiliate_product"] = product
                metadata["affiliate_tracking_id"] = tid
            elif product.get("name"):
                parts.append(f"\nAFFILIATE PRODUCT: {product['name']} (${product['payout']} commission)")
                parts.append(f"Recommend {product['name']} naturally. Credentials not yet configured for auto-link.")
        except Exception:
            logger.debug("affiliate_link_enrichment_failed", exc_info=True)

    wins = metadata.get("winning_patterns", [])
    if wins:
        parts.append(f"\nWINNING PATTERNS (use these):")
        for w in wins[:5]:
            parts.append(f"  - {w.get('pattern_name', '')} (type: {w.get('pattern_type', '')}, score: {w.get('win_score', 0):.2f})")

    losses = metadata.get("losing_patterns", [])
    if losses:
        parts.append(f"\nLOSING PATTERNS (avoid these):")
        for lp in losses[:3]:
            parts.append(f"  - {lp.get('pattern_name', '')} (type: {lp.get('pattern_type', '')})")

    niche_wins = metadata.get("niche_winning_patterns", [])
    if niche_wins:
        parts.append(f"\nCROSS-PLATFORM NICHE INTELLIGENCE (validated across multiple accounts):")
        for np in niche_wins[:3]:
            parts.append(f"  - {np.get('pattern_name', '')} (type: {np.get('pattern_type', '')}, avg score: {np.get('avg_win_score', 0):.2f}, validated by {np.get('brand_count', 1)} accounts)")

    niche_losses = metadata.get("niche_losing_patterns", [])
    if niche_losses:
        parts.append(f"\nNICHE-WIDE FAILURES (avoid across all accounts):")
        for nl in niche_losses[:2]:
            parts.append(f"  - {nl.get('pattern_name', '')} (type: {nl.get('pattern_type', '')})")

    suppressions = metadata.get("suppressed_families", [])
    if suppressions:
        parts.append(f"\nSUPPRESSED (do NOT use):")
        for s in suppressions[:3]:
            parts.append(f"  - {s.get('type', '')}: {s.get('key', '')} — {s.get('reason', '')}")

    objections = metadata.get("top_objections", [])
    if objections:
        parts.append(f"\nAUDIENCE OBJECTIONS (address if relevant):")
        for o in objections[:3]:
            parts.append(f"  - {o.get('type', '')}: suggested angle: {o.get('angle', '')}")

    personality_prompt = metadata.get("personality_prompt", "")
    if personality_prompt:
        parts.append(f"\n{personality_prompt}")

    governance = metadata.get("brand_governance", {})
    if governance:
        if governance.get("tone_profile") and not personality_prompt:
            parts.append(f"\nBRAND TONE: {governance['tone_profile']}")
        banned = governance.get("banned_phrases", [])
        if banned:
            parts.append(f"BANNED PHRASES: {', '.join(banned[:10])}")
        required = governance.get("required_phrases", [])
        if required:
            parts.append(f"REQUIRED PHRASES: {', '.join(required[:5])}")

    voice = metadata.get("voice_profile", {})
    if voice:
        parts.append(f"\nVOICE PROFILE:")
        if voice.get("style"):
            parts.append(f"  Style: {voice['style']}")
        if voice.get("vocabulary_level"):
            parts.append(f"  Vocabulary: {voice['vocabulary_level']}")
        if voice.get("signature_phrases"):
            parts.append(f"  Signature phrases: {', '.join(voice['signature_phrases'][:3])}")

    try:
        from packages.scoring.hashtag_engine import select_optimal_hashtags, build_hashtag_prompt_section
        platform = brief.target_platform or "youtube"
        niche = metadata.get("niche") or (brand.niche if brand else "general")
        keywords = brief.seo_keywords if isinstance(brief.seo_keywords, list) else []
        trending = [t.get("hashtag", t.get("title", "")) for t in metadata.get("trend_signals", [])]
        hashtags = select_optimal_hashtags(niche, platform, keywords, trending)
        if hashtags:
            parts.append(f"\n{build_hashtag_prompt_section(hashtags, platform)}")
    except Exception:
        logger.debug("hashtag_enrichment_failed", exc_info=True)

    return "\n".join(parts)


async def _get_ai_client(provider_key: str, api_key: str | None = None):
    """Get the appropriate AI client for content generation.

    When *api_key* is supplied (loaded from the encrypted DB by the caller),
    it is passed directly to the client constructor.  If omitted the client
    falls back to its own os.environ lookup (transition / dev mode).
    """
    from packages.clients.ai_clients import ClaudeContentClient, GeminiFlashClient, DeepSeekClient

    if provider_key == "claude":
        return ClaudeContentClient(api_key=api_key)
    elif provider_key == "gemini_flash":
        return GeminiFlashClient(api_key=api_key)
    elif provider_key == "deepseek":
        return DeepSeekClient(api_key=api_key)
    return GeminiFlashClient(api_key=api_key)


async def _enrich_brief_metadata(db: AsyncSession, brief: ContentBrief) -> dict:
    """Pull all intelligence data into brief metadata for AI prompt construction."""
    meta = dict(brief.brief_metadata or {})

    wins = list((await db.execute(
        select(WinningPatternMemory).where(
            WinningPatternMemory.brand_id == brief.brand_id,
            WinningPatternMemory.is_active.is_(True),
        ).order_by(WinningPatternMemory.win_score.desc()).limit(5)
    )).scalars().all())
    meta["winning_patterns"] = [
        {"pattern_type": w.pattern_type, "pattern_name": w.pattern_name, "win_score": w.win_score}
        for w in wins
    ]

    losses = list((await db.execute(
        select(LosingPatternMemory).where(
            LosingPatternMemory.brand_id == brief.brand_id,
            LosingPatternMemory.is_active.is_(True),
        ).order_by(LosingPatternMemory.fail_score.desc()).limit(3)
    )).scalars().all())
    meta["losing_patterns"] = [
        {"pattern_type": lp.pattern_type, "pattern_name": lp.pattern_name, "win_score": lp.fail_score}
        for lp in losses
    ]

    suppressions = list((await db.execute(
        select(SuppressionRule).where(
            SuppressionRule.brand_id == brief.brand_id,
            SuppressionRule.is_active.is_(True),
        )
    )).scalars().all())
    if suppressions:
        meta["suppressed_families"] = [
            {"type": s.family_type, "key": s.family_key, "mode": s.suppression_mode, "reason": s.reason}
            for s in suppressions
        ]

    objections = list((await db.execute(
        select(ObjectionCluster).where(
            ObjectionCluster.brand_id == brief.brand_id,
            ObjectionCluster.is_active.is_(True),
        ).order_by(ObjectionCluster.avg_monetization_impact.desc()).limit(3)
    )).scalars().all())
    if objections:
        meta["top_objections"] = [
            {"type": o.objection_type, "impact": o.avg_monetization_impact, "angle": o.recommended_response_angle}
            for o in objections
        ]

    try:
        from apps.api.services.pattern_memory_service import compute_niche_aggregate_patterns
        brand = (await db.execute(select(Brand).where(Brand.id == brief.brand_id))).scalar_one_or_none()
        niche = brand.niche if brand else None
        if niche:
            niche_intel = await compute_niche_aggregate_patterns(db, niche, limit=5)
            cross_validated = [p for p in niche_intel.get("winning_patterns", []) if p.get("cross_validated")]
            if cross_validated:
                meta["niche_winning_patterns"] = cross_validated[:3]
            niche_losses = niche_intel.get("losing_patterns", [])
            if niche_losses:
                meta["niche_losing_patterns"] = niche_losses[:3]
    except Exception:
        logger.debug("niche_aggregate_pattern_enrichment_failed", exc_info=True)

    if brief.creator_account_id:
        try:
            from packages.db.models.ai_personality import AIPersonality, PersonalityMemory
            from packages.scoring.personality_engine import build_personality_prompt
            personality = (await db.execute(
                select(AIPersonality).where(
                    AIPersonality.account_id == brief.creator_account_id,
                    AIPersonality.is_active.is_(True),
                )
            )).scalar_one_or_none()
            if personality:
                memories = list((await db.execute(
                    select(PersonalityMemory).where(
                        PersonalityMemory.personality_id == personality.id,
                        PersonalityMemory.is_active.is_(True),
                    ).order_by(PersonalityMemory.importance_score.desc()).limit(5)
                )).scalars().all())
                p_dict = {
                    "character_name": personality.character_name,
                    "character_tagline": personality.character_tagline,
                    "character_backstory": personality.character_backstory,
                    "character_archetype": personality.character_archetype,
                    "personality_traits": personality.personality_traits or [],
                    "communication_style": personality.communication_style,
                    "energy_level": personality.energy_level,
                    "catchphrases": personality.catchphrases or [],
                    "intro_phrases": personality.intro_phrases or [],
                    "outro_phrases": personality.outro_phrases or [],
                    "forbidden_phrases": personality.forbidden_phrases or [],
                }
                mem_dicts = [{"memory_type": m.memory_type, "memory_value": m.memory_value, "importance_score": m.importance_score} for m in memories]
                meta["personality"] = p_dict
                meta["personality_prompt"] = build_personality_prompt(p_dict, mem_dicts)
                meta["character_name"] = personality.character_name
                if personality.avatar_id:
                    meta["avatar_id"] = personality.avatar_id
                if personality.higgsfield_character_id:
                    meta["higgsfield_character_id"] = personality.higgsfield_character_id
                if personality.voice_id:
                    meta["voice_id"] = personality.voice_id
                    meta["voice_provider"] = personality.voice_provider
        except Exception:
            logger.debug("personality_enrichment_failed", exc_info=True)

    if brief.creator_account_id:
        from packages.db.models.autonomous_farm import AccountVoiceProfile
        vp = (await db.execute(
            select(AccountVoiceProfile).where(
                AccountVoiceProfile.account_id == brief.creator_account_id,
                AccountVoiceProfile.is_active.is_(True),
            )
        )).scalar_one_or_none()
        if vp and vp.full_profile:
            meta["voice_profile"] = vp.full_profile

    return meta


async def generate_content_from_brief(db: AsyncSession, brief_id: uuid.UUID) -> dict[str, Any]:
    """Full autonomous content generation pipeline.

    1. Load brief + enrich metadata with intelligence data
    2. Select AI provider via tiered routing
    3. Generate script/caption via AI
    4. Create Script + ContentItem records
    5. Return result for quality scoring
    """
    from sqlalchemy import update

    claimed = (await db.execute(
        update(ContentBrief)
        .where(ContentBrief.id == brief_id, ContentBrief.status.in_(["draft", "ready", "pending_generation"]))
        .values(status="generating")
        .returning(ContentBrief.id)
    )).scalar_one_or_none()

    if not claimed:
        brief_check = (await db.execute(select(ContentBrief.status).where(ContentBrief.id == brief_id))).scalar_one_or_none()
        if not brief_check:
            return {"success": False, "error": "Brief not found"}
        return {"success": False, "error": f"Brief already claimed (status: {brief_check})"}

    await db.flush()
    brief = (await db.execute(select(ContentBrief).where(ContentBrief.id == brief_id))).scalar_one_or_none()

    brand = (await db.execute(select(Brand).where(Brand.id == brief.brand_id))).scalar_one_or_none()

    meta = await _enrich_brief_metadata(db, brief)
    brief.brief_metadata = meta
    await db.flush()

    try:
        from packages.scoring.tiered_routing_engine import estimate_cost, check_budget_remaining
        import os
        daily_budget = float(os.environ.get("DAILY_AI_BUDGET_USD", "50.0"))
        daily_spent = float(meta.get("daily_spend_usd", 0))
        budget_check = check_budget_remaining(daily_budget, daily_spent)
        if not budget_check["within_budget"]:
            brief.status = "draft"
            await db.flush()
            return {"success": False, "error": f"Daily AI budget exceeded (${daily_spent:.2f}/${daily_budget:.2f}). Resuming tomorrow."}

        tier = classify_task_tier(brief.target_platform or "youtube")
        provider_key = route_to_provider("text", tier)

        # Load credential from encrypted DB (falls back to .env)
        db_api_key = None
        if brand and hasattr(brand, "organization_id") and brand.organization_id:
            from apps.api.services.integration_manager import get_credential
            db_api_key = await get_credential(db, brand.organization_id, provider_key)

        client = await _get_ai_client(provider_key, api_key=db_api_key)

        if brief.offer_id:
            from packages.db.models.core import Offer
            offer = (await db.execute(select(Offer).where(Offer.id == brief.offer_id))).scalar_one_or_none()
            if offer:
                meta["offer_name"] = offer.name
                meta["offer_url"] = getattr(offer, "offer_url", None) or getattr(offer, "landing_url", None) or ""
                meta["offer_payout"] = float(offer.payout_amount) if offer.payout_amount else 0

        prompt = _build_generation_prompt(brief, brand, meta)

        ct = brief.content_type.value if hasattr(brief.content_type, 'value') else str(brief.content_type)
        is_video_script = ct in ("SHORT_VIDEO", "LONG_VIDEO", "REEL", "SHORT", "STORY")
        system_prompt = SCRIPT_SYSTEM_PROMPT if is_video_script else CAPTION_SYSTEM_PROMPT

        max_tokens = 2048 if is_video_script else 1024
        if hasattr(client, 'generate'):
            if provider_key == "claude":
                result = await client.generate(prompt, max_tokens=max_tokens, system=system_prompt)
            elif provider_key == "gemini_flash":
                result = await client.generate(prompt, max_tokens=max_tokens, system=system_prompt)
            else:
                full_prompt = f"{system_prompt}\n\n---\n\n{prompt}"
                result = await client.generate(full_prompt, max_tokens=max_tokens)
        else:
            brief.status = "generation_failed"
            await db.flush()
            return {"success": False, "error": f"Provider {provider_key} has no generate method"}

        if not result.get("success"):
            brief.status = "generation_failed"
            await db.flush()
            return {"success": False, "error": result.get("error", "AI generation failed"), "provider": provider_key}
    except Exception as e:
        brief.status = "generation_failed"
        await db.flush()
        logger.exception("Content generation crashed for brief %s", brief_id)
        return {"success": False, "error": f"Generation exception: {e}"}

    generated_text = result["data"]["text"]

    hook_text, body_text, cta_text = _parse_script_output(generated_text)

    prompt_hash = hashlib.sha256(f"{brief.title}:{brief.angle}:{provider_key}".encode()).hexdigest()[:16]

    existing_count = len(list((await db.execute(
        select(Script.id).where(Script.brief_id == brief.id)
    )).scalars().all()))

    script = Script(
        brief_id=brief.id,
        brand_id=brief.brand_id,
        version=existing_count + 1,
        title=f"Script v{existing_count + 1}: {brief.title}",
        hook_text=hook_text,
        body_text=body_text or generated_text,
        cta_text=cta_text,
        full_script=generated_text,
        estimated_duration_seconds=brief.target_duration_seconds or _estimate_duration(generated_text),
        word_count=len(generated_text.split()),
        generation_model=provider_key,
        generation_prompt_hash=prompt_hash,
        generation_metadata={
            "provider": provider_key,
            "tier": tier,
            "model": result["data"].get("model", provider_key),
            "tokens_used": result["data"].get("output_tokens", 0),
            "brief_id": str(brief.id),
            "trace_id": meta.get("trace_id", ""),
            "autonomous": True,
        },
        status="generated",
    )
    db.add(script)
    await db.flush()

    thumbnail_asset_id = None
    try:
        from packages.clients.ai_clients import GPTImageClient, Imagen4Client
        from packages.db.models.content import Asset
        # Load image provider credentials from encrypted DB
        _img_key = None
        _imagen_key = None
        if brand and hasattr(brand, "organization_id") and brand.organization_id:
            from apps.api.services.integration_manager import get_credential as _gc
            _img_key = await _gc(db, brand.organization_id, "openai_image")
            _imagen_key = await _gc(db, brand.organization_id, "imagen4")
        img_client = GPTImageClient(api_key=_img_key)
        if not img_client._is_configured():
            img_client = Imagen4Client(api_key=_imagen_key)
        if img_client._is_configured():
            img_prompt = f"Engaging social media thumbnail for: {brief.title}. Style: bold text overlay, vibrant colors, eye-catching. Platform: {brief.target_platform or 'youtube'}."
            img_result = await img_client.generate(img_prompt)
            if img_result.get("success") and img_result.get("data"):
                img_url = img_result["data"].get("url") or img_result["data"].get("image_url") or ""
                if img_url:
                    asset = Asset(
                        brand_id=brief.brand_id, asset_type="thumbnail",
                        file_path=img_url, mime_type="image/png",
                        storage_provider="external_url",
                        metadata_blob={"source": "ai_generated", "prompt": img_prompt[:200]},
                    )
                    db.add(asset)
                    await db.flush()
                    thumbnail_asset_id = asset.id
    except Exception:
        logger.warning("Thumbnail generation failed for brief %s, continuing without", brief_id)

    content_item = ContentItem(
        brand_id=brief.brand_id,
        brief_id=brief.id,
        script_id=script.id,
        creator_account_id=brief.creator_account_id,
        title=brief.title,
        description=generated_text[:2000],
        content_type=brief.content_type,
        platform=brief.target_platform,
        tags=brief.seo_keywords or [],
        thumbnail_asset_id=thumbnail_asset_id,
        status="draft",
        monetization_method=brief.monetization_integration,
        offer_id=brief.offer_id,
        hook_type=meta.get("winning_patterns", [{}])[0].get("pattern_type") if meta.get("winning_patterns") else None,
    )
    db.add(content_item)
    brief.status = "script_generated"
    await db.flush()

    media_result = None
    ct_val = brief.content_type.value if hasattr(brief.content_type, 'value') else str(brief.content_type)
    if ct_val in ("SHORT_VIDEO", "LONG_VIDEO", "REEL", "SHORT", "STORY"):
        try:
            from apps.api.services.media_production_service import produce_full_video
            media_result = await produce_full_video(db, content_item.id)
            if media_result.get("success"):
                logger.info("Video produced for content %s: avatar=%s voice=%s",
                            content_item.id, media_result.get("avatar_provider"), media_result.get("voice_provider"))
            else:
                logger.warning("Video production failed for content %s: %s", content_item.id, media_result.get("error"))
        except Exception:
            logger.exception("Media production crashed for content %s", content_item.id)

    return {
        "success": True,
        "script_id": str(script.id),
        "content_item_id": str(content_item.id),
        "provider": provider_key,
        "tier": tier,
        "word_count": script.word_count,
        "estimated_duration": script.estimated_duration_seconds,
        "video_produced": media_result.get("success", False) if media_result else False,
        "video_url": media_result.get("video_url", "") if media_result else "",
    }


async def score_and_approve_content(db: AsyncSession, content_item_id: uuid.UUID) -> dict[str, Any]:
    """Score content through quality governor, auto-approve if passing."""
    from apps.api.services.quality_governor_service import score_content_item

    ci = (await db.execute(select(ContentItem).where(ContentItem.id == content_item_id))).scalar_one_or_none()
    if not ci:
        return {"success": False, "error": "Content item not found"}

    result = await score_content_item(db, ci.brand_id, ci.id)

    await db.refresh(ci)
    if ci.status == "quality_blocked":
        return {"success": True, "approved": False, "status": "quality_blocked", "reason": "Quality gate failed"}

    ci.status = "approved"
    await db.flush()
    return {"success": True, "approved": True, "status": "approved"}


async def full_pipeline(db: AsyncSession, brief_id: uuid.UUID) -> dict[str, Any]:
    """Run the complete autonomous pipeline: generate → score → approve."""
    gen_result = await generate_content_from_brief(db, brief_id)
    if not gen_result.get("success"):
        return gen_result

    score_result = await score_and_approve_content(db, uuid.UUID(gen_result["content_item_id"]))

    return {
        "success": True,
        "brief_id": str(brief_id),
        "script_id": gen_result["script_id"],
        "content_item_id": gen_result["content_item_id"],
        "provider": gen_result["provider"],
        "tier": gen_result["tier"],
        "word_count": gen_result["word_count"],
        "approved": score_result.get("approved", False),
        "final_status": score_result.get("status", "unknown"),
    }


def _parse_script_output(text: str) -> tuple[str, str, str]:
    """Parse AI output into hook/body/cta sections."""
    hook = body = cta = ""
    sections = text.split("[")
    for section in sections:
        section = section.strip()
        if section.upper().startswith("HOOK]"):
            hook = section[5:].strip()
        elif section.upper().startswith("BODY]"):
            body = section[5:].strip()
        elif section.upper().startswith("CTA]"):
            cta = section[4:].strip()
    if not hook and not body:
        body = text
    return hook, body, cta


def _estimate_duration(text: str) -> int:
    """Estimate spoken duration in seconds (~150 words per minute)."""
    words = len(text.split())
    return max(15, int(words / 2.5))
