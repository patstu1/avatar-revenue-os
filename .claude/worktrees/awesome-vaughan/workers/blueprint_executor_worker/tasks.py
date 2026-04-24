"""Blueprint executor — auto-executes an approved GM blueprint end-to-end.

Triggered by blueprint approval (not beat-scheduled).
Runs all 3 execution steps sequentially, then seeds initial content briefs
so the autonomous generation pipeline can start producing.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from workers.celery_app import app

logger = structlog.get_logger()

EXPECTED_STEPS = ["create_brands", "create_accounts", "create_offers"]
DEFAULT_PLATFORMS = ["tiktok", "instagram", "youtube"]


@app.task(bind=True, name="workers.blueprint_executor_worker.tasks.execute_approved_blueprint")
def execute_approved_blueprint(self, blueprint_id: str) -> dict:
    """Execute all steps of an approved blueprint, then seed content briefs."""
    return asyncio.run(_execute_impl(blueprint_id))


async def _execute_impl(blueprint_id: str) -> dict:
    from packages.db.session import async_session_factory
    from packages.db.models.gm import GMBlueprint
    from apps.api.services import gm_startup
    from apps.api.services.event_bus import emit_event

    async with async_session_factory() as db:
        # ── Load blueprint ──
        bp = (await db.execute(
            select(GMBlueprint).where(GMBlueprint.id == uuid.UUID(blueprint_id))
        )).scalar_one_or_none()

        if not bp:
            logger.error("blueprint_executor.not_found", blueprint_id=blueprint_id)
            return {"success": False, "error": "blueprint_not_found"}

        if bp.status not in ("approved", "executing"):
            logger.warning("blueprint_executor.invalid_status", status=bp.status)
            return {"success": False, "error": f"invalid_status:{bp.status}"}

        org_id = bp.organization_id

        # ── Mark executing ──
        bp.status = "executing"
        bp.execution_progress = bp.execution_progress or {}
        await db.flush()

        await emit_event(
            db, domain="orchestration", event_type="blueprint.execution_started",
            summary=f"Blueprint execution started — {len(EXPECTED_STEPS)} steps",
            org_id=org_id,
            entity_type="gm_blueprint", entity_id=bp.id,
            previous_state="approved", new_state="executing",
        )
        await db.commit()

        # ── Execute each step sequentially ──
        all_success = True
        for step_key in EXPECTED_STEPS:
            try:
                exec_result = await gm_startup.execute_blueprint_step(
                    db, org_id, bp, step_key,
                )
                step_success = exec_result.get("success", False)

                bp.execution_progress[step_key] = {
                    "status": "completed" if step_success else "failed",
                    "result": exec_result,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }

                await emit_event(
                    db, domain="orchestration", event_type="blueprint.step_completed",
                    summary=f"Blueprint step '{step_key}': {'completed' if step_success else 'failed'}",
                    org_id=org_id,
                    entity_type="gm_blueprint", entity_id=bp.id,
                    details={"step": step_key, "success": step_success, "result": exec_result},
                )
                await db.commit()

                if not step_success:
                    all_success = False
                    logger.error("blueprint_executor.step_failed", step=step_key, result=exec_result)
                    break

            except Exception as exc:
                bp.execution_progress[step_key] = {
                    "status": "failed",
                    "error": str(exc),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                }
                all_success = False
                logger.error("blueprint_executor.step_exception", step=step_key, error=str(exc))

                await emit_event(
                    db, domain="orchestration", event_type="blueprint.step_failed",
                    summary=f"Blueprint step '{step_key}' failed: {str(exc)[:200]}",
                    org_id=org_id,
                    entity_type="gm_blueprint", entity_id=bp.id,
                    severity="error",
                    details={"step": step_key, "error": str(exc)},
                )
                await db.commit()
                break

        # ── Seed content briefs if execution succeeded ──
        briefs_created = 0
        if all_success:
            try:
                briefs_created = await _seed_initial_briefs(db, org_id)
                await db.commit()
            except Exception as exc:
                logger.warning("blueprint_executor.brief_seeding_failed", error=str(exc))

        # ── Final status ──
        if all_success:
            bp.status = "completed"
            bp.completed_at = datetime.now(timezone.utc)
        else:
            bp.status = "failed"

        await emit_event(
            db, domain="orchestration",
            event_type="blueprint.execution_completed" if all_success else "blueprint.execution_failed",
            summary=f"Blueprint execution {'completed' if all_success else 'failed'} — {briefs_created} briefs seeded",
            org_id=org_id,
            entity_type="gm_blueprint", entity_id=bp.id,
            previous_state="executing",
            new_state=bp.status,
            severity="info" if all_success else "error",
            details={"briefs_seeded": briefs_created},
        )
        await db.commit()

        return {
            "success": all_success,
            "status": bp.status,
            "execution_progress": bp.execution_progress,
            "briefs_seeded": briefs_created,
        }


async def _seed_initial_briefs(db: AsyncSession, org_id: uuid.UUID) -> int:
    """Create initial content briefs for each brand + offer + platform combination.

    These briefs are created with status='draft' so the existing
    process_pending_briefs beat task (every 30 min) picks them up
    and auto-generates content.
    """
    from packages.db.models.core import Brand
    from packages.db.models.offers import Offer
    from packages.db.models.content import ContentBrief, ContentType

    # Find all brands for this org
    brands = (await db.execute(
        select(Brand).where(
            Brand.organization_id == org_id,
            Brand.is_active.is_(True),
        )
    )).scalars().all()

    count = 0
    for brand in brands:
        # Find offers for this brand
        offers = (await db.execute(
            select(Offer).where(
                Offer.brand_id == brand.id,
                Offer.is_active.is_(True),
            )
        )).scalars().all()

        for offer in offers:
            for platform in DEFAULT_PLATFORMS:
                brief = ContentBrief(
                    brand_id=brand.id,
                    offer_id=offer.id,
                    title=f"[Auto] {offer.name} — {platform.title()} launch content",
                    content_type=ContentType.SHORT_VIDEO,
                    target_platform=platform,
                    hook=f"Attention-grabbing opener for {offer.name}",
                    angle=f"Showcase the value proposition of {offer.name} for {brand.niche or 'target audience'}",
                    key_points=[
                        f"Core benefit of {offer.name}",
                        "Social proof or credibility signal",
                        "Clear call to action",
                    ],
                    cta_strategy=f"Direct CTA to {offer.offer_url or 'offer page'}",
                    monetization_integration=offer.monetization_method or "lead_gen",
                    tone_guidance="Professional, confident, direct",
                    status="draft",
                    brief_metadata={
                        "source": "blueprint_executor",
                        "qa_retry_count": 0,
                    },
                )
                db.add(brief)
                count += 1

    await db.flush()
    logger.info("blueprint_executor.briefs_seeded", count=count, org_id=str(org_id))
    return count
