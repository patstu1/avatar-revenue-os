"""Quality Feedback Loop — connects content performance back to generation quality.

This closes the loop: publish → measure → learn → generate better.

When performance data arrives (from analytics ingestion), this service:
1. Evaluates which generation parameters produced the best outcomes
2. Updates winning/losing pattern scores from real performance
3. Adjusts generation context for future content
4. Suppresses weak generation patterns automatically
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_event
from packages.db.models.content import ContentItem, Script
from packages.db.models.core import Brand
from packages.db.models.learning import MemoryEntry
from packages.db.models.pattern_memory import LosingPatternMemory, WinningPatternMemory
from packages.db.models.publishing import PerformanceMetric

logger = structlog.get_logger()


async def run_quality_feedback(db: AsyncSession, brand_id: uuid.UUID) -> dict:
    """Evaluate published content performance and update generation patterns.

    This is the core learning loop. It reads actual performance data,
    identifies what generation parameters produced the best/worst results,
    and updates pattern memory accordingly.
    """
    now = datetime.now(timezone.utc)
    day_30 = now - timedelta(days=30)

    # Get published content with scripts (generation parameters) and performance
    content_q = await db.execute(
        select(ContentItem, Script, PerformanceMetric)
        .outerjoin(Script, Script.id == ContentItem.script_id)
        .outerjoin(PerformanceMetric, PerformanceMetric.content_item_id == ContentItem.id)
        .where(ContentItem.brand_id == brand_id, ContentItem.status == "published", ContentItem.created_at >= day_30)
        .order_by(PerformanceMetric.revenue.desc().nullslast())
        .limit(50)
    )
    rows = content_q.all()

    if not rows:
        return {
            "processed": 0,
            "winners_updated": 0,
            "losers_created": 0,
            "message": "No published content with performance data in last 30 days",
        }

    winners_updated = 0
    losers_created = 0
    memory_entries = 0

    for content, script, perf in rows:
        if not perf:
            continue

        impressions = perf.impressions or 0
        revenue = float(perf.revenue or 0)
        engagement = float(perf.engagement_rate or 0)

        # Compute performance score
        if impressions == 0:
            continue

        rpm = (revenue / impressions * 1000) if impressions > 0 else 0
        # Normalize against the batch: best performer in this evaluation is the reference
        max_rpm_batch = (
            max(
                (float(p.revenue or 0) / max(p.impressions or 1, 1) * 1000)
                for _, _, p in rows
                if p and (p.impressions or 0) > 0
            )
            if rows
            else 20
        )
        max_imp_batch = max((p.impressions or 0) for _, _, p in rows if p) if rows else 1

        performance_score = (
            0.40 * min(1.0, rpm / max(max_rpm_batch, 1))  # Relative to batch best RPM
            + 0.30 * min(1.0, engagement * 10)  # Engagement rate (0.1 = max)
            + 0.30 * min(1.0, impressions / max(max_imp_batch, 1))  # Relative to batch best reach
        )

        # Extract generation parameters from script
        gen_model = script.generation_model if script else "unknown"
        hook_type = content.hook_type or "unknown"
        cta_type = content.cta_type or "unknown"
        content_type = (
            content.content_type.value if hasattr(content.content_type, "value") else str(content.content_type)
        )
        platform = content.platform or "unknown"
        offer_angle = content.offer_angle or "unknown"

        # Update patterns based on performance
        if performance_score >= 0.6:
            # Winner — boost or create winning pattern
            for pattern_type, pattern_name in [
                ("hook", hook_type),
                ("cta", cta_type),
                ("content_form", content_type),
                ("offer_angle", offer_angle),
            ]:
                if pattern_name and pattern_name != "unknown":
                    existing = (
                        await db.execute(
                            select(WinningPatternMemory).where(
                                WinningPatternMemory.brand_id == brand_id,
                                WinningPatternMemory.pattern_type == pattern_type,
                                WinningPatternMemory.pattern_name == pattern_name,
                                WinningPatternMemory.is_active.is_(True),
                            )
                        )
                    ).scalar_one_or_none()

                    if existing:
                        # Reinforce: update win_score toward performance_score
                        old_score = existing.win_score or 0
                        existing.win_score = round(old_score * 0.7 + performance_score * 0.3, 3)
                        existing.usage_count = (existing.usage_count or 0) + 1
                        winners_updated += 1
                    else:
                        db.add(
                            WinningPatternMemory(
                                brand_id=brand_id,
                                pattern_type=pattern_type,
                                pattern_name=pattern_name,
                                platform=platform,
                                win_score=round(performance_score, 3),
                                confidence=0.5,
                                usage_count=1,
                                performance_band="standard",
                                is_active=True,
                            )
                        )
                        winners_updated += 1

        elif performance_score < 0.25:
            # Loser — create or reinforce losing pattern
            for pattern_type, pattern_name in [
                ("hook", hook_type),
                ("cta", cta_type),
                ("content_form", content_type),
            ]:
                if pattern_name and pattern_name != "unknown":
                    existing = (
                        await db.execute(
                            select(LosingPatternMemory).where(
                                LosingPatternMemory.brand_id == brand_id,
                                LosingPatternMemory.pattern_type == pattern_type,
                                LosingPatternMemory.pattern_name == pattern_name,
                                LosingPatternMemory.is_active.is_(True),
                            )
                        )
                    ).scalar_one_or_none()

                    if not existing:
                        db.add(
                            LosingPatternMemory(
                                brand_id=brand_id,
                                pattern_type=pattern_type,
                                pattern_name=pattern_name,
                                fail_score=round(1.0 - performance_score, 3),
                                suppress_reason=f"Low performance: RPM=${rpm:.2f}, engagement={engagement:.3f}",
                                usage_count=1,
                                is_active=True,
                            )
                        )
                        losers_created += 1

        # Record learning memory entry
        db.add(
            MemoryEntry(
                brand_id=brand_id,
                memory_type="performance_feedback",
                key=f"content_{content.id}",
                value=f"{gen_model} on {platform}/{content_type}: score={performance_score:.2f}, RPM=${rpm:.2f}",
                confidence=min(0.9, performance_score + 0.2),
                source_type="quality_feedback_loop",
                source_content_id=content.id,
                structured_value={
                    "generation_model": gen_model,
                    "platform": platform,
                    "content_type": content_type,
                    "hook_type": hook_type,
                    "performance_score": performance_score,
                    "rpm": rpm,
                    "engagement": engagement,
                    "impressions": impressions,
                    "revenue": revenue,
                },
            )
        )
        memory_entries += 1

    await db.flush()

    org_id = (await db.execute(select(Brand.organization_id).where(Brand.id == brand_id))).scalar()
    await emit_event(
        db,
        domain="intelligence",
        event_type="quality_feedback.completed",
        summary=f"Quality feedback: {winners_updated} patterns reinforced, {losers_created} losers identified",
        org_id=org_id,
        brand_id=brand_id,
        details={
            "winners_updated": winners_updated,
            "losers_created": losers_created,
            "memory_entries": memory_entries,
            "content_evaluated": len(rows),
        },
    )

    return {
        "content_evaluated": len(rows),
        "winners_updated": winners_updated,
        "losers_created": losers_created,
        "memory_entries_created": memory_entries,
    }
