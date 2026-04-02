"""Portfolio launch pack: persisted plans, allocations, blockers, capital, cannibalization, output."""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.growth_pack import (
    AccountLaunchBlueprint,
    CapitalDeploymentPlan,
    CrossAccountCannibalizationReport,
    GrowthPackBlockerReport,
    NicheDeploymentReport,
    PlatformAllocationReport,
    PortfolioLaunchPlan,
    PortfolioOutputReport,
)
from apps.api.services.growth_gatekeeper_pipeline import apply_gatekeeper_pipeline, load_gatekeeper_dict_only
from packages.db.models.offers import Offer
from packages.db.models.portfolio import (
    GeoLanguageExpansionRecommendation,
    RevenuLeakReport,
    ScaleRecommendation,
    TrustSignalReport,
)
from packages.db.models.scale_alerts import LaunchCandidate, LaunchReadinessReport, ScaleBlockerReport
from packages.scoring.growth_commander import (
    assess_portfolio_balance, find_whitespace, generate_growth_commands,
)
from packages.scoring.growth_pack.gatekeeper import gatekeeper_blocker_rows, pick_primary_gate
from packages.scoring.growth_pack.orchestrator import (
    build_capital_plan,
    build_cannibalization_pairs,
    build_growth_blockers,
    build_launch_blueprints_from_commands,
    build_niche_rows,
    build_platform_allocation_rows,
    build_portfolio_launch_plan,
    build_portfolio_output,
)


def _acct_dicts(accounts: list) -> list[dict]:
    return [{
        "id": str(a.id),
        "platform": a.platform.value if hasattr(a.platform, "value") else str(a.platform),
        "geography": a.geography,
        "language": a.language,
        "niche_focus": a.niche_focus,
        "username": a.platform_username,
        "follower_count": a.follower_count,
        "fatigue_score": float(a.fatigue_score or 0),
        "saturation_score": float(a.saturation_score or 0),
        "originality_drift_score": float(a.originality_drift_score or 0),
        "account_health": a.account_health.value if hasattr(a.account_health, "value") else str(a.account_health),
        "profit_per_post": float(a.profit_per_post or 0),
        "revenue_per_mille": float(a.revenue_per_mille or 0),
        "posting_capacity_per_day": a.posting_capacity_per_day,
        "scale_role": getattr(a, "scale_role", None) or "",
    } for a in accounts]


async def _load_generation_inputs(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    if not brand:
        raise ValueError("Brand not found")
    accounts = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all())
    acc_dicts = _acct_dicts(accounts)
    offers = list((await db.execute(
        select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalars().all())
    offer_dicts = [{"id": str(o.id), "name": o.name} for o in offers]
    scale_rec = (await db.execute(
        select(ScaleRecommendation).where(ScaleRecommendation.brand_id == brand_id)
        .order_by(ScaleRecommendation.created_at.desc()).limit(1)
    )).scalars().first()
    scale_dict = {
        "recommendation_key": scale_rec.recommendation_key if scale_rec else "monitor",
        "scale_readiness_score": scale_rec.scale_readiness_score if scale_rec else 0,
        "incremental_profit_new_account": scale_rec.incremental_profit_new_account if scale_rec else 0,
        "incremental_profit_existing_push": scale_rec.incremental_profit_existing_push if scale_rec else 0,
        "explanation": scale_rec.explanation if scale_rec else "",
        "best_next_account": (scale_rec.best_next_account or {}) if scale_rec else {},
        "id": str(scale_rec.id) if scale_rec else None,
        "recommended_account_count": int(scale_rec.recommended_account_count) if scale_rec else max(1, len(acc_dicts)),
        "expansion_confidence": float(scale_rec.expansion_confidence) if scale_rec else 0.0,
    }
    candidates = list((await db.execute(
        select(LaunchCandidate).where(LaunchCandidate.brand_id == brand_id, LaunchCandidate.is_active.is_(True))
    )).scalars().all())
    cand_dicts = [{
        "id": str(c.id), "candidate_type": c.candidate_type,
        "primary_platform": c.primary_platform, "secondary_platform": c.secondary_platform,
        "niche": c.niche, "sub_niche": c.sub_niche,
        "language": c.language, "geography": c.geography,
        "avatar_persona_strategy": c.avatar_persona_strategy,
        "monetization_path": c.monetization_path,
        "content_style": c.content_style, "posting_strategy": c.posting_strategy,
        "expected_monthly_revenue_min": c.expected_monthly_revenue_min,
        "expected_monthly_revenue_max": c.expected_monthly_revenue_max,
        "expected_launch_cost": c.expected_launch_cost,
        "expected_time_to_signal_days": c.expected_time_to_signal_days,
        "expected_time_to_profit_days": c.expected_time_to_profit_days,
        "cannibalization_risk": c.cannibalization_risk,
        "audience_separation_score": c.audience_separation_score,
        "confidence": c.confidence, "urgency": c.urgency,
        "supporting_reasons": c.supporting_reasons or [],
        "launch_blockers": c.launch_blockers or [],
    } for c in candidates]
    blockers = list((await db.execute(
        select(ScaleBlockerReport).where(ScaleBlockerReport.brand_id == brand_id, ScaleBlockerReport.is_resolved.is_(False))
    )).scalars().all())
    blocker_dicts = [{"blocker_type": b.blocker_type, "severity": b.severity, "title": b.title} for b in blockers]
    readiness = (await db.execute(
        select(LaunchReadinessReport).where(LaunchReadinessReport.brand_id == brand_id, LaunchReadinessReport.is_active.is_(True))
        .order_by(LaunchReadinessReport.created_at.desc()).limit(1)
    )).scalars().first()
    readiness_dict = {"launch_readiness_score": readiness.launch_readiness_score, "recommended_action": readiness.recommended_action} if readiness else None
    trust_rows = list((await db.execute(select(TrustSignalReport).where(TrustSignalReport.brand_id == brand_id))).scalars().all())
    trust_avg = round(sum(t.trust_score for t in trust_rows) / max(1, len(trust_rows)), 1) if trust_rows else 60.0
    leak_count = (await db.execute(
        select(func.count()).select_from(RevenuLeakReport).where(RevenuLeakReport.brand_id == brand_id, RevenuLeakReport.is_resolved.is_(False))
    )).scalar() or 0
    geo_recs = list((await db.execute(
        select(GeoLanguageExpansionRecommendation).where(GeoLanguageExpansionRecommendation.brand_id == brand_id).limit(10)
    )).scalars().all())
    geo_dicts = [{"target_geography": g.target_geography, "target_language": g.target_language, "estimated_revenue_potential": g.estimated_revenue_potential} for g in geo_recs]
    balance = assess_portfolio_balance(acc_dicts)
    whitespace = find_whitespace(acc_dicts, brand.niche, geo_dicts)
    commands = generate_growth_commands(
        scale_dict, cand_dicts, blocker_dicts, readiness_dict,
        acc_dicts, offer_dicts, brand.niche, trust_avg, leak_count, geo_dicts,
    )
    commands = await apply_gatekeeper_pipeline(
        db, brand_id,
        commands=commands,
        acc_dicts=acc_dicts,
        scale_dict=scale_dict,
        readiness_dict=readiness_dict,
        trust_avg=trust_avg,
        leak_count=leak_count,
        brand_niche=brand.niche,
    )
    by_plat: dict[str, int] = defaultdict(int)
    for a in acc_dicts:
        by_plat[(a.get("platform") or "youtube").lower()] += 1
    return {
        "brand": brand,
        "acc_dicts": acc_dicts,
        "scale_dict": scale_dict,
        "cand_dicts": cand_dicts,
        "blocker_dicts": blocker_dicts,
        "leak_count": leak_count,
        "balance": balance,
        "whitespace": whitespace,
        "commands": commands,
        "accounts_by_platform": dict(by_plat),
    }


async def recompute_portfolio_launch_plan(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    launch_cmds = [c for c in ctx["commands"] if c.get("command_type") == "launch_account"]
    rec_total = int(ctx["scale_dict"].get("recommended_account_count") or len(ctx["acc_dicts"]))
    mix = {p: int(n) for p, n in ctx["accounts_by_platform"].items()}
    order = [{"rank": i + 1, "command_type": c.get("command_type"), "title": c.get("title")} for i, c in enumerate(ctx["commands"][:5])]
    role_mix = {"flagship": 1, "growth": max(0, rec_total - 1)}
    cost_90 = sum(float(c.get("expected_cost") or 0) for c in launch_cmds[:3]) + 500.0
    rev_max = sum(float(c.get("expected_upside") or 0) for c in launch_cmds[:3]) * 3
    plan = build_portfolio_launch_plan(
        recommended_total=rec_total,
        platform_mix=mix,
        launch_order=order,
        role_mix=role_mix,
        cost_90=cost_90,
        rev_min_90=rev_max * 0.3,
        rev_max_90=rev_max,
        confidence=float(ctx["scale_dict"].get("expansion_confidence") or 0.55),
        explanation={"sources": ["scale_recommendation", "growth_commander_engine"], "comparison": launch_cmds[0].get("comparison") if launch_cmds else {}},
    )
    await db.execute(delete(PortfolioLaunchPlan).where(PortfolioLaunchPlan.brand_id == brand_id))
    db.add(PortfolioLaunchPlan(brand_id=brand_id, **plan))
    await db.flush()
    return {"portfolio_launch_plan": plan}


async def recompute_account_blueprints(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    launch_cmds = [c for c in ctx["commands"] if c.get("command_type") in ("launch_account", "shift_platform", "shift_niche")]
    rows = build_launch_blueprints_from_commands(launch_cmds, ctx["brand"].niche or "")
    await db.execute(delete(AccountLaunchBlueprint).where(AccountLaunchBlueprint.brand_id == brand_id))
    for row in rows:
        db.add(AccountLaunchBlueprint(brand_id=brand_id, **row))
    await db.flush()
    return {"blueprints_created": len(rows)}


async def recompute_platform_allocation(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    rows = build_platform_allocation_rows(ctx["accounts_by_platform"], ctx["scale_dict"], ctx["brand"].niche or "")
    await db.execute(delete(PlatformAllocationReport).where(PlatformAllocationReport.brand_id == brand_id))
    for row in rows:
        db.add(PlatformAllocationReport(brand_id=brand_id, **row))
    await db.flush()
    return {"rows": len(rows)}


async def recompute_niche_deployment(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    rows = build_niche_rows(ctx["whitespace"], ctx["cand_dicts"], ctx["brand"].niche or "")
    await db.execute(delete(NicheDeploymentReport).where(NicheDeploymentReport.brand_id == brand_id))
    for row in rows:
        db.add(NicheDeploymentReport(brand_id=brand_id, **row))
    await db.flush()
    return {"rows": len(rows)}


async def recompute_growth_blockers_pack(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    readiness = (await db.execute(
        select(LaunchReadinessReport).where(LaunchReadinessReport.brand_id == brand_id, LaunchReadinessReport.is_active.is_(True))
        .order_by(LaunchReadinessReport.created_at.desc()).limit(1)
    )).scalars().first()
    funnel_weak = bool(readiness and readiness.launch_readiness_score < 50)
    readiness_dict = {"launch_readiness_score": readiness.launch_readiness_score, "recommended_action": readiness.recommended_action} if readiness else None
    trust_rows = list((await db.execute(select(TrustSignalReport).where(TrustSignalReport.brand_id == brand_id))).scalars().all())
    trust_avg = round(sum(t.trust_score for t in trust_rows) / max(1, len(trust_rows)), 1) if trust_rows else 60.0
    gk = await load_gatekeeper_dict_only(
        db, brand_id,
        acc_dicts=ctx["acc_dicts"],
        scale_dict=ctx["scale_dict"],
        readiness_dict=readiness_dict,
        trust_avg=trust_avg,
        leak_count=ctx["leak_count"],
    )
    pairs = build_cannibalization_pairs(ctx["acc_dicts"])
    has_high = any(p["risk_level"] == "high" for p in pairs)
    gk_key, gk_expl = pick_primary_gate(gk, has_high_cannibalization=has_high)
    extra = gatekeeper_blocker_rows(gk_key, gk_expl, gk)
    rows = build_growth_blockers(ctx["leak_count"], ctx["blocker_dicts"], funnel_weak, extra_rows=extra)
    await db.execute(delete(GrowthPackBlockerReport).where(GrowthPackBlockerReport.brand_id == brand_id))
    for row in rows:
        db.add(GrowthPackBlockerReport(brand_id=brand_id, **row))
    await db.flush()
    return {"rows": len(rows)}


async def recompute_capital_deployment(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    total = 5000.0 + float(ctx["scale_dict"].get("incremental_profit_new_account") or 0) * 10
    constrained = ctx["leak_count"] > 5 or any(c.get("command_type") == "fix_funnel_first" for c in ctx["commands"])
    plat_mix = {p: round(total / max(1, len(ctx["accounts_by_platform"])) * 0.15, 2) for p in ctx["accounts_by_platform"]} or {"youtube": round(total * 0.3, 2)}
    plan = build_capital_plan(total, plat_mix, constrained)
    await db.execute(delete(CapitalDeploymentPlan).where(CapitalDeploymentPlan.brand_id == brand_id))
    db.add(CapitalDeploymentPlan(brand_id=brand_id, **plan))
    await db.flush()
    return {"capital_deployment": plan}


async def recompute_cross_account_cannibalization(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    pairs = build_cannibalization_pairs(ctx["acc_dicts"])
    await db.execute(delete(CrossAccountCannibalizationReport).where(CrossAccountCannibalizationReport.brand_id == brand_id))
    for p in pairs:
        db.add(CrossAccountCannibalizationReport(
            brand_id=brand_id,
            account_a_id=uuid.UUID(p["account_a_id"]),
            account_b_id=uuid.UUID(p["account_b_id"]),
            overlap_score=p["overlap_score"],
            audience_overlap_score=p["audience_overlap_score"],
            topic_overlap_score=p["topic_overlap_score"],
            monetization_overlap_score=p["monetization_overlap_score"],
            risk_level=p["risk_level"],
            recommendation_json=p["recommendation_json"],
        ))
    await db.flush()
    return {"pairs": len(pairs)}


async def recompute_portfolio_output(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _load_generation_inputs(db, brand_id)
    out = build_portfolio_output(ctx["acc_dicts"], ctx["accounts_by_platform"])
    await db.execute(delete(PortfolioOutputReport).where(PortfolioOutputReport.brand_id == brand_id))
    db.add(PortfolioOutputReport(brand_id=brand_id, **out))
    await db.flush()
    return {"portfolio_output": out}


# --- read-only getters ---

def _bp_ser(b: AccountLaunchBlueprint) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "brand_id": str(b.brand_id),
        "platform": b.platform,
        "account_type": b.account_type,
        "niche": b.niche,
        "sub_niche": b.sub_niche,
        "avatar_id": str(b.avatar_id) if b.avatar_id else None,
        "persona_strategy_json": b.persona_strategy_json,
        "monetization_strategy_json": b.monetization_strategy_json,
        "content_role": b.content_role,
        "first_30_content_plan_json": b.first_30_content_plan_json,
        "first_offer_stack_json": b.first_offer_stack_json,
        "first_cta_strategy_json": b.first_cta_strategy_json,
        "first_owned_audience_strategy_json": b.first_owned_audience_strategy_json,
        "success_criteria_json": b.success_criteria_json,
        "failure_criteria_json": b.failure_criteria_json,
        "expected_cost": b.expected_cost,
        "expected_time_to_signal_days": b.expected_time_to_signal_days,
        "confidence_score": b.confidence_score,
        "explanation_json": b.explanation_json,
        "created_at": str(b.created_at),
    }


async def list_portfolio_launch_plans(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(PortfolioLaunchPlan).where(PortfolioLaunchPlan.brand_id == brand_id).order_by(PortfolioLaunchPlan.created_at.desc()).limit(5)
    )).scalars().all())
    return [{
        "id": str(r.id),
        "recommended_total_account_count": r.recommended_total_account_count,
        "recommended_platform_mix_json": r.recommended_platform_mix_json,
        "recommended_launch_order_json": r.recommended_launch_order_json,
        "recommended_role_mix_json": r.recommended_role_mix_json,
        "estimated_first_90_day_cost": r.estimated_first_90_day_cost,
        "expected_first_90_day_revenue_min": r.expected_first_90_day_revenue_min,
        "expected_first_90_day_revenue_max": r.expected_first_90_day_revenue_max,
        "confidence_score": r.confidence_score,
        "explanation_json": r.explanation_json,
        "created_at": str(r.created_at),
    } for r in rows]


async def list_account_blueprints(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(AccountLaunchBlueprint).where(AccountLaunchBlueprint.brand_id == brand_id).order_by(AccountLaunchBlueprint.created_at.desc())
    )).scalars().all())
    return [_bp_ser(b) for b in rows]


async def get_account_blueprint(db: AsyncSession, blueprint_id: uuid.UUID) -> Optional[dict]:
    b = (await db.execute(select(AccountLaunchBlueprint).where(AccountLaunchBlueprint.id == blueprint_id))).scalar_one_or_none()
    return _bp_ser(b) if b else None


async def list_platform_allocation(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(PlatformAllocationReport).where(PlatformAllocationReport.brand_id == brand_id).order_by(PlatformAllocationReport.expansion_priority.desc())
    )).scalars().all())
    return [{
        "id": str(r.id),
        "platform": r.platform,
        "recommended_account_count": r.recommended_account_count,
        "current_account_count": r.current_account_count,
        "expansion_priority": r.expansion_priority,
        "rationale_json": r.rationale_json,
        "expected_upside": r.expected_upside,
        "confidence_score": r.confidence_score,
        "created_at": str(r.created_at),
    } for r in rows]


async def list_niche_deployment(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(NicheDeploymentReport).where(NicheDeploymentReport.brand_id == brand_id).order_by(NicheDeploymentReport.expected_upside.desc())
    )).scalars().all())
    return [{
        "id": str(r.id),
        "niche": r.niche,
        "sub_niche": r.sub_niche,
        "recommended_account_role": r.recommended_account_role,
        "recommended_platform": r.recommended_platform,
        "expected_upside": r.expected_upside,
        "saturation_risk": r.saturation_risk,
        "cannibalization_risk": r.cannibalization_risk,
        "confidence_score": r.confidence_score,
        "explanation_json": r.explanation_json,
        "created_at": str(r.created_at),
    } for r in rows]


async def list_growth_blockers_pack(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(GrowthPackBlockerReport).where(GrowthPackBlockerReport.brand_id == brand_id).order_by(GrowthPackBlockerReport.urgency_score.desc())
    )).scalars().all())
    return [{
        "id": str(r.id),
        "blocker_type": r.blocker_type,
        "severity": r.severity,
        "affected_scope_type": r.affected_scope_type,
        "affected_scope_id": str(r.affected_scope_id) if r.affected_scope_id else None,
        "reason": r.reason,
        "recommended_fix": r.recommended_fix,
        "expected_impact_json": r.expected_impact_json,
        "confidence_score": r.confidence_score,
        "urgency_score": r.urgency_score,
        "created_at": str(r.created_at),
    } for r in rows]


async def list_capital_deployment(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(CapitalDeploymentPlan).where(CapitalDeploymentPlan.brand_id == brand_id).order_by(CapitalDeploymentPlan.created_at.desc()).limit(3)
    )).scalars().all())
    return [{
        "id": str(r.id),
        "total_budget": r.total_budget,
        "platform_budget_mix_json": r.platform_budget_mix_json,
        "account_budget_mix_json": r.account_budget_mix_json,
        "content_budget_mix_json": r.content_budget_mix_json,
        "funnel_budget_mix_json": r.funnel_budget_mix_json,
        "paid_budget_mix_json": r.paid_budget_mix_json,
        "holdback_budget": r.holdback_budget,
        "explanation_json": r.explanation_json,
        "confidence_score": r.confidence_score,
        "created_at": str(r.created_at),
    } for r in rows]


async def list_cross_cannibalization(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(CrossAccountCannibalizationReport).where(CrossAccountCannibalizationReport.brand_id == brand_id).order_by(CrossAccountCannibalizationReport.overlap_score.desc())
    )).scalars().all())
    return [{
        "id": str(r.id),
        "account_a_id": str(r.account_a_id),
        "account_b_id": str(r.account_b_id),
        "overlap_score": r.overlap_score,
        "audience_overlap_score": r.audience_overlap_score,
        "topic_overlap_score": r.topic_overlap_score,
        "monetization_overlap_score": r.monetization_overlap_score,
        "risk_level": r.risk_level,
        "recommendation_json": r.recommendation_json,
        "created_at": str(r.created_at),
    } for r in rows]


async def list_portfolio_output(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(PortfolioOutputReport).where(PortfolioOutputReport.brand_id == brand_id).order_by(PortfolioOutputReport.created_at.desc()).limit(3)
    )).scalars().all())
    return [{
        "id": str(r.id),
        "total_output_recommendation": r.total_output_recommendation,
        "per_platform_output_json": r.per_platform_output_json,
        "per_account_output_json": r.per_account_output_json,
        "duplication_risk_score": r.duplication_risk_score,
        "saturation_risk_score": r.saturation_risk_score,
        "throttle_recommendation_json": r.throttle_recommendation_json,
        "created_at": str(r.created_at),
    } for r in rows]
