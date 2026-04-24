"""Autonomous Phase B recurring workers — content runner, distribution, monetization, suppression."""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

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
from packages.db.session import get_sync_engine
from packages.scoring.execution_policy_engine import (
    RUN_STEPS,
    evaluate_suppressions,
    plan_distribution,
    select_monetization_route,
)
from workers.base_task import TrackedTask
from workers.celery_app import app

logger = structlog.get_logger()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _acct_dicts(session: Session, brand_id: _uuid.UUID) -> list[dict]:
    accounts = session.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id)
    ).scalars().all()
    mat_rows = session.execute(
        select(AccountMaturityReport).where(
            AccountMaturityReport.brand_id == brand_id,
            AccountMaturityReport.is_active.is_(True),
        )
    ).scalars().all()
    mat_map = {r.account_id: r for r in mat_rows}

    out_rows = session.execute(
        select(AccountOutputReport).where(
            AccountOutputReport.brand_id == brand_id,
            AccountOutputReport.is_active.is_(True),
        )
    ).scalars().all()
    out_map = {r.account_id: r for r in out_rows}

    result = []
    for a in accounts:
        plat = a.platform.value if hasattr(a.platform, "value") else str(a.platform)
        mr = mat_map.get(a.id)
        opr = out_map.get(a.id)
        result.append({
            "account_id": str(a.id),
            "platform": plat,
            "maturity_state": mr.maturity_state if mr else "warming",
            "health_score": mr.health_score if mr else 0.5,
            "saturation_score": a.saturation_score,
            "avg_engagement_rate": mr.avg_engagement_rate if mr else 0.0,
            "current_output_per_week": opr.current_output_per_week if opr else 0,
            "max_safe_output_per_week": opr.max_safe_output_per_week if opr else 21,
        })
    return result


def _policy_dicts(session: Session) -> list[dict]:
    rows = session.execute(
        select(PlatformWarmupPolicy).where(PlatformWarmupPolicy.is_active.is_(True))
    ).scalars().all()
    return [{"platform": p.platform, "max_safe_output_per_day": p.max_safe_posts_per_day} for p in rows]


# ---------------------------------------------------------------------------
# Task 1 — Autonomous Content Runner
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_b_worker.tasks.run_content_runner")
def run_content_runner(self) -> dict:
    """Advance autonomous runs through their step pipeline."""
    engine = get_sync_engine()
    runs_advanced = 0
    errors: list[dict] = []

    with Session(engine) as session:
        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        for brand in brands:
            try:
                queue_items = session.execute(
                    select(AutoQueueItem).where(
                        AutoQueueItem.brand_id == brand.id,
                        AutoQueueItem.is_active.is_(True),
                        AutoQueueItem.queue_status == "ready",
                    ).order_by(AutoQueueItem.priority_score.desc()).limit(5)
                ).scalars().all()

                policies = session.execute(
                    select(ExecutionPolicy).where(
                        ExecutionPolicy.brand_id == brand.id,
                        ExecutionPolicy.is_active.is_(True),
                        ExecutionPolicy.action_type == "publish_content",
                    )
                ).scalars().first()

                exec_mode = policies.execution_mode if policies else "guarded"

                for qi in queue_items:
                    run = AutonomousRun(
                        brand_id=brand.id,
                        queue_item_id=qi.id,
                        target_account_id=qi.target_account_id,
                        target_platform=qi.platform,
                        execution_mode=exec_mode,
                        run_status="running",
                        current_step="policy_check",
                        started_at=_now(),
                        explanation=f"Worker auto-run: {qi.queue_item_type} on {qi.platform}.",
                    )
                    session.add(run)
                    session.flush()

                    for i, step_name in enumerate(RUN_STEPS):
                        session.add(AutonomousRunStep(
                            run_id=run.id,
                            step_name=step_name,
                            step_order=i,
                            step_status="completed" if step_name in ("queued", "policy_check") else "pending",
                            started_at=_now() if step_name in ("queued", "policy_check") else None,
                            completed_at=_now() if step_name in ("queued", "policy_check") else None,
                        ))

                    qi.queue_status = "processing"
                    runs_advanced += 1

                logger.info("content_runner.brand_done", brand_id=str(brand.id), runs=runs_advanced)
            except Exception as exc:
                logger.exception("content_runner.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {"status": "completed", "runs_advanced": runs_advanced, "errors": errors}


# ---------------------------------------------------------------------------
# Task 2 — Distribution Plan Recomputation
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_b_worker.tasks.recompute_distribution_plans")
def recompute_distribution_plans(self) -> dict:
    """Create distribution plans for running autonomous runs."""
    engine = get_sync_engine()
    plans_created = 0
    errors: list[dict] = []

    with Session(engine) as session:
        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        for brand in brands:
            try:
                runs = session.execute(
                    select(AutonomousRun).where(
                        AutonomousRun.brand_id == brand.id,
                        AutonomousRun.is_active.is_(True),
                        AutonomousRun.run_status == "running",
                        AutonomousRun.distribution_plan_id.is_(None),
                    ).limit(20)
                ).scalars().all()

                if not runs:
                    continue

                accts = _acct_dicts(session, brand.id)
                pols = _policy_dicts(session)

                for run in runs:
                    concept = run.explanation or f"Run {run.id}"
                    result = plan_distribution(
                        source_concept=concept,
                        source_platform=run.target_platform,
                        content_family="general",
                        available_accounts=accts,
                        platform_policies=pols,
                    )

                    plan = DistributionPlan(
                        brand_id=brand.id,
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
                    session.add(plan)
                    session.flush()
                    run.distribution_plan_id = plan.id
                    plans_created += 1

                logger.info("distribution.brand_done", brand_id=str(brand.id), plans=plans_created)
            except Exception as exc:
                logger.exception("distribution.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {"status": "completed", "plans_created": plans_created, "errors": errors}


# ---------------------------------------------------------------------------
# Task 3 — Monetization Route Recomputation
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_b_worker.tasks.recompute_monetization_routes")
def recompute_monetization_routes(self) -> dict:
    """Select monetization routes for running autonomous runs."""
    engine = get_sync_engine()
    routes_created = 0
    errors: list[dict] = []

    with Session(engine) as session:
        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        for brand in brands:
            try:
                runs = session.execute(
                    select(AutonomousRun).where(
                        AutonomousRun.brand_id == brand.id,
                        AutonomousRun.is_active.is_(True),
                        AutonomousRun.run_status == "running",
                        AutonomousRun.monetization_route_id.is_(None),
                    ).limit(20)
                ).scalars().all()

                if not runs:
                    continue

                offers = session.execute(
                    select(Offer).where(Offer.brand_id == brand.id).limit(100)
                ).scalars().all()
                offer_dicts = [{
                    "name": o.name,
                    "type": o.monetization_method.value if hasattr(o.monetization_method, "value") else str(o.monetization_method),
                    "keywords": [str(t) for t in (o.audience_fit_tags or [])],
                    "revenue_per_conversion": float(o.payout_amount) if o.payout_amount else 50.0,
                    "active": o.is_active,
                } for o in offers]

                acct_dicts = _acct_dicts(session, brand.id)
                acct_map = {a["account_id"]: a for a in acct_dicts}

                for run in runs:
                    acct_ctx = acct_map.get(str(run.target_account_id), {
                        "platform": run.target_platform,
                        "maturity_state": "stable",
                        "health_score": 0.5,
                    })

                    qi = session.get(AutoQueueItem, run.queue_item_id) if run.queue_item_id else None

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

                    result = select_monetization_route(content_ctx, offer_dicts, audience_signals, acct_ctx)

                    route = MonetizationRoute(
                        brand_id=brand.id,
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
                    session.add(route)
                    session.flush()
                    run.monetization_route_id = route.id
                    routes_created += 1

                logger.info("monetization.brand_done", brand_id=str(brand.id), routes=routes_created)
            except Exception as exc:
                logger.exception("monetization.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {"status": "completed", "routes_created": routes_created, "errors": errors}


# ---------------------------------------------------------------------------
# Task 4 — Suppression Execution Checks
# ---------------------------------------------------------------------------

@app.task(base=TrackedTask, bind=True, name="workers.autonomous_phase_b_worker.tasks.run_suppression_checks")
def run_suppression_checks(self) -> dict:
    """Evaluate and persist suppression actions across all brands."""
    engine = get_sync_engine()
    suppressions_created = 0
    errors: list[dict] = []

    with Session(engine) as session:
        brands = session.execute(
            select(Brand).where(Brand.is_active.is_(True))
        ).scalars().all()

        for brand in brands:
            try:
                acct_dicts = _acct_dicts(session, brand.id)

                qi_rows = session.execute(
                    select(AutoQueueItem).where(
                        AutoQueueItem.brand_id == brand.id,
                        AutoQueueItem.is_active.is_(True),
                    ).limit(200)
                ).scalars().all()

                qi_dicts = [{
                    "id": str(q.id),
                    "content_family": q.content_family or "general",
                    "platform": q.platform,
                    "priority_score": q.priority_score,
                    "monetization_path": q.monetization_path,
                    "queue_status": q.queue_status,
                } for q in qi_rows]

                performance = {
                    "overall_engagement_rate": 0.02,
                    "revenue_trend": "flat",
                    "content_fatigue_score": 0.3,
                    "audience_growth_rate": 0.01,
                }

                results = evaluate_suppressions(acct_dicts, qi_dicts, performance)

                for s in results:
                    entity_id = None
                    if s.get("affected_entity_id"):
                        try:
                            entity_id = _uuid.UUID(str(s["affected_entity_id"]))
                        except (ValueError, TypeError):
                            pass

                    session.add(SuppressionExecution(
                        brand_id=brand.id,
                        suppression_type=s["suppression_type"],
                        affected_scope=s["affected_scope"],
                        affected_entity_id=entity_id,
                        trigger_reason=s["trigger_reason"],
                        duration_hours=s.get("duration_hours"),
                        lift_condition=s.get("lift_condition"),
                        confidence=s["confidence"],
                        suppression_status="active",
                        explanation=s["explanation"],
                    ))
                    suppressions_created += 1

                logger.info("suppression.brand_done", brand_id=str(brand.id), created=len(results))
            except Exception as exc:
                logger.exception("suppression.brand_error", brand_id=str(brand.id))
                errors.append({"brand_id": str(brand.id), "error": str(exc)})

        session.commit()

    return {"status": "completed", "suppressions_created": suppressions_created, "errors": errors}
