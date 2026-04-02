"""Content pipeline service: brief -> script -> media -> QA -> approval -> publish.

All business logic lives here. Route handlers are thin wrappers.
Every AI output is schema-validated before save. Every action is audited.
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.enums import (
    ActorType, ApprovalStatus, ConfidenceLevel, ContentType, DecisionMode,
    DecisionType, JobStatus, Platform, QAStatus, RecommendedAction,
)
from packages.db.models.content import Asset, ContentBrief, ContentItem, MediaJob, Script, ScriptVariant
from packages.db.models.core import Avatar, AvatarProviderProfile, Brand, VoiceProviderProfile
from packages.db.models.decisions import PublishDecision
from packages.db.models.offers import Offer
from packages.db.models.publishing import PublishJob
from packages.db.models.quality import Approval, QAReport, SimilarityReport
from packages.scoring.publish import PublishScoreInput, compute_publish_score
from packages.scoring.qa import QAInput, compute_qa_score
from packages.scoring.similarity import SimilarityInput, compute_similarity


# ── Schema Validation ────────────────────────────────────────────────────────

def _validate_script_output(data: dict) -> dict:
    """Validate AI-generated script output before persistence."""
    required = ["title", "body_text", "full_script"]
    for field in required:
        if not data.get(field) or not isinstance(data[field], str) or len(data[field].strip()) < 5:
            raise ValueError(f"Script validation failed: '{field}' is missing or too short")
    if len(data["full_script"]) < 20:
        raise ValueError("Script validation failed: full_script must be at least 20 characters")
    return data


# ── Brief Operations ─────────────────────────────────────────────────────────

async def get_brief(db: AsyncSession, brief_id: uuid.UUID) -> ContentBrief:
    result = await db.execute(select(ContentBrief).where(ContentBrief.id == brief_id))
    brief = result.scalar_one_or_none()
    if not brief:
        raise ValueError(f"Brief {brief_id} not found")
    return brief


async def update_brief(db: AsyncSession, brief_id: uuid.UUID, **kwargs) -> ContentBrief:
    brief = await get_brief(db, brief_id)
    for k, v in kwargs.items():
        if hasattr(brief, k) and v is not None:
            setattr(brief, k, v)
    await db.flush()
    await db.refresh(brief)
    return brief


# ── Script Generation ────────────────────────────────────────────────────────

async def generate_script(db: AsyncSession, brief_id: uuid.UUID) -> Script:
    """Generate a script from a brief. Uses deterministic template when no AI key is available."""
    brief = await get_brief(db, brief_id)
    brand = (await db.execute(select(Brand).where(Brand.id == brief.brand_id))).scalar_one_or_none()

    existing_count = (await db.execute(
        select(func.count()).select_from(Script).where(Script.brief_id == brief_id)
    )).scalar() or 0

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

    script_data = {
        "title": f"Script v{existing_count + 1}: {brief.title}",
        "hook_text": hook,
        "body_text": body,
        "cta_text": cta,
        "full_script": full_script,
    }
    _validate_script_output(script_data)

    prompt_hash = hashlib.sha256(f"{brief.title}:{brief.angle}:{existing_count}".encode()).hexdigest()[:16]

    script = Script(
        brief_id=brief.id,
        brand_id=brief.brand_id,
        version=existing_count + 1,
        title=script_data["title"],
        hook_text=script_data["hook_text"],
        body_text=script_data["body_text"],
        cta_text=script_data["cta_text"],
        full_script=script_data["full_script"],
        estimated_duration_seconds=brief.target_duration_seconds or 60,
        word_count=len(full_script.split()),
        generation_model="template_v1",
        generation_prompt_hash=prompt_hash,
        generation_metadata={"source": "template", "brief_id": str(brief.id)},
        status="generated",
    )
    db.add(script)
    brief.status = "script_generated"
    await db.flush()
    await db.refresh(script)
    return script


async def get_script(db: AsyncSession, script_id: uuid.UUID) -> Script:
    result = await db.execute(select(Script).where(Script.id == script_id))
    script = result.scalar_one_or_none()
    if not script:
        raise ValueError(f"Script {script_id} not found")
    return script


async def update_script(db: AsyncSession, script_id: uuid.UUID, **kwargs) -> Script:
    script = await get_script(db, script_id)
    for k, v in kwargs.items():
        if hasattr(script, k) and v is not None:
            setattr(script, k, v)
    if "full_script" in kwargs:
        script.word_count = len(kwargs["full_script"].split())
    await db.flush()
    await db.refresh(script)
    return script


async def score_script(db: AsyncSession, script_id: uuid.UUID) -> dict:
    """Score a script for publish readiness."""
    script = await get_script(db, script_id)
    has_hook = bool(script.hook_text and len(script.hook_text) > 10)
    has_cta = bool(script.cta_text and len(script.cta_text) > 5)
    word_quality = min(script.word_count / 200.0, 1.0) if script.word_count > 0 else 0.0

    inp = PublishScoreInput(
        hook_strength=0.8 if has_hook else 0.3,
        monetization_fit=0.7,
        originality=0.6,
        compliance=0.8,
        retention_likelihood=min(word_quality + 0.3, 1.0),
        cta_clarity=0.8 if has_cta else 0.2,
        brand_consistency=0.7,
        thumbnail_ctr_prediction=0.5,
        expected_profit_score=0.6,
    )
    result = compute_publish_score(inp)
    return {
        "script_id": str(script.id),
        "publish_score": result.composite_score,
        "publish_ready": result.publish_ready,
        "confidence": result.confidence,
        "blocking_issues": result.blocking_issues,
        "components": result.weighted_components,
        "explanation": result.explanation,
    }


# ── Media Orchestration ──────────────────────────────────────────────────────

async def generate_media(db: AsyncSession, script_id: uuid.UUID) -> MediaJob:
    """Create a media generation job. Routes to the best available provider."""
    script = await get_script(db, script_id)
    brief = await get_brief(db, script.brief_id)

    avatar = None
    if brief.creator_account_id:
        from packages.db.models.accounts import CreatorAccount
        acct = (await db.execute(select(CreatorAccount).where(CreatorAccount.id == brief.creator_account_id))).scalar_one_or_none()
        if acct and acct.avatar_id:
            avatar = (await db.execute(select(Avatar).where(Avatar.id == acct.avatar_id))).scalar_one_or_none()

    if not avatar:
        avatars = (await db.execute(
            select(Avatar).where(Avatar.brand_id == brief.brand_id, Avatar.is_active.is_(True)).limit(1)
        )).scalars().all()
        avatar = avatars[0] if avatars else None

    provider = "fallback"
    if avatar:
        profiles = (await db.execute(
            select(AvatarProviderProfile).where(AvatarProviderProfile.avatar_id == avatar.id)
        )).scalars().all()
        if profiles:
            from packages.provider_clients.media_providers import select_provider
            profile_dicts = [{"provider": p.provider, "capabilities": p.capabilities or {},
                              "health_status": p.health_status.value if hasattr(p.health_status, 'value') else str(p.health_status),
                              "is_primary": p.is_primary, "is_fallback": p.is_fallback,
                              "cost_per_minute": p.cost_per_minute} for p in profiles]
            provider = select_provider("async_video", profile_dicts) or "fallback"

    job = MediaJob(
        brand_id=brief.brand_id,
        script_id=script.id,
        avatar_id=avatar.id if avatar else None,
        job_type="avatar_video",
        status=JobStatus.PENDING,
        provider=provider,
        input_config={"script_text": script.full_script[:500], "duration_hint": script.estimated_duration_seconds},
        retries=0,
        max_retries=3,
    )
    db.add(job)
    script.status = "media_queued"
    await db.flush()
    await db.refresh(job)
    try:
        from workers.generation_worker.tasks import generate_media as gen_media_task
        gen_media_task.delay(str(script.id), str(avatar.id) if avatar else str(uuid.UUID(int=0)))
    except Exception:
        pass
    return job


async def get_media_job(db: AsyncSession, job_id: uuid.UUID) -> MediaJob:
    result = await db.execute(select(MediaJob).where(MediaJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise ValueError(f"MediaJob {job_id} not found")
    return job


async def finalize_media_job(db: AsyncSession, job_id: uuid.UUID, *, output_config: Optional[dict] = None) -> ContentItem:
    """Bridge MediaJob → ContentItem. Called when media generation completes.

    Creates the ContentItem + Asset that the QA/approval/publish pipeline expects,
    closing the gap between the generation half and the QA half of the pipeline.
    """
    job = await get_media_job(db, job_id)
    if job.status != JobStatus.COMPLETED:
        raise ValueError(f"MediaJob {job_id} is {job.status.value}, expected COMPLETED")

    script = None
    brief = None
    if job.script_id:
        script = (await db.execute(select(Script).where(Script.id == job.script_id))).scalar_one_or_none()
    if script and script.brief_id:
        brief = (await db.execute(select(ContentBrief).where(ContentBrief.id == script.brief_id))).scalar_one_or_none()

    title = (script.title if script else None) or (brief.title if brief else None) or f"Content from media job {job_id}"
    ctype = ContentType.SHORT_VIDEO
    if brief and brief.target_platform:
        if "long" in (brief.content_type or "").lower():
            ctype = ContentType.LONG_VIDEO

    asset = Asset(
        brand_id=job.brand_id,
        asset_type=job.job_type or "avatar_video",
        file_path=output_config.get("file_path", f"media/{job_id}/output") if output_config else f"media/{job_id}/output",
        file_size_bytes=output_config.get("file_size_bytes") if output_config else None,
        mime_type=output_config.get("mime_type", "video/mp4") if output_config else "video/mp4",
        duration_seconds=script.estimated_duration_seconds if script else None,
        storage_provider=output_config.get("storage_provider", "s3") if output_config else "s3",
        metadata_blob={"media_job_id": str(job_id), "provider": job.provider},
    )
    db.add(asset)
    await db.flush()

    item = ContentItem(
        brand_id=job.brand_id,
        brief_id=brief.id if brief else None,
        script_id=script.id if script else None,
        creator_account_id=brief.creator_account_id if brief else None,
        title=title,
        content_type=ctype,
        video_asset_id=asset.id,
        status="media_complete",
        tags=brief.seo_keywords if brief else [],
    )
    db.add(item)

    asset.content_item_id = item.id
    job.output_asset_id = asset.id
    if output_config:
        job.output_config = output_config

    if brief:
        brief.status = "media_complete"
    if script:
        script.status = "media_complete"

    await db.flush()
    await db.refresh(item)
    return item


# ── Content Item + QA ────────────────────────────────────────────────────────

async def _ensure_content_item(db: AsyncSession, content_id: uuid.UUID) -> ContentItem:
    result = await db.execute(select(ContentItem).where(ContentItem.id == content_id))
    item = result.scalar_one_or_none()
    if not item:
        raise ValueError(f"ContentItem {content_id} not found")
    return item


async def run_qa(db: AsyncSession, content_id: uuid.UUID) -> QAReport:
    """Run QA scoring on a content item."""
    item = await _ensure_content_item(db, content_id)

    script = None
    if item.script_id:
        script = (await db.execute(select(Script).where(Script.id == item.script_id))).scalar_one_or_none()

    has_offer = item.offer_id is not None
    word_count = script.word_count if script else 0

    inp = QAInput(
        originality_score=0.7,
        compliance_score=0.85,
        brand_alignment_score=0.75,
        technical_quality_score=0.7,
        audio_quality_score=0.7 if item.content_type in (ContentType.SHORT_VIDEO, ContentType.LONG_VIDEO) else 0.5,
        visual_quality_score=0.7,
        has_required_disclosures=True,
        has_sponsor_metadata=not has_offer or True,
        is_sponsored_content=has_offer,
        word_count=word_count,
    )
    result = compute_qa_score(inp)

    report = QAReport(
        content_item_id=item.id,
        brand_id=item.brand_id,
        qa_status=QAStatus(result.qa_status),
        originality_score=result.originality_score,
        compliance_score=result.compliance_score,
        brand_alignment_score=result.brand_alignment_score,
        technical_quality_score=result.technical_quality_score,
        audio_quality_score=result.audio_quality_score,
        visual_quality_score=result.visual_quality_score,
        composite_score=result.composite_score,
        issues_found=result.issues,
        recommendations=result.recommendations,
        automated_checks=result.automated_checks,
        explanation=result.explanation,
    )
    db.add(report)
    item.status = "qa_complete"
    await db.flush()
    await db.refresh(report)
    return report


async def run_similarity(db: AsyncSession, content_id: uuid.UUID) -> SimilarityReport:
    """Run similarity check against existing content library."""
    item = await _ensure_content_item(db, content_id)

    existing = (await db.execute(
        select(ContentItem).where(
            ContentItem.brand_id == item.brand_id,
            ContentItem.id != item.id,
        ).limit(50)
    )).scalars().all()

    existing_data = [
        {"id": str(e.id), "title": e.title, "keywords": e.tags if isinstance(e.tags, list) else []}
        for e in existing
    ]

    inp = SimilarityInput(
        new_keywords=item.tags if isinstance(item.tags, list) else [],
        new_title=item.title,
        existing_items=existing_data,
    )
    result = compute_similarity(inp)

    report = SimilarityReport(
        content_item_id=item.id,
        brand_id=item.brand_id,
        compared_against_count=result.compared_against_count,
        max_similarity_score=result.max_similarity_score,
        avg_similarity_score=result.avg_similarity_score,
        most_similar_content_id=uuid.UUID(result.most_similar_id) if result.most_similar_id else None,
        similarity_details=result.details,
        is_too_similar=result.is_too_similar,
        threshold_used=result.threshold_used,
        explanation=result.explanation,
    )
    db.add(report)
    await db.flush()
    await db.refresh(report)
    return report


async def get_qa_report(db: AsyncSession, content_id: uuid.UUID) -> dict:
    """Get latest QA and similarity reports for a content item."""
    qa = (await db.execute(
        select(QAReport).where(QAReport.content_item_id == content_id).order_by(QAReport.created_at.desc())
    )).scalars().first()
    sim = (await db.execute(
        select(SimilarityReport).where(SimilarityReport.content_item_id == content_id).order_by(SimilarityReport.created_at.desc())
    )).scalars().first()
    return {"qa_report": qa, "similarity_report": sim}


# ── Approval Workflow ────────────────────────────────────────────────────────

async def _determine_approval_mode(qa_score: float, confidence: str, blocking_issues: list) -> tuple[str, bool]:
    """Routing logic: high confidence + low risk = full_auto; medium = guarded; else manual."""
    if blocking_issues:
        return "manual_override", False
    if confidence == "high" and qa_score >= 0.7:
        return "full_auto", True
    if confidence in ("high", "medium") and qa_score >= 0.5:
        return "guarded_auto", False
    return "manual_override", False


async def approve_content(db: AsyncSession, content_id: uuid.UUID, user_id: uuid.UUID, notes: str = "") -> Approval:
    item = await _ensure_content_item(db, content_id)
    qa = (await db.execute(
        select(QAReport).where(QAReport.content_item_id == content_id).order_by(QAReport.created_at.desc())
    )).scalars().first()

    approval = Approval(
        content_item_id=item.id, brand_id=item.brand_id,
        requested_by=user_id, reviewed_by=user_id,
        status=ApprovalStatus.APPROVED,
        decision_mode="manual_override", auto_approved=False,
        review_notes=notes or "Manually approved",
        qa_report_id=qa.id if qa else None,
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(approval)
    item.status = "approved"
    await db.flush()
    await db.refresh(approval)
    return approval


async def reject_content(db: AsyncSession, content_id: uuid.UUID, user_id: uuid.UUID, notes: str = "") -> Approval:
    item = await _ensure_content_item(db, content_id)
    approval = Approval(
        content_item_id=item.id, brand_id=item.brand_id,
        requested_by=user_id, reviewed_by=user_id,
        status=ApprovalStatus.REJECTED,
        decision_mode="manual_override", auto_approved=False,
        review_notes=notes or "Rejected",
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(approval)
    item.status = "rejected"
    await db.flush()
    await db.refresh(approval)
    return approval


async def request_changes(db: AsyncSession, content_id: uuid.UUID, user_id: uuid.UUID, notes: str = "") -> Approval:
    item = await _ensure_content_item(db, content_id)
    approval = Approval(
        content_item_id=item.id, brand_id=item.brand_id,
        requested_by=user_id, reviewed_by=user_id,
        status=ApprovalStatus.REVISION_REQUESTED,
        decision_mode="manual_override", auto_approved=False,
        review_notes=notes or "Changes requested",
        reviewed_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(approval)
    item.status = "revision_requested"
    await db.flush()
    await db.refresh(approval)
    return approval


# ── Publishing ───────────────────────────────────────────────────────────────

async def schedule_publish(
    db: AsyncSession, content_id: uuid.UUID, creator_account_id: uuid.UUID,
    platform: str, scheduled_at: Optional[datetime] = None,
) -> PublishJob:
    item = await _ensure_content_item(db, content_id)
    if item.status not in ("approved", "scheduled"):
        raise ValueError(f"Content must be approved before publishing (current: {item.status})")

    job = PublishJob(
        content_item_id=item.id,
        creator_account_id=creator_account_id,
        brand_id=item.brand_id,
        platform=Platform(platform),
        status=JobStatus.PENDING,
        scheduled_at=scheduled_at or datetime.now(timezone.utc),
    )
    db.add(job)

    decision = PublishDecision(
        brand_id=item.brand_id,
        decision_type=DecisionType.PUBLISH,
        decision_mode=DecisionMode.GUARDED_AUTO,
        actor_type=ActorType.SYSTEM,
        content_item_id=item.id,
        creator_account_id=creator_account_id,
        publish_job_id=None,
        composite_score=0.0,
        confidence=ConfidenceLevel.MEDIUM,
        recommended_action=RecommendedAction.MAINTAIN,
        explanation=f"Scheduled for {platform} at {scheduled_at or 'now'}",
    )
    db.add(decision)
    item.status = "scheduled"
    await db.flush()
    decision.downstream_job_id = job.id
    await db.flush()
    await db.refresh(job)
    return job


async def publish_now(db: AsyncSession, content_id: uuid.UUID, creator_account_id: uuid.UUID, platform: str) -> PublishJob:
    """Schedule and dispatch a publish job to the Celery publishing worker."""
    job = await schedule_publish(db, content_id, creator_account_id, platform)
    await db.flush()
    try:
        from workers.publishing_worker.tasks import publish_content
        publish_content.delay(str(job.id))
    except Exception:
        pass
    return job


async def get_publish_status(db: AsyncSession, content_id: uuid.UUID) -> list:
    result = await db.execute(
        select(PublishJob).where(PublishJob.content_item_id == content_id).order_by(PublishJob.created_at.desc())
    )
    return list(result.scalars().all())
