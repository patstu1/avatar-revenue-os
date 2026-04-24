"""Content Lifecycle Service — the coordinated content pipeline.

This service wraps the existing content_pipeline_service functions with:
1. SystemEvent emission on every state transition
2. Quality gates that actually block progression
3. OperatorAction generation for review/approval needs
4. Correlation IDs that link related events in a flow

The existing pipeline service remains unchanged — this service composes
on top of it, adding the horizontal integration that makes it part of
the operating system.

State Machine:
    draft → brief_ready → generating → generated → qa_review →
    approved → publishing → published → tracking
                                ↓
                             rejected / revision_requested
                                ↓
                             quality_blocked
                                ↓
                              failed
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services import content_pipeline_service as pipeline
from apps.api.services import governance_bridge as gov
from apps.api.services import intelligence_bridge as intel
from apps.api.services.event_bus import emit_action, emit_event
from apps.api.services.publish_policy_engine import evaluate_publish_policy
from packages.db.models.content import ContentItem, Script
from packages.db.models.core import Brand
from packages.db.models.quality import Approval

logger = structlog.get_logger()


# ── State Transition Helpers ────────────────────────────────────────────────


async def _get_org_id(db: AsyncSession, brand_id: uuid.UUID) -> Optional[uuid.UUID]:
    """Resolve org_id from brand_id for event emission."""
    brand = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar_one_or_none()
    return brand


async def _transition_content(
    db: AsyncSession,
    item: ContentItem,
    new_status: str,
    *,
    org_id: Optional[uuid.UUID] = None,
    correlation_id: Optional[uuid.UUID] = None,
    actor_type: str = "system",
    actor_id: Optional[str] = None,
    summary: Optional[str] = None,
    details: Optional[dict] = None,
    requires_action: bool = False,
    severity: str = "info",
):
    """Transition a content item's status and emit an event."""
    previous = item.status
    item.status = new_status

    if not org_id:
        org_id = await _get_org_id(db, item.brand_id)

    await emit_event(
        db,
        domain="content",
        event_type=f"content.{new_status}",
        summary=summary or f"Content '{item.title[:80]}' → {new_status}",
        org_id=org_id,
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=item.id,
        previous_state=previous,
        new_state=new_status,
        severity=severity,
        actor_type=actor_type,
        actor_id=actor_id,
        details=details or {},
        correlation_id=correlation_id,
        requires_action=requires_action,
    )

    await db.flush()


# ── Pipeline Operations with Event Integration ────────────────────────────


async def generate_script_with_events(
    db: AsyncSession,
    brief_id: uuid.UUID,
    *,
    actor_id: Optional[str] = None,
) -> Script:
    """Generate a script from a brief, emitting lifecycle events.

    Now includes:
    - Kill ledger check (prevents repeating dead approaches)
    - Intelligence context injection (patterns, suppressions)
    - Event emission for full observability

    Events emitted:
    - content.generating (brief transitions to generating state)
    - content.generated (script created successfully)
    - content.failed (generation failed)
    - intelligence.kill_blocked (if kill ledger prevents generation)
    """
    brief = await pipeline.get_brief(db, brief_id)
    org_id = await _get_org_id(db, brief.brand_id)
    correlation_id = uuid.uuid4()

    # --- Kill Ledger Check ---
    kill_check = await intel.check_kill_ledger(
        db,
        brief.brand_id,
        entity_type="content_brief",
    )
    if kill_check["blocked"]:
        await emit_event(
            db,
            domain="intelligence",
            event_type="intelligence.kill_blocked",
            summary=f"Generation blocked by kill ledger: {brief.title[:60]}",
            org_id=org_id,
            brand_id=brief.brand_id,
            entity_type="content_brief",
            entity_id=brief.id,
            severity="warning",
            requires_action=True,
            correlation_id=correlation_id,
            details={"kill_entries": kill_check["kill_entries"]},
        )
        raise ValueError(f"Blocked by kill ledger: {kill_check['reason']}")

    # --- Get Intelligence Context (logged for observability) ---
    intel_context = await intel.get_generation_intelligence(
        db,
        brief.brand_id,
        platform=brief.target_platform,
    )

    # Emit: generation starting (with intelligence signal count)
    await emit_event(
        db,
        domain="content",
        event_type="content.generating",
        summary=f"Generating script for brief: {brief.title[:80]}",
        org_id=org_id,
        brand_id=brief.brand_id,
        entity_type="content_brief",
        entity_id=brief.id,
        previous_state=brief.status,
        new_state="generating",
        actor_type="human" if actor_id else "system",
        actor_id=actor_id,
        correlation_id=correlation_id,
        details={"intelligence_signals": intel_context["total_intelligence_signals"]},
    )

    try:
        script = await pipeline.generate_script(db, brief_id)

        # Emit: generation complete
        await emit_event(
            db,
            domain="content",
            event_type="content.generated",
            summary=f"Script generated: {script.title[:80]} ({script.word_count} words, {script.generation_model})",
            org_id=org_id,
            brand_id=brief.brand_id,
            entity_type="script",
            entity_id=script.id,
            previous_state="generating",
            new_state="generated",
            correlation_id=correlation_id,
            details={
                "word_count": script.word_count,
                "model": script.generation_model,
                "brief_id": str(brief.id),
            },
        )

        return script

    except Exception as e:
        # Emit: generation failed
        await emit_event(
            db,
            domain="content",
            event_type="content.generation_failed",
            summary=f"Script generation failed for: {brief.title[:80]} — {str(e)[:200]}",
            org_id=org_id,
            brand_id=brief.brand_id,
            entity_type="content_brief",
            entity_id=brief.id,
            severity="error",
            requires_action=True,
            correlation_id=correlation_id,
            details={"error": str(e)[:500]},
        )

        # Create operator action for the failure
        await emit_action(
            db,
            org_id=org_id,
            action_type="retry_generation",
            title=f"Script generation failed: {brief.title[:60]}",
            description=f"Generation failed with error: {str(e)[:300]}. Review the brief and retry.",
            category="failure",
            priority="high",
            brand_id=brief.brand_id,
            entity_type="content_brief",
            entity_id=brief.id,
            source_module="content_lifecycle",
        )

        raise


async def run_qa_with_events(
    db: AsyncSession,
    content_id: uuid.UUID,
    *,
    actor_id: Optional[str] = None,
) -> dict:
    """Run QA scoring with event emission and quality gate enforcement.

    This is a real gate — if QA fails, the content is blocked and an
    operator action is created for review.

    Events emitted:
    - content.qa_review (QA started)
    - content.qa_passed (QA passed, ready for approval)
    - content.quality_blocked (QA failed, blocked)
    """
    item = await pipeline._ensure_content_item(db, content_id)
    org_id = await _get_org_id(db, item.brand_id)
    correlation_id = uuid.uuid4()

    # Emit: QA starting
    await emit_event(
        db,
        domain="content",
        event_type="content.qa_started",
        summary=f"QA review started: {item.title[:80]}",
        org_id=org_id,
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=item.id,
        previous_state=item.status,
        new_state="qa_review",
        actor_type="human" if actor_id else "system",
        actor_id=actor_id,
        correlation_id=correlation_id,
    )

    # Run QA scoring
    qa_report = await pipeline.run_qa(db, content_id)
    sim_report = await pipeline.run_similarity(db, content_id)

    # Evaluate quality gate
    qa_passed = qa_report.qa_status.value in ("pass", "review")
    similarity_ok = not sim_report.is_too_similar
    quality_blocked = not qa_passed or not similarity_ok

    blocking_reasons = []
    if not qa_passed:
        blocking_reasons.append(f"QA score {qa_report.composite_score:.2f} below threshold")
    if not similarity_ok:
        blocking_reasons.append(f"Too similar to existing content (max: {sim_report.max_similarity_score:.2f})")

    if quality_blocked:
        # Block the content
        await _transition_content(
            db,
            item,
            "quality_blocked",
            org_id=org_id,
            correlation_id=correlation_id,
            severity="warning",
            summary=f"Content blocked by quality gate: {item.title[:60]} — {'; '.join(blocking_reasons)}",
            details={
                "qa_score": qa_report.composite_score,
                "qa_status": qa_report.qa_status.value,
                "similarity_score": sim_report.max_similarity_score,
                "blocking_reasons": blocking_reasons,
            },
            requires_action=True,
        )

        # Create operator action for review
        await emit_action(
            db,
            org_id=org_id,
            action_type="review_blocked_content",
            title=f"Content blocked: {item.title[:60]}",
            description=f"Quality gate blocked this content. Reasons: {'; '.join(blocking_reasons)}. "
            f"Review and either fix issues or override the block.",
            category="blocker",
            priority="high",
            brand_id=item.brand_id,
            entity_type="content_item",
            entity_id=item.id,
            source_module="quality_governor",
            action_payload={
                "qa_report_id": str(qa_report.id),
                "blocking_reasons": blocking_reasons,
            },
        )
    else:
        # QA passed — evaluate publish policy to determine tier
        policy_result = await evaluate_publish_policy(
            db,
            item,
            qa_score=qa_report.composite_score,
            confidence=qa_report.qa_status.value if qa_report.qa_status else None,
        )
        tier = policy_result.tier

        if tier == "block":
            # Policy says block — treat like quality_blocked
            await _transition_content(
                db,
                item,
                "quality_blocked",
                org_id=org_id,
                correlation_id=correlation_id,
                severity="warning",
                summary=f"Content blocked by publish policy: {item.title[:60]} — {policy_result.explanation}",
                details={
                    "qa_score": qa_report.composite_score,
                    "publish_policy_tier": tier,
                    "matched_rule": policy_result.rule_name,
                    "explanation": policy_result.explanation,
                },
                requires_action=True,
            )
            await emit_action(
                db,
                org_id=org_id,
                action_type="review_blocked_content",
                title=f"Policy blocked: {item.title[:60]}",
                description=f"Publish policy rule '{policy_result.rule_name}' blocked this content. "
                f"{policy_result.explanation}",
                category="blocker",
                priority="high",
                brand_id=item.brand_id,
                entity_type="content_item",
                entity_id=item.id,
                source_module="publish_policy_engine",
                action_payload={
                    "qa_report_id": str(qa_report.id),
                    "publish_policy_tier": tier,
                    "matched_rule": policy_result.rule_name,
                    "factors": policy_result.factors,
                },
            )

        elif tier in ("auto_publish", "sample_review"):
            # Auto-approve — no human in the loop
            await _transition_content(
                db,
                item,
                "approved",
                org_id=org_id,
                correlation_id=correlation_id,
                summary=f"Auto-approved ({tier}): {item.title[:60]} (QA: {qa_report.composite_score:.2f}, rule: {policy_result.rule_name})",
                details={
                    "qa_score": qa_report.composite_score,
                    "publish_policy_tier": tier,
                    "matched_rule": policy_result.rule_name,
                    "auto_approved": True,
                    "sample_flagged": policy_result.sample_flagged,
                },
            )

            # Create Approval record for audit + worker pickup
            approval = Approval(
                content_item_id=item.id,
                brand_id=item.brand_id,
                status="approved",
                decision_mode="full_auto",
                auto_approved=True,
                review_notes=f"Auto-approved by publish policy rule: {policy_result.rule_name}",
                qa_report_id=qa_report.id,
                publish_policy_tier=tier,
                sample_flagged=policy_result.sample_flagged,
                reviewed_at=datetime.now(timezone.utc).isoformat(),
            )
            db.add(approval)

            # If sample review AND this item was flagged, create async review action
            if tier == "sample_review" and policy_result.sample_flagged:
                await emit_action(
                    db,
                    org_id=org_id,
                    action_type="review_published_content",
                    title=f"Sample review: {item.title[:60]}",
                    description=f"This content was auto-published but flagged for sample review "
                    f"by rule '{policy_result.rule_name}'. Review post-publish.",
                    category="approval",
                    priority="low",
                    brand_id=item.brand_id,
                    entity_type="content_item",
                    entity_id=item.id,
                    source_module="publish_policy_engine",
                    action_payload={
                        "qa_score": qa_report.composite_score,
                        "publish_policy_tier": tier,
                        "sample_flagged": True,
                        "matched_rule": policy_result.rule_name,
                    },
                )

        else:
            # manual_approval (or any unrecognized tier) — hold for human
            await _transition_content(
                db,
                item,
                "qa_complete",
                org_id=org_id,
                correlation_id=correlation_id,
                summary=f"QA passed, awaiting manual approval: {item.title[:60]} (score: {qa_report.composite_score:.2f})",
                details={
                    "qa_score": qa_report.composite_score,
                    "qa_status": qa_report.qa_status.value,
                    "publish_policy_tier": tier,
                    "matched_rule": policy_result.rule_name,
                },
            )
            await emit_action(
                db,
                org_id=org_id,
                action_type="approve_content",
                title=f"Review & approve: {item.title[:60]}",
                description=f"Content passed QA (score: {qa_report.composite_score:.2f}) but "
                f"publish policy rule '{policy_result.rule_name}' requires manual approval.",
                category="approval",
                priority="medium",
                brand_id=item.brand_id,
                entity_type="content_item",
                entity_id=item.id,
                source_module="publish_policy_engine",
                action_payload={
                    "qa_score": qa_report.composite_score,
                    "qa_report_id": str(qa_report.id),
                    "publish_policy_tier": tier,
                    "matched_rule": policy_result.rule_name,
                },
            )

    return {
        "qa_report": qa_report,
        "similarity_report": sim_report,
        "quality_blocked": quality_blocked,
        "blocking_reasons": blocking_reasons,
    }


async def approve_with_events(
    db: AsyncSession,
    content_id: uuid.UUID,
    user_id: uuid.UUID,
    notes: str = "",
) -> dict:
    """Approve content with event emission.

    Events emitted:
    - content.approved (content approved for publishing)
    """
    item = await pipeline._ensure_content_item(db, content_id)
    org_id = await _get_org_id(db, item.brand_id)

    approval = await pipeline.approve_content(db, content_id, user_id, notes)

    await emit_event(
        db,
        domain="content",
        event_type="content.approved",
        summary=f"Content approved: {item.title[:80]}",
        org_id=org_id,
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=item.id,
        previous_state="qa_complete",
        new_state="approved",
        actor_type="human",
        actor_id=str(user_id),
        details={"notes": notes, "approval_id": str(approval.id)},
    )

    # Record outcome in memory layer (what generation params led to approval)
    script = None
    if item.script_id:
        from packages.db.models.content import Script as ScriptModel

        script = (await db.execute(select(ScriptModel).where(ScriptModel.id == item.script_id))).scalar_one_or_none()

    await gov.record_generation_outcome(
        db,
        item.brand_id,
        item.id,
        generation_params={
            "model": script.generation_model if script else "unknown",
            "platform": item.platform,
            "content_type": item.content_type.value if hasattr(item.content_type, "value") else str(item.content_type),
        },
        approval_status="approved",
    )

    return {"approval": approval, "item": item}


async def reject_with_events(
    db: AsyncSession,
    content_id: uuid.UUID,
    user_id: uuid.UUID,
    notes: str = "",
) -> dict:
    """Reject content with event emission."""
    item = await pipeline._ensure_content_item(db, content_id)
    org_id = await _get_org_id(db, item.brand_id)

    approval = await pipeline.reject_content(db, content_id, user_id, notes)

    await emit_event(
        db,
        domain="content",
        event_type="content.rejected",
        summary=f"Content rejected: {item.title[:80]}",
        org_id=org_id,
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=item.id,
        previous_state="qa_complete",
        new_state="rejected",
        severity="warning",
        actor_type="human",
        actor_id=str(user_id),
        details={"notes": notes, "approval_id": str(approval.id)},
    )

    return {"approval": approval, "item": item}


async def publish_with_events(
    db: AsyncSession,
    content_id: uuid.UUID,
    creator_account_id: uuid.UUID,
    platform: str,
    *,
    actor_id: Optional[str] = None,
) -> dict:
    """Publish content with event emission and state tracking.

    Events emitted:
    - content.publishing (publish job dispatched)
    - Downstream: orchestration.job.completed/failed from worker
    """
    item = await pipeline._ensure_content_item(db, content_id)
    org_id = await _get_org_id(db, item.brand_id)

    job = await pipeline.publish_now(db, content_id, creator_account_id, platform)

    await emit_event(
        db,
        domain="publishing",
        event_type="content.publishing",
        summary=f"Publishing started: {item.title[:60]} → {platform}",
        org_id=org_id,
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=item.id,
        previous_state="approved",
        new_state="publishing",
        actor_type="human" if actor_id else "system",
        actor_id=actor_id,
        details={
            "platform": platform,
            "publish_job_id": str(job.id),
            "creator_account_id": str(creator_account_id),
        },
    )

    return {"job": job, "item": item}


async def finalize_media_with_events(
    db: AsyncSession,
    job_id: uuid.UUID,
    *,
    output_config: Optional[dict] = None,
) -> ContentItem:
    """Finalize a media job and create content item, with events.

    Events emitted:
    - content.media_complete (content item created from media job)
    """
    item = await pipeline.finalize_media_job(db, job_id, output_config=output_config)
    org_id = await _get_org_id(db, item.brand_id)

    await emit_event(
        db,
        domain="content",
        event_type="content.media_complete",
        summary=f"Media finalized: {item.title[:80]}",
        org_id=org_id,
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=item.id,
        new_state="media_complete",
        details={"media_job_id": str(job_id)},
    )

    # Auto-create QA action
    await emit_action(
        db,
        org_id=org_id,
        action_type="run_qa",
        title=f"Run QA: {item.title[:60]}",
        description="Media generation complete. Run QA scoring to check quality before approval.",
        category="approval",
        priority="medium",
        brand_id=item.brand_id,
        entity_type="content_item",
        entity_id=item.id,
        source_module="content_lifecycle",
    )

    return item
