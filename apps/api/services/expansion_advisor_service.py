"""Account Expansion Advisor service — recompute + read."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.expansion_advisor import AccountExpansionAdvisory
from packages.db.models.offers import Offer
from packages.scoring.expansion_advisor_engine import compute_expansion_advisory
from packages.scoring.scale import AccountScaleSnapshot, run_scale_engine


async def recompute_advisory(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    accounts_raw = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all())

    snapshots = []
    for a in accounts_raw:
        snapshots.append(AccountScaleSnapshot(
            account_id=str(a.id),
            platform=a.platform.value if hasattr(a.platform, "value") else str(a.platform),
            username=a.platform_username,
            niche_focus=a.niche_focus or "",
            sub_niche_focus=a.sub_niche_focus or "",
            revenue=float(a.total_revenue or 0),
            profit=float(a.total_profit or 0),
            profit_per_post=float(a.profit_per_post or 0),
            revenue_per_mille=float(a.revenue_per_mille or 0),
            ctr=float(a.ctr or 0),
            conversion_rate=float(a.conversion_rate or 0),
            follower_growth_rate=float(a.follower_growth_rate or 0),
            fatigue_score=float(a.fatigue_score or 0),
            saturation_score=float(a.saturation_score or 0),
            originality_drift_score=float(a.originality_drift_score or 0),
            diminishing_returns_score=float(getattr(a, "diminishing_returns_score", 0) or 0),
            posting_capacity_per_day=int(a.posting_capacity_per_day or 1),
            account_health=a.account_health.value if hasattr(a.account_health, "value") else str(a.account_health),
            offer_performance_score=0.5,
            scale_role=a.scale_role,
            impressions_rollup=int(a.follower_count or 0),
        ))

    offers = list((await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all())
    offer_dicts = [{"id": str(o.id), "name": o.name, "epc": float(o.epc or 0), "conversion_rate": float(o.conversion_rate or 0)} for o in offers]

    total_imp = sum(s.impressions_rollup for s in snapshots)
    content_count_scalar = (await db.execute(
        select(func.count(ContentItem.id)).where(ContentItem.brand_id == brand_id)
    )).scalar() or 0

    scale_result_obj = run_scale_engine(
        snapshots, offer_dicts, total_imp, brand.niche,
        funnel_weak=False, weak_offer_diversity=len(offers) < 2,
    )
    scale_dict = {
        "recommendation_key": scale_result_obj.recommendation_key,
        "best_next_account": scale_result_obj.best_next_account,
        "incremental_profit_new_account": scale_result_obj.incremental_profit_new_account,
        "incremental_profit_more_volume": scale_result_obj.incremental_profit_more_volume,
        "scale_readiness_score": scale_result_obj.scale_readiness_score,
        "expansion_confidence": scale_result_obj.expansion_confidence,
        "cannibalization_risk": scale_result_obj.cannibalization_risk,
        "audience_segment_separation": scale_result_obj.audience_segment_separation,
        "explanation": scale_result_obj.explanation,
    }

    account_dicts = [{"id": str(a.id), "platform": s.platform, "username": s.username} for a, s in zip(accounts_raw, snapshots)]
    avg_fatigue = sum(s.fatigue_score for s in snapshots) / max(1, len(snapshots)) if snapshots else 0
    avg_saturation = sum(s.saturation_score for s in snapshots) / max(1, len(snapshots)) if snapshots else 0
    healths = [s.account_health for s in snapshots]
    avg_health = "critical" if any(h == "critical" for h in healths) else "warning" if any(h == "warning" for h in healths) else "healthy"

    advisory = compute_expansion_advisory(
        scale_result=scale_dict,
        accounts=account_dicts,
        brand_niche=brand.niche,
        brand_sub_niche=brand.sub_niche,
        offer_count=len(offers),
        content_count=int(content_count_scalar),
        avg_account_health=avg_health,
        avg_fatigue=avg_fatigue,
        avg_saturation=avg_saturation,
    )

    await db.execute(delete(AccountExpansionAdvisory).where(AccountExpansionAdvisory.brand_id == brand_id))
    db.add(AccountExpansionAdvisory(brand_id=brand_id, **advisory))
    await db.flush()

    from packages.db.models.scale_alerts import LaunchCandidate, OperatorAlert
    if advisory["should_add_account_now"]:
        db.add(OperatorAlert(
            brand_id=brand_id,
            alert_type="expansion_advisor_expand",
            title=f"Expansion Advisor: Add {advisory.get('platform', 'new')} account now",
            summary=advisory["explanation"][:500],
            explanation=advisory["explanation"],
            recommended_action=f"Add {advisory.get('account_type', 'organic')} {advisory.get('platform', '')} account — {advisory.get('content_role', '')} role, {advisory.get('monetization_path', '')[:200]}",
            confidence=float(advisory.get("confidence", 0)),
            urgency=float(advisory.get("urgency", 0)),
            expected_upside=float(advisory.get("expected_upside", 0)),
            expected_cost=float(advisory.get("expected_cost", 0)),
            expected_time_to_signal_days=int(advisory.get("expected_time_to_signal_days", 14)),
            supporting_metrics=advisory.get("evidence", {}),
            blocking_factors=advisory.get("blockers", []),
        ))
        db.add(LaunchCandidate(
            brand_id=brand_id,
            candidate_type="expansion_advisor",
            primary_platform=advisory.get("platform") or "tiktok",
            niche=advisory.get("niche") or brand.niche or "general",
            sub_niche=advisory.get("sub_niche"),
            monetization_path=advisory.get("monetization_path"),
            content_style=advisory.get("content_role"),
            confidence=float(advisory.get("confidence", 0)),
            urgency=float(advisory.get("urgency", 0)),
        ))
        await db.flush()
    else:
        hold_reason = advisory.get("hold_reason", "Expansion not justified yet.")
        blockers = advisory.get("blockers", [])
        blocker_summary = "; ".join(b.get("description", "") for b in blockers[:3]) if blockers else ""

        db.add(OperatorAlert(
            brand_id=brand_id,
            alert_type="expansion_advisor_hold",
            title="Expansion Advisor: DO NOT add account yet",
            summary=f"HOLD: {hold_reason[:300]}",
            explanation=f"{hold_reason} {blocker_summary}".strip(),
            recommended_action=f"Fix: {blocker_summary[:300]}" if blocker_summary else f"Wait until: {hold_reason[:300]}",
            confidence=float(advisory.get("confidence", 0)),
            urgency=30.0,
            supporting_metrics=advisory.get("evidence", {}),
            blocking_factors=blockers,
        ))
        await db.flush()

    return {"rows_processed": 1, "should_add": advisory["should_add_account_now"], "status": "completed"}


async def list_advisories(db: AsyncSession, brand_id: uuid.UUID) -> list:
    return list((await db.execute(
        select(AccountExpansionAdvisory)
        .where(AccountExpansionAdvisory.brand_id == brand_id, AccountExpansionAdvisory.is_active.is_(True))
        .order_by(AccountExpansionAdvisory.created_at.desc())
    )).scalars().all())
