"""Strategy Adjustment Worker — analytics-driven content strategy adaptation.

Runs after each analytics ingestion cycle. Reads ALL winning and losing patterns,
generates proportional briefs, deprioritizes losers, rotates offers, detects
engagement spikes, and cross-pollinates winning monetization angles.

ZERO ARTIFICIAL CAPS on pattern counts, brief counts, or content volume.
Everything is proportional to measured reality.
"""
from __future__ import annotations

import asyncio
import logging
import math
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from celery import shared_task
from sqlalchemy import select, func, update, and_, or_

from workers.base_task import TrackedTask
from packages.db.session import async_session_factory
from packages.db.models.content import ContentBrief
from packages.db.models.core import Brand
from packages.db.models.accounts import CreatorAccount
from packages.db.models.offers import Offer
from packages.db.models.pattern_memory import (
    WinningPatternMemory,
    LosingPatternMemory,
    PatternReuseRecommendation,
)
from packages.db.models.publishing import PerformanceMetric
from packages.db.enums import ContentType, Platform

logger = logging.getLogger(__name__)

# ── Platform → content type mapping ──────────────────────────────────────────

PLATFORM_CONTENT_TYPES = {
    "youtube": [ContentType.LONG_VIDEO, ContentType.SHORT_VIDEO],
    "tiktok": [ContentType.SHORT_VIDEO],
    "instagram": [ContentType.SHORT_VIDEO, ContentType.CAROUSEL],
    "x": [ContentType.TEXT_POST],
    "linkedin": [ContentType.TEXT_POST, ContentType.CAROUSEL],
}


def _run(coro):
    return asyncio.run(coro)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN TASK: adjust_content_strategy
# ─────────────────────────────────────────────────────────────────────────────

@shared_task(
    name="workers.strategy_adjustment_worker.tasks.adjust_content_strategy",
    base=TrackedTask,
)
def adjust_content_strategy(brand_id: str, org_id: Optional[str] = None):
    """Run full strategy adjustment cycle for a single brand.

    Called after each analytics ingestion cycle. Reads ALL patterns (no caps),
    generates proportional briefs, deprioritizes losers, rotates offers,
    detects spikes, and cross-pollinates monetization angles.
    """
    bid = uuid.UUID(brand_id)
    oid = uuid.UUID(org_id) if org_id else None
    result = _run(_do_adjust_strategy(bid, oid))
    return result


@shared_task(
    name="workers.strategy_adjustment_worker.tasks.adjust_all_strategies",
    base=TrackedTask,
)
def adjust_all_strategies():
    """Run strategy adjustment for ALL active brands. No cap on brand count."""
    return _run(_do_adjust_all())


async def _do_adjust_all():
    """Iterate ALL brands and adjust each one."""
    async with async_session_factory() as db:
        brands = list((await db.execute(
            select(Brand.id, Brand.organization_id).where(Brand.is_active.is_(True))
        )).all())

    results = []
    for brand_id, org_id in brands:
        try:
            result = await _do_adjust_strategy(brand_id, org_id)
            results.append(result)
        except Exception:
            logger.exception("strategy adjustment failed for brand %s", brand_id)
            results.append({"brand_id": str(brand_id), "error": "failed"})

    total_briefs = sum(r.get("briefs_created", 0) for r in results)
    total_deprioritized = sum(r.get("briefs_deprioritized", 0) for r in results)
    total_offers_rotated = sum(r.get("offers_rotated", 0) for r in results)
    total_bursts = sum(r.get("burst_briefs_queued", 0) for r in results)
    total_cross = sum(r.get("cross_platform_tests", 0) for r in results)

    return {
        "status": "completed",
        "brands_processed": len(results),
        "total_briefs_created": total_briefs,
        "total_briefs_deprioritized": total_deprioritized,
        "total_offers_rotated": total_offers_rotated,
        "total_burst_briefs": total_bursts,
        "total_cross_platform_tests": total_cross,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CORE LOGIC
# ─────────────────────────────────────────────────────────────────────────────

async def _do_adjust_strategy(brand_id: uuid.UUID, org_id: Optional[uuid.UUID]) -> dict:
    """Full strategy adjustment for one brand."""
    from apps.api.services.event_bus import emit_event_sync
    from packages.db.session import get_sync_engine
    from sqlalchemy.orm import Session as SyncSession

    summary = {
        "brand_id": str(brand_id),
        "briefs_created": 0,
        "briefs_deprioritized": 0,
        "offers_rotated": 0,
        "burst_briefs_queued": 0,
        "cross_platform_tests": 0,
        "adjustments": [],
    }

    async with async_session_factory() as db:
        # ── 1. Load ALL active winning patterns (zero cap) ────────────────
        winning_patterns = list((await db.execute(
            select(WinningPatternMemory).where(
                WinningPatternMemory.brand_id == brand_id,
                WinningPatternMemory.is_active.is_(True),
            ).order_by(WinningPatternMemory.win_score.desc())
        )).scalars().all())

        # ── 2. Load ALL active losing patterns (zero cap) ────────────────
        losing_patterns = list((await db.execute(
            select(LosingPatternMemory).where(
                LosingPatternMemory.brand_id == brand_id,
                LosingPatternMemory.is_active.is_(True),
            ).order_by(LosingPatternMemory.fail_score.desc())
        )).scalars().all())

        # ── 3. Load active accounts for this brand ───────────────────────
        accounts = list((await db.execute(
            select(CreatorAccount).where(
                CreatorAccount.brand_id == brand_id,
                CreatorAccount.is_active.is_(True),
            )
        )).scalars().all())

        # ── 4. Load active offers for this brand ─────────────────────────
        offers = list((await db.execute(
            select(Offer).where(
                Offer.brand_id == brand_id,
                Offer.is_active.is_(True),
            )
        )).scalars().all())

        # ── 5. Load existing pending briefs (for deprioritization) ───────
        pending_briefs = list((await db.execute(
            select(ContentBrief).where(
                ContentBrief.brand_id == brand_id,
                ContentBrief.status.in_(["draft", "ready", "pending_generation"]),
            )
        )).scalars().all())

        if not winning_patterns and not losing_patterns:
            logger.info("strategy_adjust: no patterns for brand %s, skipping", brand_id)
            return summary

        # ── Step A: Generate briefs proportional to winning pattern scores ──
        briefs_created = await _generate_winner_briefs(
            db, brand_id, winning_patterns, accounts, offers,
        )
        summary["briefs_created"] = briefs_created

        # ── Step B: Deprioritize pending briefs that match losing patterns ──
        deprioritized = await _deprioritize_loser_briefs(
            db, brand_id, losing_patterns, pending_briefs,
        )
        summary["briefs_deprioritized"] = deprioritized

        # ── Step C: Rotate offers — winners get more placement, zeroes get swapped ──
        rotated = await _rotate_offers(db, brand_id, winning_patterns, offers)
        summary["offers_rotated"] = rotated

        # ── Step D: Detect engagement spikes and burst-queue content ──────
        burst = await _detect_spikes_and_burst(db, brand_id, accounts, winning_patterns)
        summary["burst_briefs_queued"] = burst

        # ── Step E: Cross-pollinate winning monetization angles ───────────
        cross = await _cross_pollinate_monetization(db, brand_id, winning_patterns, accounts)
        summary["cross_platform_tests"] = cross

        await db.commit()

    # ── Emit strategy.auto_adjusted event ────────────────────────────────
    try:
        engine = get_sync_engine()
        with SyncSession(engine) as sync_session:
            emit_event_sync(
                sync_session,
                domain="strategy",
                event_type="strategy.auto_adjusted",
                summary=(
                    f"Strategy auto-adjusted for brand {brand_id}: "
                    f"{briefs_created} briefs created, {deprioritized} deprioritized, "
                    f"{rotated} offers rotated, {burst} burst briefs, "
                    f"{cross} cross-platform tests"
                ),
                brand_id=brand_id,
                org_id=org_id,
                severity="info",
                actor_type="worker",
                actor_id="strategy_adjustment_worker",
                details=summary,
            )
            sync_session.commit()
    except Exception:
        logger.exception("strategy_adjust: failed to emit event for brand %s", brand_id)

    logger.info(
        "strategy_adjust.complete brand=%s briefs=%d depri=%d rotated=%d burst=%d cross=%d",
        brand_id, briefs_created, deprioritized, rotated, burst, cross,
    )
    return summary


# ─────────────────────────────────────────────────────────────────────────────
# STEP A: Generate winner briefs — proportional to win_score vs. average
# ─────────────────────────────────────────────────────────────────────────────

async def _generate_winner_briefs(
    db, brand_id, winning_patterns, accounts, offers,
) -> int:
    """For each winning pattern, generate briefs proportional to its relative strength.

    The stronger a pattern's win_score relative to the average, the more briefs
    it gets. No ceiling — if there are 500 winning patterns each deserving 3
    briefs, you get 1500 briefs.
    """
    if not winning_patterns or not accounts:
        return 0

    # Compute average win_score across ALL active winning patterns
    scores = [p.win_score for p in winning_patterns if p.win_score > 0]
    if not scores:
        return 0

    avg_score = sum(scores) / len(scores)
    if avg_score <= 0:
        avg_score = 1.0  # prevent division by zero

    # Load existing brief titles to avoid duplication
    existing_titles = set()
    existing = list((await db.execute(
        select(ContentBrief.title).where(
            ContentBrief.brand_id == brand_id,
            ContentBrief.status.in_(["draft", "ready", "pending_generation", "generating", "script_generated"]),
        )
    )).scalars().all())
    existing_titles = {t.lower().strip() for t in existing if t}

    # Build account lookup by platform
    acct_by_platform = {}
    for acct in accounts:
        plat = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
        acct_by_platform.setdefault(plat, []).append(acct)

    # Build offer lookup for monetization integration
    offer_map = {str(o.id): o for o in offers}

    total_created = 0

    for pattern in winning_patterns:
        if pattern.win_score <= 0:
            continue

        # Briefs proportional to how far above average this pattern is
        # Minimum 1 brief per winning pattern, scales up with relative strength
        relative_strength = pattern.win_score / avg_score
        brief_count = max(1, round(relative_strength))

        # Determine target platform(s)
        target_platforms = []
        if pattern.platform:
            target_platforms = [pattern.platform]
        else:
            target_platforms = list(acct_by_platform.keys())

        for platform in target_platforms:
            platform_accounts = acct_by_platform.get(platform, [])
            if not platform_accounts:
                continue

            content_types = PLATFORM_CONTENT_TYPES.get(platform, [ContentType.SHORT_VIDEO])
            acct = platform_accounts[0]  # primary account for this platform

            # Find matching offer if pattern has one
            offer = None
            if pattern.offer_id and str(pattern.offer_id) in offer_map:
                offer = offer_map[str(pattern.offer_id)]

            for i in range(brief_count):
                title = _build_brief_title(pattern, platform, i)
                if title.lower().strip() in existing_titles:
                    continue

                content_type = content_types[i % len(content_types)]
                duration = 60 if content_type in (ContentType.SHORT_VIDEO, ContentType.TEXT_POST) else 600

                brief = ContentBrief(
                    brand_id=brand_id,
                    creator_account_id=acct.id,
                    offer_id=offer.id if offer else None,
                    title=title,
                    content_type=content_type,
                    target_platform=platform,
                    hook=f"Pattern-driven: {pattern.pattern_name}",
                    angle=pattern.explanation or pattern.pattern_signature,
                    key_points=[
                        f"Based on winning pattern: {pattern.pattern_name}",
                        f"Win score: {pattern.win_score:.2f} (relative strength: {relative_strength:.1f}x)",
                        f"Pattern type: {pattern.pattern_type}",
                    ],
                    cta_strategy=f"Monetization: {pattern.monetization_method or 'organic'}" if pattern.monetization_method else None,
                    monetization_integration=pattern.monetization_method,
                    target_duration_seconds=duration,
                    tone_guidance=f"Content form: {pattern.content_form}" if pattern.content_form else None,
                    brief_metadata={
                        "source": "strategy_adjustment_worker",
                        "pattern_id": str(pattern.id),
                        "pattern_type": pattern.pattern_type,
                        "win_score": pattern.win_score,
                        "relative_strength": relative_strength,
                        "auto_generated": True,
                    },
                    status="draft",
                )
                db.add(brief)
                existing_titles.add(title.lower().strip())
                total_created += 1

    await db.flush()
    return total_created


def _build_brief_title(pattern, platform: str, index: int) -> str:
    """Build a unique, descriptive title for a strategy-driven brief."""
    base = pattern.pattern_name or pattern.pattern_signature[:80]
    suffix = f" [{platform}]" if platform else ""
    idx = f" v{index + 1}" if index > 0 else ""
    return f"[Strategy] {base}{suffix}{idx}"


# ─────────────────────────────────────────────────────────────────────────────
# STEP B: Deprioritize pending briefs matching losing patterns
# ─────────────────────────────────────────────────────────────────────────────

async def _deprioritize_loser_briefs(
    db, brand_id, losing_patterns, pending_briefs,
) -> int:
    """Move briefs matching losing patterns to the back of the queue.

    Sets status to 'deprioritized' so winners publish first.
    No cap on how many get deprioritized — if the data says it's a loser,
    it gets deprioritized.
    """
    if not losing_patterns or not pending_briefs:
        return 0

    # Build a set of losing pattern signatures for fast matching
    loser_signatures = set()
    loser_types = set()
    loser_platforms = set()
    loser_monetizations = set()

    for lp in losing_patterns:
        loser_signatures.add(lp.pattern_signature.lower())
        loser_types.add(lp.pattern_type.lower())
        if lp.platform:
            loser_platforms.add(lp.platform.lower())

    deprioritized = 0
    for brief in pending_briefs:
        metadata = brief.brief_metadata or {}

        # Check if this brief was generated from a now-losing pattern
        source_pattern_type = metadata.get("pattern_type", "").lower()
        brief_platform = (brief.target_platform or "").lower()

        matched = False

        # Direct match: brief was sourced from a pattern that's now losing
        if source_pattern_type and source_pattern_type in loser_types:
            if brief_platform and brief_platform in loser_platforms:
                matched = True
            elif not loser_platforms:
                matched = True

        # Signature match: brief angle matches a losing pattern signature
        if not matched and brief.angle:
            brief_angle_lower = brief.angle.lower()
            for sig in loser_signatures:
                if sig in brief_angle_lower or brief_angle_lower in sig:
                    matched = True
                    break

        if matched:
            brief.status = "deprioritized"
            brief.brief_metadata = {
                **(brief.brief_metadata or {}),
                "deprioritized_by": "strategy_adjustment_worker",
                "deprioritized_at": datetime.now(timezone.utc).isoformat(),
                "reason": "matches_losing_pattern",
            }
            deprioritized += 1

    await db.flush()
    return deprioritized


# ─────────────────────────────────────────────────────────────────────────────
# STEP C: Rotate offers — winners get more placement, zero-converters swapped
# ─────────────────────────────────────────────────────────────────────────────

async def _rotate_offers(db, brand_id, winning_patterns, offers) -> int:
    """Adjust offer placement based on pattern performance.

    - Winning offers (referenced by high-win-score patterns) get their priority boosted.
    - Zero-conversion offers get their priority dropped.
    """
    if not winning_patterns or not offers:
        return 0

    # Count how many winning patterns reference each offer
    offer_win_counts: dict[str, float] = {}
    for p in winning_patterns:
        if p.offer_id:
            oid_str = str(p.offer_id)
            offer_win_counts[oid_str] = offer_win_counts.get(oid_str, 0) + p.win_score

    # Find offers with zero conversions
    zero_conversion_offers = [
        o for o in offers
        if o.conversion_rate == 0 and o.epc == 0
    ]

    rotated = 0

    # Boost winning offers proportionally
    for offer in offers:
        oid_str = str(offer.id)
        if oid_str in offer_win_counts:
            total_win = offer_win_counts[oid_str]
            new_priority = max(offer.priority, round(total_win * 10))
            if new_priority != offer.priority:
                offer.priority = new_priority
                rotated += 1

    # Drop zero-converter priority so they appear less in future briefs
    for offer in zero_conversion_offers:
        if offer.priority > 0:
            offer.priority = max(0, offer.priority - 5)
            rotated += 1

    # Swap zero-converters in pending briefs with winning offers
    if zero_conversion_offers and offer_win_counts:
        zero_ids = {str(o.id) for o in zero_conversion_offers}
        best_offer_id = max(offer_win_counts, key=offer_win_counts.get)

        pending_with_zero = list((await db.execute(
            select(ContentBrief).where(
                ContentBrief.brand_id == brand_id,
                ContentBrief.status.in_(["draft", "ready", "pending_generation"]),
                ContentBrief.offer_id.in_([uuid.UUID(oid) for oid in zero_ids]),
            )
        )).scalars().all())

        for brief in pending_with_zero:
            brief.offer_id = uuid.UUID(best_offer_id)
            brief.brief_metadata = {
                **(brief.brief_metadata or {}),
                "offer_swapped_by": "strategy_adjustment_worker",
                "offer_swapped_at": datetime.now(timezone.utc).isoformat(),
                "previous_offer_id": str(brief.offer_id) if brief.offer_id else None,
                "reason": "zero_conversion_swap",
            }
            rotated += 1

    await db.flush()
    return rotated


# ─────────────────────────────────────────────────────────────────────────────
# STEP D: Detect engagement spikes and burst-queue content
# ─────────────────────────────────────────────────────────────────────────────

async def _detect_spikes_and_burst(
    db, brand_id, accounts, winning_patterns,
) -> int:
    """If an account shows a sudden engagement spike, queue a burst of content.

    A spike is defined as: latest engagement_rate > 2x the account's 7-day average.
    Burst size is proportional to the spike magnitude — no cap.
    """
    if not accounts:
        return 0

    total_burst = 0
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    for acct in accounts:
        platform = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)

        # Get 7-day average engagement for this account
        avg_result = (await db.execute(
            select(func.avg(PerformanceMetric.engagement_rate)).where(
                PerformanceMetric.creator_account_id == acct.id,
                PerformanceMetric.measured_at >= seven_days_ago,
            )
        )).scalar_one_or_none()

        avg_engagement = float(avg_result) if avg_result else 0.0
        if avg_engagement <= 0:
            continue

        # Get latest metric
        latest = (await db.execute(
            select(PerformanceMetric).where(
                PerformanceMetric.creator_account_id == acct.id,
            ).order_by(PerformanceMetric.measured_at.desc()).limit(1)
        )).scalar_one_or_none()

        if not latest or not latest.engagement_rate:
            continue

        spike_ratio = latest.engagement_rate / avg_engagement

        if spike_ratio >= 2.0:
            # Spike detected — burst size proportional to spike magnitude
            burst_count = max(1, round(spike_ratio))

            # Use the top winning patterns for burst content
            burst_patterns = winning_patterns[:burst_count] if winning_patterns else []
            content_types = PLATFORM_CONTENT_TYPES.get(platform, [ContentType.SHORT_VIDEO])

            for idx in range(burst_count):
                pattern = burst_patterns[idx % len(burst_patterns)] if burst_patterns else None
                title_base = pattern.pattern_name if pattern else f"Spike Capitalize {platform}"
                title = f"[Burst] {title_base} [{platform}] #{idx + 1}"

                brief = ContentBrief(
                    brand_id=brand_id,
                    creator_account_id=acct.id,
                    title=title,
                    content_type=content_types[idx % len(content_types)],
                    target_platform=platform,
                    hook=f"Engagement spike detected ({spike_ratio:.1f}x) — capitalize now",
                    angle=pattern.explanation if pattern else "Engagement spike — ride the wave",
                    key_points=[
                        f"Spike ratio: {spike_ratio:.1f}x above 7-day average",
                        f"Account: {acct.platform_username or str(acct.id)}",
                        f"Average engagement: {avg_engagement:.4f}, Current: {latest.engagement_rate:.4f}",
                    ],
                    brief_metadata={
                        "source": "strategy_adjustment_worker",
                        "burst_trigger": "engagement_spike",
                        "spike_ratio": spike_ratio,
                        "account_id": str(acct.id),
                        "pattern_id": str(pattern.id) if pattern else None,
                        "auto_generated": True,
                    },
                    status="draft",
                )
                db.add(brief)
                total_burst += 1

            logger.info(
                "strategy_adjust.spike brand=%s account=%s spike=%.1fx burst=%d",
                brand_id, acct.id, spike_ratio, burst_count,
            )

    await db.flush()
    return total_burst


# ─────────────────────────────────────────────────────────────────────────────
# STEP E: Cross-pollinate monetization angles across platforms
# ─────────────────────────────────────────────────────────────────────────────

async def _cross_pollinate_monetization(
    db, brand_id, winning_patterns, accounts,
) -> int:
    """If a monetization angle works on one platform, test it on all other active platforms.

    Checks existing PatternReuseRecommendations AND generates new cross-platform
    briefs for patterns that only exist on a single platform.
    """
    if not winning_patterns or not accounts:
        return 0

    # Build set of active platforms for this brand
    active_platforms = set()
    acct_by_platform = {}
    for acct in accounts:
        plat = acct.platform.value if hasattr(acct.platform, "value") else str(acct.platform)
        active_platforms.add(plat)
        acct_by_platform.setdefault(plat, []).append(acct)

    if len(active_platforms) < 2:
        return 0  # Need at least 2 platforms to cross-pollinate

    # Load existing reuse recommendations to avoid duplicating
    existing_reuse = set()
    reuse_recs = list((await db.execute(
        select(PatternReuseRecommendation).where(
            PatternReuseRecommendation.brand_id == brand_id,
            PatternReuseRecommendation.is_active.is_(True),
        )
    )).scalars().all())

    for rec in reuse_recs:
        existing_reuse.add((str(rec.pattern_id), rec.target_platform))

    # Load existing brief titles for dedup
    existing_titles = set()
    existing = list((await db.execute(
        select(ContentBrief.title).where(
            ContentBrief.brand_id == brand_id,
            ContentBrief.status.in_(["draft", "ready", "pending_generation", "generating", "script_generated"]),
        )
    )).scalars().all())
    existing_titles = {t.lower().strip() for t in existing if t}

    cross_tests = 0

    for pattern in winning_patterns:
        if not pattern.platform or not pattern.monetization_method:
            continue

        source_platform = pattern.platform.lower()
        if source_platform not in active_platforms:
            continue

        # Only high-confidence patterns worth cross-pollinating
        if pattern.confidence < 0.5 or pattern.win_score < 1.0:
            continue

        for target_platform in active_platforms:
            if target_platform == source_platform:
                continue

            # Skip if already recommended
            if (str(pattern.id), target_platform) in existing_reuse:
                continue

            platform_accounts = acct_by_platform.get(target_platform, [])
            if not platform_accounts:
                continue

            title = f"[Cross-Test] {pattern.pattern_name} [{source_platform} -> {target_platform}]"
            if title.lower().strip() in existing_titles:
                continue

            content_types = PLATFORM_CONTENT_TYPES.get(target_platform, [ContentType.SHORT_VIDEO])
            acct = platform_accounts[0]

            brief = ContentBrief(
                brand_id=brand_id,
                creator_account_id=acct.id,
                offer_id=pattern.offer_id,
                title=title,
                content_type=content_types[0],
                target_platform=target_platform,
                hook=f"Cross-platform test: {pattern.pattern_name}",
                angle=f"Winning on {source_platform} ({pattern.monetization_method}) — testing on {target_platform}",
                key_points=[
                    f"Source platform: {source_platform} (win_score: {pattern.win_score:.2f})",
                    f"Monetization method: {pattern.monetization_method}",
                    f"Confidence: {pattern.confidence:.2f}",
                    f"Target platform: {target_platform}",
                ],
                monetization_integration=pattern.monetization_method,
                brief_metadata={
                    "source": "strategy_adjustment_worker",
                    "cross_platform_test": True,
                    "source_pattern_id": str(pattern.id),
                    "source_platform": source_platform,
                    "target_platform": target_platform,
                    "monetization_method": pattern.monetization_method,
                    "auto_generated": True,
                },
                status="draft",
            )
            db.add(brief)
            existing_titles.add(title.lower().strip())

            # Also create a reuse recommendation for tracking
            reuse_rec = PatternReuseRecommendation(
                brand_id=brand_id,
                pattern_id=pattern.id,
                target_platform=target_platform,
                target_content_form=pattern.content_form,
                expected_uplift=pattern.win_score * 0.6,  # conservative estimate
                confidence=pattern.confidence * 0.7,  # discounted for new platform
                explanation=(
                    f"Auto-cross-pollination: {pattern.monetization_method} winning on "
                    f"{source_platform} (score={pattern.win_score:.2f}), testing on {target_platform}"
                ),
                is_active=True,
            )
            db.add(reuse_rec)
            existing_reuse.add((str(pattern.id), target_platform))

            cross_tests += 1

    await db.flush()
    return cross_tests
