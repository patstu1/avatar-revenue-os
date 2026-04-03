"""Growth Commander service: exact portfolio-expansion commands.

Architecture: recompute is WRITE (POST only). All get_* are READ-ONLY.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.db.models.portfolio import (
    GeoLanguageExpansionRecommendation, RevenueLeakReport,
    ScaleRecommendation, TrustSignalReport,
)
from packages.db.models.scale_alerts import (
    GrowthCommand, GrowthCommandRun, LaunchCandidate, LaunchReadinessReport,
    OperatorAlert, ScaleBlockerReport,
)
from packages.scoring.growth_commander import (
    assess_portfolio_balance, compute_portfolio_directive, find_whitespace, generate_growth_commands,
)
from packages.scoring.growth_pack.orchestrator import canonical_fields_from_command
from apps.api.services.audit_service import log_action as audit_log_action
from apps.api.services.growth_gatekeeper_pipeline import apply_gatekeeper_pipeline


def _acct_dicts(accounts: list) -> list[dict]:
    return [{
        "id": str(a.id), "platform": a.platform.value if hasattr(a.platform, "value") else str(a.platform),
        "geography": a.geography, "language": a.language, "niche_focus": a.niche_focus,
        "username": a.platform_username, "follower_count": a.follower_count,
        "fatigue_score": float(a.fatigue_score or 0), "saturation_score": float(a.saturation_score or 0),
        "originality_drift_score": float(a.originality_drift_score or 0),
        "account_health": a.account_health.value if hasattr(a.account_health, "value") else str(a.account_health),
        "profit_per_post": float(a.profit_per_post or 0),
        "revenue_per_mille": float(a.revenue_per_mille or 0),
        "posting_capacity_per_day": a.posting_capacity_per_day,
        "scale_role": getattr(a, "scale_role", None) or "",
    } for a in accounts]


async def recompute_growth_commands(
    db: AsyncSession,
    brand_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
) -> dict[str, Any]:
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
        select(func.count()).select_from(RevenueLeakReport).where(RevenueLeakReport.brand_id == brand_id, RevenueLeakReport.is_resolved.is_(False))
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
    portfolio_directive = compute_portfolio_directive(
        len(acc_dicts), scale_dict, balance, commands, leak_count,
    )

    run = GrowthCommandRun(
        brand_id=brand_id,
        triggered_by_user_id=user_id,
        status="processing",
        commands_generated=0,
        command_types=[],
        portfolio_balance_snapshot={},
        whitespace_count=0,
        portfolio_directive={},
    )
    db.add(run)
    await db.flush()

    scale_rid = uuid.UUID(scale_dict["id"]) if scale_dict.get("id") else None

    try:
        await db.execute(
            update(GrowthCommand)
            .where(
                GrowthCommand.brand_id == brand_id,
                GrowthCommand.is_active.is_(True),
            )
            .values(
                is_active=False,
                superseded_at=func.now(),
                superseded_by_run_id=run.id,
            )
        )

        for cmd in commands:
            cf = canonical_fields_from_command(cmd)
            db.add(GrowthCommand(
                brand_id=brand_id, command_type=cmd["command_type"],
                priority=cmd["priority"], title=cmd["title"][:500],
                exact_instruction=cmd["exact_instruction"], rationale=cmd.get("rationale"),
                comparison=cmd.get("comparison"), platform_fit=cmd.get("platform_fit"),
                niche_fit=cmd.get("niche_fit"), monetization_path=cmd.get("monetization_path"),
                cannibalization_analysis=cmd.get("cannibalization_analysis"),
                success_threshold=cmd.get("success_threshold"), failure_threshold=cmd.get("failure_threshold"),
                expected_upside=cmd["expected_upside"], expected_cost=cmd["expected_cost"],
                expected_time_to_signal_days=cmd["expected_time_to_signal_days"],
                expected_time_to_profit_days=cmd["expected_time_to_profit_days"],
                confidence=cmd["confidence"], urgency=cmd["urgency"],
                blocking_factors=cmd.get("blocking_factors"),
                first_week_plan=cmd.get("first_week_plan"),
                linked_launch_candidate_id=uuid.UUID(cmd["linked_launch_candidate_id"]) if cmd.get("linked_launch_candidate_id") else None,
                linked_scale_recommendation_id=uuid.UUID(cmd["linked_scale_recommendation_id"]) if cmd.get("linked_scale_recommendation_id") else None,
                evidence=cmd.get("evidence"),
                execution_spec=cmd.get("execution_spec") or {},
                required_resources=cmd.get("required_resources") or {},
                created_in_run_id=run.id,
                command_priority=cf["command_priority"],
                action_deadline=cf["action_deadline"],
                platform=cf["platform"],
                account_type=cf["account_type"],
                niche=cf["niche"],
                sub_niche=cf["sub_niche"],
                persona_strategy_json=cf["persona_strategy_json"],
                monetization_strategy_json=cf["monetization_strategy_json"],
                output_requirements_json=cf["output_requirements_json"],
                success_threshold_json=cf["success_threshold_json"],
                failure_threshold_json=cf["failure_threshold_json"],
                expected_revenue_min=cf["expected_revenue_min"],
                expected_revenue_max=cf["expected_revenue_max"],
                risk_score=cf["risk_score"],
                blockers_json=cf["blockers_json"],
                explanation_json=cf["explanation_json"],
                consequence_if_ignored_json=cf["consequence_if_ignored_json"],
                lifecycle_status=cf["lifecycle_status"],
            ))

        run.status = "completed"
        run.commands_generated = len(commands)
        run.command_types = [c["command_type"] for c in commands]
        run.portfolio_balance_snapshot = balance
        run.whitespace_count = len(whitespace)
        run.portfolio_directive = portfolio_directive
        await db.flush()

        await _sync_growth_operator_alerts(db, brand_id, commands, scale_rid)

    except Exception as exc:
        run.status = "failed"
        run.error_message = str(exc)[:4000]
        await db.flush()
        await audit_log_action(
            db, "growth_commander.recompute_failed",
            organization_id=brand.organization_id,
            brand_id=brand_id, user_id=user_id, actor_type="system",
            entity_type="growth_command_run", entity_id=run.id,
            details={"error": str(exc)[:2000]},
        )
        raise

    return {
        "commands_generated": len(commands),
        "command_types": [c["command_type"] for c in commands],
        "portfolio_balance": balance,
        "whitespace_opportunities": len(whitespace),
        "portfolio_directive": portfolio_directive,
        "last_run_id": str(run.id),
    }


async def _sync_growth_operator_alerts(
    db: AsyncSession,
    brand_id: uuid.UUID,
    commands: list[dict],
    scale_recommendation_id: Optional[uuid.UUID],
) -> None:
    await db.execute(
        update(OperatorAlert)
        .where(
            OperatorAlert.brand_id == brand_id,
            OperatorAlert.alert_type == "growth_commander_priority",
            OperatorAlert.is_active.is_(True),
        )
        .values(is_active=False)
    )
    sorted_cmds = sorted(commands, key=lambda c: (-float(c.get("priority", 0)), -float(c.get("urgency", 0))))
    for cmd in sorted_cmds[:5]:
        if float(cmd.get("urgency", 0)) < 35:
            continue
        lc = uuid.UUID(cmd["linked_launch_candidate_id"]) if cmd.get("linked_launch_candidate_id") else None
        ls = uuid.UUID(cmd["linked_scale_recommendation_id"]) if cmd.get("linked_scale_recommendation_id") else scale_recommendation_id
        db.add(OperatorAlert(
            brand_id=brand_id,
            alert_type="growth_commander_priority",
            title=f"[Growth Commander] {cmd['title'][:480]}",
            summary=cmd["exact_instruction"][:4000],
            explanation=cmd.get("rationale"),
            recommended_action=cmd["command_type"],
            confidence=float(cmd.get("confidence", 0)),
            urgency=float(cmd.get("urgency", 0)),
            expected_upside=float(cmd.get("expected_upside", 0)),
            expected_cost=float(cmd.get("expected_cost", 0)),
            expected_time_to_signal_days=int(cmd.get("expected_time_to_signal_days", 14)),
            supporting_metrics={
                "command_type": cmd["command_type"],
                "priority": cmd.get("priority"),
                "evidence": cmd.get("evidence"),
                "execution_spec": cmd.get("execution_spec"),
                "required_resources": cmd.get("required_resources"),
            },
            blocking_factors=cmd.get("blocking_factors") if isinstance(cmd.get("blocking_factors"), list) else [],
            linked_scale_recommendation_id=ls,
            linked_launch_candidate_id=lc,
            status="unread",
            is_active=True,
        ))
    await db.flush()


async def get_growth_commands(db: AsyncSession, brand_id: uuid.UUID) -> list[dict]:
    rows = list((await db.execute(
        select(GrowthCommand).where(GrowthCommand.brand_id == brand_id, GrowthCommand.is_active.is_(True))
        .order_by(GrowthCommand.priority.desc())
    )).scalars().all())
    return [_ser(r) for r in rows]


async def list_growth_command_runs(
    db: AsyncSession, brand_id: uuid.UUID, limit: int = 30,
) -> list[dict[str, Any]]:
    rows = list((await db.execute(
        select(GrowthCommandRun)
        .where(GrowthCommandRun.brand_id == brand_id)
        .order_by(desc(GrowthCommandRun.created_at))
        .limit(min(limit, 100))
    )).scalars().all())
    return [_ser_run(r) for r in rows]


def _ser_run(r: GrowthCommandRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "created_at": str(r.created_at),
        "status": r.status,
        "commands_generated": r.commands_generated,
        "command_types": r.command_types or [],
        "portfolio_balance_snapshot": r.portfolio_balance_snapshot or {},
        "whitespace_count": r.whitespace_count,
        "error_message": r.error_message,
        "triggered_by_user_id": str(r.triggered_by_user_id) if r.triggered_by_user_id else None,
        "portfolio_directive": r.portfolio_directive or {},
    }


async def get_portfolio_assessment(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    accounts = list((await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all())
    acc_dicts = _acct_dicts(accounts)

    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    geo_recs = list((await db.execute(
        select(GeoLanguageExpansionRecommendation).where(GeoLanguageExpansionRecommendation.brand_id == brand_id).limit(10)
    )).scalars().all())
    geo_dicts = [{"target_geography": g.target_geography, "target_language": g.target_language, "estimated_revenue_potential": g.estimated_revenue_potential} for g in geo_recs]

    balance = assess_portfolio_balance(acc_dicts)
    whitespace = find_whitespace(acc_dicts, brand.niche if brand else None, geo_dicts)

    latest_run = (await db.execute(
        select(GrowthCommandRun)
        .where(GrowthCommandRun.brand_id == brand_id, GrowthCommandRun.status == "completed")
        .order_by(desc(GrowthCommandRun.created_at))
        .limit(1)
    )).scalars().first()

    return {
        "balance": balance,
        "whitespace": whitespace,
        "latest_portfolio_directive": latest_run.portfolio_directive if latest_run else None,
    }


def _ser(r: GrowthCommand) -> dict:
    return {
        "id": str(r.id), "command_type": r.command_type, "priority": r.priority,
        "title": r.title, "exact_instruction": r.exact_instruction,
        "rationale": r.rationale, "comparison": r.comparison,
        "platform_fit": r.platform_fit, "niche_fit": r.niche_fit,
        "monetization_path": r.monetization_path,
        "cannibalization_analysis": r.cannibalization_analysis,
        "success_threshold": r.success_threshold, "failure_threshold": r.failure_threshold,
        "expected_upside": r.expected_upside, "expected_cost": r.expected_cost,
        "expected_time_to_signal_days": r.expected_time_to_signal_days,
        "expected_time_to_profit_days": r.expected_time_to_profit_days,
        "confidence": r.confidence,
        "confidence_score": r.confidence,
        "urgency": r.urgency,
        "urgency_score": r.urgency,
        "blocking_factors": r.blocking_factors, "first_week_plan": r.first_week_plan,
        "linked_launch_candidate_id": str(r.linked_launch_candidate_id) if r.linked_launch_candidate_id else None,
        "linked_scale_recommendation_id": str(r.linked_scale_recommendation_id) if r.linked_scale_recommendation_id else None,
        "evidence": r.evidence,
        "execution_spec": r.execution_spec or {},
        "required_resources": r.required_resources or {},
        "required_resources_json": r.required_resources or {},
        "command_priority": r.command_priority,
        "action_deadline": str(r.action_deadline) if r.action_deadline else None,
        "platform": r.platform,
        "account_type": r.account_type,
        "niche": r.niche,
        "sub_niche": r.sub_niche,
        "persona_strategy_json": r.persona_strategy_json or {},
        "monetization_strategy_json": r.monetization_strategy_json or {},
        "output_requirements_json": r.output_requirements_json or {},
        "success_threshold_json": r.success_threshold_json or {},
        "failure_threshold_json": r.failure_threshold_json or {},
        "expected_revenue_min": r.expected_revenue_min,
        "expected_revenue_max": r.expected_revenue_max,
        "risk_score": r.risk_score,
        "blockers_json": r.blockers_json or [],
        "explanation_json": r.explanation_json or {},
        "consequence_if_ignored_json": r.consequence_if_ignored_json or {},
        "status": r.lifecycle_status,
        "created_at": str(r.created_at),
    }
