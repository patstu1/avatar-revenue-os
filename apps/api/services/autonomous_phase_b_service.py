"""Autonomous Execution Phase B — execution policies, content runner, distribution, monetization routing, suppression."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger()

from packages.db.models.accounts import CreatorAccount
from packages.db.models.autonomous_phase_a import (
    AccountMaturityReport,
    AccountOutputReport,
    AutoQueueItem,
    PlatformWarmupPolicy,
)
from packages.db.models.autonomous_phase_b import (
    AutonomousRun,
    AutonomousRunStep,
    DistributionPlan,
    ExecutionPolicy,
    MonetizationRoute,
    SuppressionExecution,
)
from packages.db.models.core import Brand
from packages.db.models.offers import Offer
from packages.scoring.execution_policy_engine import (
    ACTION_TYPES,
    RUN_STEPS,
    compute_policies_for_brand,
    evaluate_suppressions,
    plan_distribution,
    select_monetization_route,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------


def _policy_out(p: ExecutionPolicy) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "brand_id": str(p.brand_id),
        "action_type": p.action_type,
        "execution_mode": p.execution_mode,
        "confidence_threshold": p.confidence_threshold,
        "risk_level": p.risk_level,
        "cost_class": p.cost_class,
        "compliance_sensitivity": p.compliance_sensitivity,
        "platform_sensitivity": p.platform_sensitivity,
        "budget_impact": p.budget_impact,
        "account_health_impact": p.account_health_impact,
        "approval_requirement": p.approval_requirement,
        "rollback_rule": p.rollback_rule,
        "kill_switch_class": p.kill_switch_class,
        "policy_metadata_json": p.policy_metadata_json,
        "explanation": p.explanation,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _run_out(r: AutonomousRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "queue_item_id": str(r.queue_item_id) if r.queue_item_id else None,
        "target_account_id": str(r.target_account_id) if r.target_account_id else None,
        "target_platform": r.target_platform,
        "execution_mode": r.execution_mode,
        "run_status": r.run_status,
        "current_step": r.current_step,
        "content_brief_id": str(r.content_brief_id) if r.content_brief_id else None,
        "content_item_id": str(r.content_item_id) if r.content_item_id else None,
        "publish_job_id": str(r.publish_job_id) if r.publish_job_id else None,
        "distribution_plan_id": str(r.distribution_plan_id) if r.distribution_plan_id else None,
        "monetization_route_id": str(r.monetization_route_id) if r.monetization_route_id else None,
        "started_at": r.started_at,
        "completed_at": r.completed_at,
        "error_message": r.error_message,
        "run_metadata_json": r.run_metadata_json,
        "explanation": r.explanation,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _dist_plan_out(d: DistributionPlan) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "brand_id": str(d.brand_id),
        "source_concept": d.source_concept,
        "source_content_item_id": str(d.source_content_item_id) if d.source_content_item_id else None,
        "target_platforms_json": d.target_platforms_json,
        "derivative_types_json": d.derivative_types_json,
        "platform_priority_json": d.platform_priority_json,
        "cadence_json": d.cadence_json,
        "publish_timing_json": d.publish_timing_json,
        "duplication_guard_json": d.duplication_guard_json,
        "plan_status": d.plan_status,
        "confidence": d.confidence,
        "explanation": d.explanation,
        "is_active": d.is_active,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


def _mon_route_out(m: MonetizationRoute) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "brand_id": str(m.brand_id),
        "content_item_id": str(m.content_item_id) if m.content_item_id else None,
        "queue_item_id": str(m.queue_item_id) if m.queue_item_id else None,
        "route_class": m.route_class,
        "selected_route": m.selected_route,
        "funnel_path": m.funnel_path,
        "follow_up_requirements_json": m.follow_up_requirements_json,
        "revenue_estimate": m.revenue_estimate,
        "confidence": m.confidence,
        "route_status": m.route_status,
        "explanation": m.explanation,
        "is_active": m.is_active,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }


def _suppression_out(s: SuppressionExecution) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "brand_id": str(s.brand_id),
        "suppression_type": s.suppression_type,
        "affected_scope": s.affected_scope,
        "affected_entity_id": str(s.affected_entity_id) if s.affected_entity_id else None,
        "trigger_reason": s.trigger_reason,
        "duration_hours": s.duration_hours,
        "lift_condition": s.lift_condition,
        "confidence": s.confidence,
        "suppression_status": s.suppression_status,
        "lifted_at": s.lifted_at,
        "explanation": s.explanation,
        "is_active": s.is_active,
        "created_at": s.created_at,
        "updated_at": s.updated_at,
    }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _avg_health(db: AsyncSession, brand_id: uuid.UUID) -> float:
    rows = list(
        (
            await db.execute(
                select(AccountMaturityReport).where(
                    AccountMaturityReport.brand_id == brand_id,
                    AccountMaturityReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    if not rows:
        return 0.5
    return sum(r.health_score for r in rows) / len(rows)


async def _brand_context(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    guidelines = brand.brand_guidelines if brand else {} or {}
    return {
        "default_mode": guidelines.get("execution_mode", "guarded") if isinstance(guidelines, dict) else "guarded",
        "compliance_level": guidelines.get("compliance_level", "standard")
        if isinstance(guidelines, dict)
        else "standard",
        "budget_remaining": 1000.0,
        "platform_sensitivity": "standard",
        "has_active_violations": False,
    }


async def _active_accounts_dicts(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    accounts = list(
        (await db.execute(select(CreatorAccount).where(CreatorAccount.brand_id == brand_id))).scalars().all()
    )
    maturity_rows = list(
        (
            await db.execute(
                select(AccountMaturityReport).where(
                    AccountMaturityReport.brand_id == brand_id,
                    AccountMaturityReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    mat_map = {r.account_id: r for r in maturity_rows}

    output_rows = list(
        (
            await db.execute(
                select(AccountOutputReport).where(
                    AccountOutputReport.brand_id == brand_id,
                    AccountOutputReport.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    out_map = {r.account_id: r for r in output_rows}

    result = []
    for a in accounts:
        plat = a.platform.value if hasattr(a.platform, "value") else str(a.platform)
        mr = mat_map.get(a.id)
        opr = out_map.get(a.id)
        result.append(
            {
                "account_id": str(a.id),
                "platform": plat,
                "maturity_state": mr.maturity_state if mr else "warming",
                "health_score": mr.health_score if mr else 0.5,
                "saturation_score": a.saturation_score,
                "avg_engagement_rate": mr.avg_engagement_rate if mr else 0.0,
                "current_output_per_week": opr.current_output_per_week if opr else 0,
                "max_safe_output_per_week": opr.max_safe_output_per_week if opr else 21,
            }
        )
    return result


async def _platform_policies_dicts(db: AsyncSession) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(select(PlatformWarmupPolicy).where(PlatformWarmupPolicy.is_active.is_(True)))).scalars().all()
    )
    return [{"platform": p.platform, "max_safe_output_per_day": p.max_safe_posts_per_day} for p in rows]


async def _brand_offers_dicts(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = list((await db.execute(select(Offer).where(Offer.brand_id == brand_id).limit(100))).scalars().all())
    return [
        {
            "name": o.name,
            "type": o.monetization_method.value
            if hasattr(o.monetization_method, "value")
            else str(o.monetization_method),
            "keywords": [str(t) for t in (o.audience_fit_tags or [])],
            "revenue_per_conversion": float(o.payout_amount) if o.payout_amount else 50.0,
            "active": o.is_active,
        }
        for o in rows
    ]


# ---------------------------------------------------------------------------
# 1. Execution Policies
# ---------------------------------------------------------------------------


async def recompute_execution_policies(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _brand_context(db, brand_id)
    avg_h = await _avg_health(db, brand_id)
    confidence_map = {at: 0.6 for at in ACTION_TYPES}

    policies = compute_policies_for_brand(ACTION_TYPES, confidence_map, avg_h, ctx)

    await db.execute(
        update(ExecutionPolicy)
        .where(ExecutionPolicy.brand_id == brand_id, ExecutionPolicy.is_active.is_(True))
        .values(is_active=False)
    )

    created = 0
    for p in policies:
        db.add(
            ExecutionPolicy(
                brand_id=brand_id,
                action_type=p["action_type"],
                execution_mode=p["execution_mode"],
                confidence_threshold=p["confidence_threshold"],
                risk_level=p["risk_level"],
                cost_class=p["cost_class"],
                compliance_sensitivity=p["compliance_sensitivity"],
                platform_sensitivity=p["platform_sensitivity"],
                budget_impact=p["budget_impact"],
                account_health_impact=p["account_health_impact"],
                approval_requirement=p["approval_requirement"],
                rollback_rule=p["rollback_rule"],
                kill_switch_class=p["kill_switch_class"],
                explanation=p["explanation"],
            )
        )
        created += 1
    await db.flush()
    return {"brand_id": str(brand_id), "policies_created": created}


async def list_execution_policies(
    db: AsyncSession,
    brand_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(ExecutionPolicy)
                .where(
                    ExecutionPolicy.brand_id == brand_id,
                    ExecutionPolicy.is_active.is_(True),
                )
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_policy_out(p) for p in rows]


# ---------------------------------------------------------------------------
# 2. Autonomous Runs (Content Runner)
# ---------------------------------------------------------------------------


async def start_autonomous_run(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Consume top ready queue items and start autonomous runs for each."""
    queue_items = list(
        (
            await db.execute(
                select(AutoQueueItem)
                .where(
                    AutoQueueItem.brand_id == brand_id,
                    AutoQueueItem.is_active.is_(True),
                    AutoQueueItem.queue_status == "ready",
                )
                .order_by(AutoQueueItem.priority_score.desc())
                .limit(10)
            )
        )
        .scalars()
        .all()
    )

    policies = list(
        (
            await db.execute(
                select(ExecutionPolicy).where(
                    ExecutionPolicy.brand_id == brand_id,
                    ExecutionPolicy.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    publish_policy = None
    for p in policies:
        if p.action_type == "publish_content":
            publish_policy = p
            break

    exec_mode = publish_policy.execution_mode if publish_policy else "guarded"

    runs_created = 0
    for qi in queue_items:
        run = AutonomousRun(
            brand_id=brand_id,
            queue_item_id=qi.id,
            target_account_id=qi.target_account_id,
            target_platform=qi.platform,
            execution_mode=exec_mode,
            run_status="running",
            current_step="policy_check",
            started_at=_utc_now(),
            explanation=f"Auto-run from queue item '{qi.queue_item_type}' on {qi.platform}.",
        )
        db.add(run)
        await db.flush()

        for i, step_name in enumerate(RUN_STEPS):
            step = AutonomousRunStep(
                run_id=run.id,
                step_name=step_name,
                step_order=i,
                step_status="completed" if step_name in ("queued", "policy_check") else "pending",
                started_at=_utc_now() if step_name in ("queued", "policy_check") else None,
                completed_at=_utc_now() if step_name in ("queued", "policy_check") else None,
            )
            db.add(step)

        qi.queue_status = "processing"
        runs_created += 1

    await db.flush()
    return {"brand_id": str(brand_id), "runs_started": runs_created, "execution_mode": exec_mode}


async def list_autonomous_runs(
    db: AsyncSession,
    brand_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(AutonomousRun)
                .where(
                    AutonomousRun.brand_id == brand_id,
                    AutonomousRun.is_active.is_(True),
                )
                .order_by(AutonomousRun.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_run_out(r) for r in rows]


# ---------------------------------------------------------------------------
# 3. Distribution Plans
# ---------------------------------------------------------------------------


async def recompute_distribution_plans(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    runs = list(
        (
            await db.execute(
                select(AutonomousRun)
                .where(
                    AutonomousRun.brand_id == brand_id,
                    AutonomousRun.is_active.is_(True),
                    AutonomousRun.run_status == "running",
                    AutonomousRun.distribution_plan_id.is_(None),
                )
                .limit(20)
            )
        )
        .scalars()
        .all()
    )

    acct_dicts = await _active_accounts_dicts(db, brand_id)
    pol_dicts = await _platform_policies_dicts(db)

    await db.execute(
        update(DistributionPlan)
        .where(DistributionPlan.brand_id == brand_id, DistributionPlan.is_active.is_(True))
        .values(is_active=False)
    )

    plans_created = 0
    for run in runs:
        concept = run.explanation or f"Run {run.id}"
        result = plan_distribution(
            source_concept=concept,
            source_platform=run.target_platform,
            content_family="general",
            available_accounts=acct_dicts,
            platform_policies=pol_dicts,
        )

        plan = DistributionPlan(
            brand_id=brand_id,
            source_concept=result["source_concept"][:500],
            target_platforms_json=result["target_platforms"],
            derivative_types_json=result["derivative_types"],
            platform_priority_json=result["platform_priority"],
            cadence_json=result["cadence"],
            publish_timing_json=result["publish_timing"],
            duplication_guard_json=result["duplication_guard"],
            plan_status="active",
            confidence=result["confidence"],
            explanation=result["explanation"],
        )
        db.add(plan)
        await db.flush()

        run.distribution_plan_id = plan.id
        run.current_step = "distribution_planning"
        plans_created += 1

    await db.flush()
    return {"brand_id": str(brand_id), "plans_created": plans_created}


async def list_distribution_plans(
    db: AsyncSession,
    brand_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(DistributionPlan)
                .where(
                    DistributionPlan.brand_id == brand_id,
                    DistributionPlan.is_active.is_(True),
                )
                .order_by(DistributionPlan.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_dist_plan_out(d) for d in rows]


# ---------------------------------------------------------------------------
# 4. Monetization Routes
# ---------------------------------------------------------------------------


async def recompute_monetization_routes(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    runs = list(
        (
            await db.execute(
                select(AutonomousRun)
                .where(
                    AutonomousRun.brand_id == brand_id,
                    AutonomousRun.is_active.is_(True),
                    AutonomousRun.run_status == "running",
                    AutonomousRun.monetization_route_id.is_(None),
                )
                .limit(20)
            )
        )
        .scalars()
        .all()
    )

    offers = await _brand_offers_dicts(db, brand_id)
    acct_dicts = await _active_accounts_dicts(db, brand_id)
    acct_map = {a["account_id"]: a for a in acct_dicts}

    await db.execute(
        update(MonetizationRoute)
        .where(MonetizationRoute.brand_id == brand_id, MonetizationRoute.is_active.is_(True))
        .values(is_active=False)
    )

    routes_created = 0
    for run in runs:
        acct_ctx = acct_map.get(
            str(run.target_account_id),
            {
                "platform": run.target_platform,
                "maturity_state": "stable",
                "health_score": 0.5,
            },
        )

        qi = None
        if run.queue_item_id:
            qi = (
                await db.execute(select(AutoQueueItem).where(AutoQueueItem.id == run.queue_item_id))
            ).scalar_one_or_none()

        content_ctx = {
            "content_family": qi.content_family if qi else "general",
            "niche": qi.niche if qi else "",
            "signal_type": qi.queue_item_type if qi else "new_content",
            "monetization_path_hint": qi.monetization_path if qi else "",
            "urgency": qi.urgency_score if qi else 0.5,
        }

        audience_signals = {
            "conversion_intent": 0.3,
            "engagement_rate": float(acct_ctx.get("avg_engagement_rate", 0.02)),
            "email_list_size": 0,
            "community_size": 0,
            "follower_count": 0,
        }

        result = select_monetization_route(content_ctx, offers, audience_signals, acct_ctx)

        route = MonetizationRoute(
            brand_id=brand_id,
            queue_item_id=run.queue_item_id,
            route_class=result["route_class"],
            selected_route=result["selected_route"],
            funnel_path=result["funnel_path"],
            follow_up_requirements_json=result["follow_up_requirements"],
            revenue_estimate=result["revenue_estimate"],
            confidence=result["confidence"],
            route_status="active",
            explanation=result["explanation"],
        )
        db.add(route)
        await db.flush()

        run.monetization_route_id = route.id
        run.current_step = "monetization_routing"
        routes_created += 1

    await db.flush()
    return {"brand_id": str(brand_id), "routes_created": routes_created}


async def list_monetization_routes(
    db: AsyncSession,
    brand_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(MonetizationRoute)
                .where(
                    MonetizationRoute.brand_id == brand_id,
                    MonetizationRoute.is_active.is_(True),
                )
                .order_by(MonetizationRoute.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_mon_route_out(m) for m in rows]


# ---------------------------------------------------------------------------
# 5. Suppression Executions
# ---------------------------------------------------------------------------


async def run_suppression_check(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    acct_dicts = await _active_accounts_dicts(db, brand_id)

    queue_rows = list(
        (
            await db.execute(
                select(AutoQueueItem)
                .where(
                    AutoQueueItem.brand_id == brand_id,
                    AutoQueueItem.is_active.is_(True),
                )
                .limit(200)
            )
        )
        .scalars()
        .all()
    )
    qi_dicts = [
        {
            "id": str(q.id),
            "content_family": q.content_family or "general",
            "platform": q.platform,
            "priority_score": q.priority_score,
            "monetization_path": q.monetization_path,
            "queue_status": q.queue_status,
        }
        for q in queue_rows
    ]

    performance = {
        "overall_engagement_rate": 0.02,
        "revenue_trend": "flat",
        "content_fatigue_score": 0.3,
        "audience_growth_rate": 0.01,
    }

    suppressions = evaluate_suppressions(acct_dicts, qi_dicts, performance)

    created = 0
    for s in suppressions:
        entity_id = None
        if s.get("affected_entity_id"):
            try:
                entity_id = uuid.UUID(str(s["affected_entity_id"]))
            except (ValueError, TypeError):
                logger.debug("suppression_entity_id_parse_failed", exc_info=True)

        db.add(
            SuppressionExecution(
                brand_id=brand_id,
                suppression_type=s["suppression_type"],
                affected_scope=s["affected_scope"],
                affected_entity_id=entity_id,
                trigger_reason=s["trigger_reason"],
                duration_hours=s.get("duration_hours"),
                lift_condition=s.get("lift_condition"),
                confidence=s["confidence"],
                suppression_status="active",
                explanation=s["explanation"],
            )
        )
        created += 1

    await db.flush()
    return {"brand_id": str(brand_id), "suppressions_created": created}


async def list_suppression_executions(
    db: AsyncSession,
    brand_id: uuid.UUID,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = list(
        (
            await db.execute(
                select(SuppressionExecution)
                .where(
                    SuppressionExecution.brand_id == brand_id,
                    SuppressionExecution.is_active.is_(True),
                )
                .order_by(SuppressionExecution.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_suppression_out(s) for s in rows]
