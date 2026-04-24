"""Phase 7 service: sponsor, comment-cash, knowledge graph, roadmap, capital allocation, cockpit.

Architecture: recompute_phase7() is the WRITE path (POST only).
All get_* functions are READ-ONLY.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services import analytics_service as asvc
from apps.api.services import growth_service as gsvc
from packages.db.enums import ConfidenceLevel
from packages.db.models.accounts import CreatorAccount
from packages.db.models.content import ContentItem
from packages.db.models.core import Brand
from packages.db.models.learning import CommentCashSignal, CommentIngestion, KnowledgeGraphEdge, KnowledgeGraphNode
from packages.db.models.offers import AudienceSegment, Offer, SponsorOpportunity, SponsorProfile
from packages.db.models.portfolio import (
    CapitalAllocationRecommendation,
    GeoLanguageExpansionRecommendation,
    PaidAmplificationJob,
    RevenueLeakReport,
    RoadmapRecommendation,
    ScaleRecommendation,
    TrustSignalReport,
)
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.phase7_engines import (
    PHASE7_SOURCE,
    build_knowledge_graph_entries,
    compute_capital_allocation,
    extract_comment_cash_signals,
    generate_roadmap,
    recommend_sponsor_packages,
)
from packages.scoring.winner import ContentPerformance, detect_winners

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _accounts_as_dicts(accounts: list) -> list[dict]:
    return [
        {
            "id": str(a.id),
            "platform": a.platform.value if hasattr(a.platform, "value") else str(a.platform),
            "geography": a.geography,
            "language": a.language,
            "niche_focus": a.niche_focus,
            "follower_count": a.follower_count,
            "is_active": a.is_active,
        }
        for a in accounts
    ]


# ---------------------------------------------------------------------------
# WRITE PATH
# ---------------------------------------------------------------------------

async def recompute_phase7(
    db: AsyncSession,
    brand_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    """Recompute and persist all Phase 7 artifacts. Idempotent."""
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")

    accounts = list(
        (await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True)))).scalars().all()
    )
    acc_dicts = _accounts_as_dicts(accounts)
    offers = list(
        (await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))).scalars().all()
    )
    offer_dicts = [{"id": str(o.id), "name": o.name, "epc": o.epc, "conversion_rate": o.conversion_rate, "payout_amount": o.payout_amount} for o in offers]

    total_rev = sum(float(a.total_revenue or 0) for a in accounts)
    total_profit = sum(float(a.total_profit or 0) for a in accounts)
    total_imps = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.impressions), 0)).where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0

    # Winner detection for roadmap + knowledge graph
    content_items = list(
        (await db.execute(select(ContentItem).where(ContentItem.brand_id == brand_id).limit(100))).scalars().all()
    )
    cp_items = []
    for ci in content_items:
        row = (await db.execute(
            select(
                func.coalesce(func.sum(PerformanceMetric.impressions), 0),
                func.coalesce(func.sum(PerformanceMetric.revenue), 0.0),
                func.coalesce(func.avg(PerformanceMetric.ctr), 0.0),
                func.coalesce(func.avg(PerformanceMetric.engagement_rate), 0.0),
            ).where(PerformanceMetric.content_item_id == ci.id)
        )).one()
        imps, rev, ctr, er = int(row[0]), float(row[1]), float(row[2]), float(row[3])
        profit = rev - float(ci.total_cost or 0)
        rpm = (rev / imps * 1000) if imps > 0 else 0.0
        cp_items.append(ContentPerformance(
            content_id=str(ci.id), title=ci.title, impressions=imps, revenue=rev,
            profit=profit, rpm=rpm, ctr=ctr, engagement_rate=er,
            platform=(ci.platform or "youtube").lower(),
            account_id=str(ci.creator_account_id) if ci.creator_account_id else "",
        ))
    winner_signals = detect_winners(cp_items)
    winner_dicts = [{"content_id": w.content_id, "title": w.title, "win_score": w.win_score, "platform": next((c.platform for c in cp_items if c.content_id == w.content_id), "youtube"), "revenue": next((c.revenue for c in cp_items if c.content_id == w.content_id), 0), "rpm": next((c.rpm for c in cp_items if c.content_id == w.content_id), 0)} for w in winner_signals if w.is_winner]

    # Phase 6 data for roadmap inputs
    leaks = list((await db.execute(
        select(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand_id, RevenueLeakReport.is_resolved.is_(False)).limit(50)
    )).scalars().all())
    leak_dicts = [{"leak_type": l.leak_type, "estimated_leaked_revenue": l.estimated_leaked_revenue, "estimated_recoverable": l.estimated_recoverable, "recommended_fix": l.recommended_fix, "root_cause": l.root_cause} for l in leaks]

    segments = list((await db.execute(
        select(AudienceSegment).where(AudienceSegment.brand_id == brand_id, AudienceSegment.is_active.is_(True))
    )).scalars().all())
    seg_dicts = [{"name": s.name, "estimated_size": s.estimated_size} for s in segments]

    geo_recs = list((await db.execute(
        select(GeoLanguageExpansionRecommendation).where(GeoLanguageExpansionRecommendation.brand_id == brand_id).limit(10)
    )).scalars().all())
    geo_dicts = [{"target_geography": g.target_geography, "target_language": g.target_language, "estimated_revenue_potential": g.estimated_revenue_potential, "rationale": g.rationale} for g in geo_recs]

    scale_rec = (await db.execute(
        select(ScaleRecommendation).where(ScaleRecommendation.brand_id == brand_id).order_by(ScaleRecommendation.created_at.desc()).limit(1)
    )).scalars().first()
    scale_key = scale_rec.recommendation_key if scale_rec else None

    trust_rows = list((await db.execute(
        select(TrustSignalReport).where(TrustSignalReport.brand_id == brand_id)
    )).scalars().all())
    trust_avg = (sum(t.trust_score for t in trust_rows) / len(trust_rows)) if trust_rows else 60.0

    paid_candidates = (await db.execute(
        select(func.count()).select_from(PaidAmplificationJob).where(PaidAmplificationJob.brand_id == brand_id, PaidAmplificationJob.is_candidate.is_(True))
    )).scalar() or 0

    # —— Clean prior Phase 7 rows ——
    await db.execute(delete(CommentCashSignal).where(CommentCashSignal.brand_id == brand_id))
    await db.execute(delete(KnowledgeGraphEdge).where(KnowledgeGraphEdge.brand_id == brand_id))
    await db.execute(delete(KnowledgeGraphNode).where(KnowledgeGraphNode.brand_id == brand_id))
    await db.execute(delete(RoadmapRecommendation).where(RoadmapRecommendation.brand_id == brand_id))
    await db.execute(delete(CapitalAllocationRecommendation).where(CapitalAllocationRecommendation.brand_id == brand_id))

    # —— 1. Sponsor packages (computed but not persisted as rows — returned for display) ——
    sponsor_packages = recommend_sponsor_packages(brand.niche, acc_dicts, total_rev, int(total_imps))

    # —— 2. Comment-to-cash signals ——
    comments = list((await db.execute(
        select(CommentIngestion).where(CommentIngestion.brand_id == brand_id, CommentIngestion.is_processed.is_(True)).limit(500)
    )).scalars().all())
    comment_dicts = [{"comment_text": c.comment_text, "is_purchase_intent": c.is_purchase_intent, "is_question": c.is_question, "is_complaint": c.is_complaint} for c in comments]
    cash_signals = extract_comment_cash_signals(comment_dicts, offer_dicts)
    for cs in cash_signals:
        db.add(CommentCashSignal(
            brand_id=brand_id,
            signal_type=cs["signal_type"],
            signal_strength=cs["signal_strength"],
            estimated_revenue_potential=cs["estimated_revenue_potential"],
            suggested_offer_id=uuid.UUID(cs["suggested_offer_id"]) if cs.get("suggested_offer_id") else None,
            suggested_content_angle=cs.get("suggested_content_angle"),
            explanation=cs.get("explanation"),
        ))

    # —— 3. Knowledge graph ——
    kg_nodes, kg_edges = build_knowledge_graph_entries(brand.niche, acc_dicts, offer_dicts, winner_dicts, seg_dicts, leak_dicts)
    node_id_map: dict[int, uuid.UUID] = {}
    for i, n in enumerate(kg_nodes):
        node = KnowledgeGraphNode(
            brand_id=brand_id, node_type=n["node_type"], label=n["label"],
            properties=n.get("properties", {}), is_active=True,
        )
        db.add(node)
        await db.flush()
        node_id_map[i] = node.id
    for e in kg_edges:
        src_id = node_id_map.get(e["source_idx"])
        tgt_id = node_id_map.get(e["target_idx"])
        if src_id and tgt_id:
            db.add(KnowledgeGraphEdge(
                brand_id=brand_id, source_node_id=src_id, target_node_id=tgt_id,
                edge_type=e["edge_type"], weight=e["weight"],
                properties=e.get("properties", {}), is_active=True,
            ))

    # —— 4. Roadmap ——
    roadmap = generate_roadmap(brand.niche, acc_dicts, offer_dicts, winner_dicts, leak_dicts, seg_dicts, geo_dicts, scale_key, trust_avg)
    for rm in roadmap:
        conf = ConfidenceLevel.HIGH if rm["priority_score"] >= 75 else (ConfidenceLevel.MEDIUM if rm["priority_score"] >= 50 else ConfidenceLevel.LOW)
        db.add(RoadmapRecommendation(
            brand_id=brand_id, category=rm["category"], title=rm["title"][:500],
            description=rm.get("description"), priority_score=rm["priority_score"],
            estimated_impact_revenue=rm["estimated_impact_revenue"],
            estimated_effort=rm.get("estimated_effort", "medium"),
            confidence=conf, rationale=rm.get("rationale"),
            inputs_used={PHASE7_SOURCE: True},
        ))

    # —— 5. Capital allocation ——
    from packages.db.models.portfolio import MonetizationRecommendation
    prod_rec_count = (await db.execute(
        select(func.count()).select_from(MonetizationRecommendation).where(
            MonetizationRecommendation.brand_id == brand_id,
            MonetizationRecommendation.recommendation_type == "productization",
        )
    )).scalar() or 0
    owned_size = sum(a.follower_count for a in accounts)
    cap_allocs = compute_capital_allocation(
        total_budget=total_profit * 0.3,
        total_revenue=total_rev, total_profit=total_profit,
        accounts=acc_dicts, offers=offer_dicts,
        leak_count=len(leaks), paid_candidate_count=paid_candidates,
        geo_rec_count=len(geo_recs), trust_avg=trust_avg, scale_rec_key=scale_key,
        productization_rec_count=prod_rec_count, owned_audience_size=owned_size,
    )
    for ca in cap_allocs:
        db.add(CapitalAllocationRecommendation(
            brand_id=brand_id,
            allocation_target_type=ca["allocation_target_type"],
            recommended_allocation_pct=ca["recommended_allocation_pct"],
            expected_marginal_roi=ca["expected_marginal_roi"],
            rationale=ca["rationale"],
            inputs_snapshot={PHASE7_SOURCE: True, "budget_base": round(total_profit * 0.3, 2)},
            confidence=ConfidenceLevel.MEDIUM,
        ))

    await db.flush()
    return {
        "sponsor_packages": len(sponsor_packages),
        "comment_cash_signals": len(cash_signals),
        "knowledge_graph_nodes": len(kg_nodes),
        "knowledge_graph_edges": len(kg_edges),
        "roadmap_items": len(roadmap),
        "capital_allocations": len(cap_allocs),
    }


# ---------------------------------------------------------------------------
# READ PATH (all side-effect free)
# ---------------------------------------------------------------------------

async def get_sponsor_opportunities(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    accounts = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all())
    total_rev = sum(float(a.total_revenue or 0) for a in accounts)
    total_imps = (await db.execute(
        select(func.coalesce(func.sum(PerformanceMetric.impressions), 0)).where(PerformanceMetric.brand_id == brand_id)
    )).scalar() or 0
    packages = recommend_sponsor_packages(brand.niche if brand else None, _accounts_as_dicts(accounts), total_rev, int(total_imps))

    profiles = list((await db.execute(
        select(SponsorProfile).where(SponsorProfile.brand_id == brand_id, SponsorProfile.is_active.is_(True))
    )).scalars().all())
    opps = list((await db.execute(
        select(SponsorOpportunity).where(SponsorOpportunity.brand_id == brand_id).order_by(SponsorOpportunity.deal_value.desc())
    )).scalars().all())

    return {
        "packages": packages,
        "profiles": [{"id": str(p.id), "sponsor_name": p.sponsor_name, "industry": p.industry, "budget_range_min": p.budget_range_min, "budget_range_max": p.budget_range_max} for p in profiles],
        "opportunities": [{"id": str(o.id), "title": o.title, "deal_value": o.deal_value, "status": o.status, "sponsor_id": str(o.sponsor_id)} for o in opps],
    }


async def get_comment_cash_signals(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    rows = list((await db.execute(
        select(CommentCashSignal).where(CommentCashSignal.brand_id == brand_id).order_by(CommentCashSignal.signal_strength.desc())
    )).scalars().all())
    return {
        "signals": [
            {
                "id": str(s.id), "signal_type": s.signal_type,
                "signal_strength": s.signal_strength,
                "estimated_revenue_potential": s.estimated_revenue_potential,
                "suggested_content_angle": s.suggested_content_angle,
                "explanation": s.explanation, "is_actioned": s.is_actioned,
            }
            for s in rows
        ]
    }


async def get_roadmap(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    rows = list((await db.execute(
        select(RoadmapRecommendation).where(RoadmapRecommendation.brand_id == brand_id).order_by(RoadmapRecommendation.priority_score.desc())
    )).scalars().all())
    return {
        "items": [
            {
                "id": str(r.id), "category": r.category, "title": r.title,
                "description": r.description, "priority_score": r.priority_score,
                "estimated_impact_revenue": r.estimated_impact_revenue,
                "estimated_effort": r.estimated_effort,
                "confidence": r.confidence.value if hasattr(r.confidence, "value") else str(r.confidence),
                "rationale": r.rationale, "is_actioned": r.is_actioned,
            }
            for r in rows
        ]
    }


async def get_capital_allocation(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    rows = list((await db.execute(
        select(CapitalAllocationRecommendation).where(CapitalAllocationRecommendation.brand_id == brand_id).order_by(CapitalAllocationRecommendation.recommended_allocation_pct.desc())
    )).scalars().all())
    return {
        "allocations": [
            {
                "id": str(r.id), "allocation_target_type": r.allocation_target_type,
                "recommended_allocation_pct": r.recommended_allocation_pct,
                "expected_marginal_roi": r.expected_marginal_roi,
                "rationale": r.rationale, "is_actioned": r.is_actioned,
            }
            for r in rows
        ]
    }


async def get_knowledge_graph(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    nodes = list((await db.execute(
        select(KnowledgeGraphNode).where(KnowledgeGraphNode.brand_id == brand_id, KnowledgeGraphNode.is_active.is_(True))
    )).scalars().all())
    edges = list((await db.execute(
        select(KnowledgeGraphEdge).where(KnowledgeGraphEdge.brand_id == brand_id, KnowledgeGraphEdge.is_active.is_(True))
    )).scalars().all())
    return {
        "nodes": [{"id": str(n.id), "node_type": n.node_type, "label": n.label, "properties": n.properties} for n in nodes],
        "edges": [{"id": str(e.id), "source_node_id": str(e.source_node_id), "target_node_id": str(e.target_node_id), "edge_type": e.edge_type, "weight": e.weight} for e in edges],
    }


async def get_operator_cockpit(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Aggregate best opportunities, leaks, scale actions, blockers, expansion — read only."""
    roadmap = await get_roadmap(db, brand_id)
    capital = await get_capital_allocation(db, brand_id)
    leaks_data = await gsvc.get_leak_reports_dashboard(db, brand_id)
    sponsors = await get_sponsor_opportunities(db, brand_id)
    cash = await get_comment_cash_signals(db, brand_id)

    scale_rec = (await db.execute(
        select(ScaleRecommendation).where(ScaleRecommendation.brand_id == brand_id).order_by(ScaleRecommendation.created_at.desc()).limit(1)
    )).scalars().first()
    scale_action = {
        "recommendation_key": scale_rec.recommendation_key if scale_rec else "none",
        "explanation": scale_rec.explanation if scale_rec else "Run scale recompute first.",
        "scale_readiness_score": scale_rec.scale_readiness_score if scale_rec else 0,
    } if scale_rec else {"recommendation_key": "none", "explanation": "No scale data yet.", "scale_readiness_score": 0}

    blockers = await asvc.classify_bottlenecks(db, brand_id)
    trust_rows = list((await db.execute(
        select(TrustSignalReport).where(TrustSignalReport.brand_id == brand_id)
    )).scalars().all())
    trust_avg = round(sum(t.trust_score for t in trust_rows) / max(1, len(trust_rows)), 1) if trust_rows else 0

    geo_recs = list((await db.execute(
        select(GeoLanguageExpansionRecommendation).where(GeoLanguageExpansionRecommendation.brand_id == brand_id).limit(5)
    )).scalars().all())

    from apps.api.services import growth_commander_service as gcs
    from apps.api.services import revenue_service as rsvc
    rev_stacks = await rsvc.get_offer_stacks(db, brand_id)
    rev_funnels = await rsvc.get_funnel_paths(db, brand_id)
    growth_cmds = await gcs.get_growth_commands(db, brand_id)

    return {
        "brand_id": str(brand_id),
        "top_roadmap_items": roadmap["items"][:5],
        "capital_allocation": capital["allocations"],
        "open_leaks": leaks_data["leaks"][:5],
        "leak_summary": leaks_data["summary"],
        "scale_action": scale_action,
        "growth_blockers": blockers[:5],
        "trust_avg": trust_avg,
        "sponsor_packages": sponsors["packages"][:3],
        "comment_cash_signals": cash["signals"][:5],
        "expansion_targets": [{"geography": g.target_geography, "language": g.target_language, "revenue_potential": g.estimated_revenue_potential} for g in geo_recs],
        "top_offer_stacks": rev_stacks[:3],
        "worst_funnel_paths": rev_funnels[:3],
        "growth_commands": growth_cmds[:5],
    }
