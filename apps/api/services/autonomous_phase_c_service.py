"""Autonomous Execution Phase C — funnel, paid operator, sponsor, retention, recovery."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.autonomous_phase_b import AutonomousRun, MonetizationRoute, SuppressionExecution
from packages.db.models.autonomous_phase_c import (
    FunnelExecutionRun,
    PaidOperatorDecision,
    PaidOperatorRun,
    RecoveryEscalation,
    RetentionAutomationAction,
    SelfHealingAction,
    SponsorAutonomousAction,
)
from packages.db.models.core import Brand
from packages.db.models.publishing import PerformanceMetric
from packages.scoring.autonomous_phase_c_engine import (
    compute_funnel_executions,
    compute_paid_operator_decision,
    compute_paid_operator_runs,
    compute_retention_actions,
    compute_self_healing_action,
    compute_sponsor_autonomous_actions,
    detect_recovery_incidents,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _brand_mode(guidelines: dict | None) -> str:
    if not isinstance(guidelines, dict):
        return "guarded"
    return str(guidelines.get("execution_mode", "guarded"))


def _funnel_out(r: FunnelExecutionRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "funnel_action": r.funnel_action,
        "target_funnel_path": r.target_funnel_path,
        "cta_path": r.cta_path,
        "capture_mode": r.capture_mode,
        "execution_mode": r.execution_mode,
        "expected_upside": r.expected_upside,
        "confidence": r.confidence,
        "explanation": r.explanation,
        "run_status": r.run_status,
        "diagnostics_json": r.diagnostics_json,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _paid_run_out(r: PaidOperatorRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "paid_action": r.paid_action,
        "budget_band": r.budget_band,
        "expected_cac": r.expected_cac,
        "expected_roi": r.expected_roi,
        "execution_mode": r.execution_mode,
        "confidence": r.confidence,
        "explanation": r.explanation,
        "winner_score": r.winner_score,
        "content_item_id": str(r.content_item_id) if r.content_item_id else None,
        "autonomous_run_id": str(r.autonomous_run_id) if r.autonomous_run_id else None,
        "run_status": r.run_status,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _paid_dec_out(d: PaidOperatorDecision) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "brand_id": str(d.brand_id),
        "paid_operator_run_id": str(d.paid_operator_run_id),
        "decision_type": d.decision_type,
        "budget_band": d.budget_band,
        "expected_cac": d.expected_cac,
        "expected_roi": d.expected_roi,
        "execution_mode": d.execution_mode,
        "confidence": d.confidence,
        "explanation": d.explanation,
        "execution_status": d.execution_status,
        "is_active": d.is_active,
        "created_at": d.created_at,
        "updated_at": d.updated_at,
    }


def _sponsor_out(a: SponsorAutonomousAction) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "brand_id": str(a.brand_id),
        "sponsor_action": a.sponsor_action,
        "package_json": a.package_json,
        "target_category": a.target_category,
        "target_list_json": a.target_list_json,
        "pipeline_stage": a.pipeline_stage,
        "expected_deal_value": a.expected_deal_value,
        "confidence": a.confidence,
        "explanation": a.explanation,
        "execution_status": a.execution_status,
        "is_active": a.is_active,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


def _retention_out(a: RetentionAutomationAction) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "brand_id": str(a.brand_id),
        "retention_action": a.retention_action,
        "target_segment": a.target_segment,
        "cohort_key": a.cohort_key,
        "expected_incremental_value": a.expected_incremental_value,
        "confidence": a.confidence,
        "explanation": a.explanation,
        "execution_status": a.execution_status,
        "is_active": a.is_active,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
    }


def _recovery_out(e: RecoveryEscalation) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "brand_id": str(e.brand_id),
        "incident_type": e.incident_type,
        "escalation_requirement": e.escalation_requirement,
        "severity": e.severity,
        "explanation": e.explanation,
        "related_autonomous_run_id": str(e.related_autonomous_run_id) if e.related_autonomous_run_id else None,
        "status": e.status,
        "resolved_at": e.resolved_at,
        "is_active": e.is_active,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _heal_out(h: SelfHealingAction) -> dict[str, Any]:
    return {
        "id": str(h.id),
        "brand_id": str(h.brand_id),
        "recovery_escalation_id": str(h.recovery_escalation_id) if h.recovery_escalation_id else None,
        "incident_type": h.incident_type,
        "action_taken": h.action_taken,
        "action_mode": h.action_mode,
        "escalation_requirement": h.escalation_requirement,
        "expected_mitigation": h.expected_mitigation,
        "confidence": h.confidence,
        "explanation": h.explanation,
        "execution_status": h.execution_status,
        "is_active": h.is_active,
        "created_at": h.created_at,
        "updated_at": h.updated_at,
    }


# --- Funnel ---

async def recompute_funnel_execution(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    guidelines = brand.brand_guidelines if brand else {}

    agg = (
        await db.execute(
            select(
                func.avg(PerformanceMetric.engagement_rate),
                func.avg(PerformanceMetric.ctr),
            ).where(PerformanceMetric.brand_id == brand_id)
        )
    ).one()
    avg_eng = float(agg[0] or 0.02)
    avg_ctr = float(agg[1] or 0.01)
    leak_proxy = max(0.0, min(1.0, 0.5 - avg_eng * 5))
    intent_proxy = min(1.0, avg_ctr * 40)

    ctx = {
        "funnel_leak_score": leak_proxy,
        "high_intent_share": intent_proxy,
        "owned_list_growth": 0.015,
        "email_sequence_health": 0.55 if leak_proxy > 0.35 else 0.65,
        "sms_enabled": False,
        "default_execution_mode": _brand_mode(guidelines),
    }
    rows = compute_funnel_executions(ctx)

    await db.execute(
        update(FunnelExecutionRun)
        .where(FunnelExecutionRun.brand_id == brand_id, FunnelExecutionRun.is_active.is_(True))
        .values(is_active=False)
    )

    n = 0
    for row in rows:
        db.add(FunnelExecutionRun(
            brand_id=brand_id,
            funnel_action=row["funnel_action"],
            target_funnel_path=row["target_funnel_path"],
            cta_path=row.get("cta_path"),
            capture_mode=row["capture_mode"],
            execution_mode=row["execution_mode"],
            expected_upside=row["expected_upside"],
            confidence=row["confidence"],
            explanation=row["explanation"],
            run_status="active",
            diagnostics_json=row.get("diagnostics_json"),
        ))
        n += 1
    await db.flush()
    return {"brand_id": str(brand_id), "funnel_runs_created": n}


async def list_funnel_execution(db: AsyncSession, brand_id: uuid.UUID, limit: int = 100) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(FunnelExecutionRun).where(
                FunnelExecutionRun.brand_id == brand_id,
                FunnelExecutionRun.is_active.is_(True),
            ).order_by(FunnelExecutionRun.created_at.desc()).limit(limit)
        )).scalars().all()
    )
    return [_funnel_out(r) for r in rows]


# --- Paid operator ---

async def _collect_winners(db: AsyncSession, brand_id: uuid.UUID) -> list[dict[str, Any]]:
    winners: list[dict[str, Any]] = []

    routes = list(
        (await db.execute(
            select(MonetizationRoute).where(
                MonetizationRoute.brand_id == brand_id,
                MonetizationRoute.is_active.is_(True),
                MonetizationRoute.confidence >= 0.65,
            ).limit(20)
        )).scalars().all()
    )
    for mr in routes:
        cid = mr.content_item_id
        eng = float(mr.confidence)
        rev = float(mr.revenue_estimate)
        winners.append({
            "content_item_id": str(cid) if cid else None,
            "autonomous_run_id": None,
            "engagement_score": eng,
            "revenue_proxy": max(rev, 60),
            "days_since_publish": 5,
        })

    metrics = list(
        (await db.execute(
            select(PerformanceMetric).where(PerformanceMetric.brand_id == brand_id).limit(50)
        )).scalars().all()
    )
    for m in metrics:
        eng = float(m.engagement_rate) if m.engagement_rate else float(m.ctr or 0) * 10
        eng = min(1.0, max(0.0, eng))
        winners.append({
            "content_item_id": str(m.content_item_id),
            "autonomous_run_id": None,
            "engagement_score": eng,
            "revenue_proxy": float(m.revenue or 0) + 50,
            "days_since_publish": 7,
        })

    runs = list(
        (await db.execute(
            select(AutonomousRun).where(
                AutonomousRun.brand_id == brand_id,
                AutonomousRun.is_active.is_(True),
                AutonomousRun.run_status == "running",
            ).limit(10)
        )).scalars().all()
    )
    for ar in runs:
        winners.append({
            "content_item_id": None,
            "autonomous_run_id": str(ar.id),
            "engagement_score": 0.7,
            "revenue_proxy": 120,
            "days_since_publish": 3,
        })

    return winners


async def recompute_paid_operator(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    brand = (await db.execute(select(Brand).where(Brand.id == brand_id))).scalar_one_or_none()
    guidelines = brand.brand_guidelines if brand else {}

    winners = await _collect_winners(db, brand_id)
    ctx = {"default_execution_mode": _brand_mode(guidelines), "paid_budget_ceiling_daily": 500.0}
    planned = compute_paid_operator_runs(winners, ctx)

    await db.execute(
        update(PaidOperatorRun)
        .where(PaidOperatorRun.brand_id == brand_id, PaidOperatorRun.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(PaidOperatorDecision)
        .where(PaidOperatorDecision.brand_id == brand_id, PaidOperatorDecision.is_active.is_(True))
        .values(is_active=False)
    )

    runs_created = 0
    decisions_created = 0
    for p in planned:
        cid = None
        if p.get("content_item_id"):
            try:
                cid = uuid.UUID(str(p["content_item_id"]))
            except (ValueError, TypeError):
                cid = None
        arid = None
        if p.get("autonomous_run_id"):
            try:
                arid = uuid.UUID(str(p["autonomous_run_id"]))
            except (ValueError, TypeError):
                arid = None

        run = PaidOperatorRun(
            brand_id=brand_id,
            paid_action=p["paid_action"],
            budget_band=p["budget_band"],
            expected_cac=p["expected_cac"],
            expected_roi=p["expected_roi"],
            execution_mode=p["execution_mode"],
            confidence=p["confidence"],
            explanation=p["explanation"],
            winner_score=p["winner_score"],
            content_item_id=cid,
            autonomous_run_id=arid,
            run_status="active",
        )
        db.add(run)
        await db.flush()
        runs_created += 1

        # NOTE: Real ad-platform metrics (CPA, spend, conversions) are not yet
        # connected.  Until an ads integration exists the decision engine
        # receives *synthetic* performance derived from the engine's own
        # estimates.  This means the decision will bias toward "hold" — which
        # is the safest default when real data is absent.
        perf = {
            "cpa_actual": p["expected_cac"] * 0.95,
            "cpa_target": 55,
            "spend_7d": 180,
            "conversions_7d": 4,
            "roi_actual": p["expected_roi"] * 0.9,
            "_data_source": "synthetic_estimate",
        }
        dec = compute_paid_operator_decision({"run_id": str(run.id)}, perf)
        dec["explanation"] = f"[data_source=synthetic_estimate] {dec['explanation']}"
        db.add(PaidOperatorDecision(
            brand_id=brand_id,
            paid_operator_run_id=run.id,
            decision_type=dec["decision_type"],
            budget_band=dec["budget_band"],
            expected_cac=dec["expected_cac"],
            expected_roi=dec["expected_roi"],
            execution_mode=dec["execution_mode"],
            confidence=dec["confidence"],
            explanation=dec["explanation"],
        ))
        decisions_created += 1

    if runs_created == 0:
        run = PaidOperatorRun(
            brand_id=brand_id,
            paid_action="hold_no_proven_winners",
            budget_band="none",
            expected_cac=0.0,
            expected_roi=0.0,
            execution_mode="guarded",
            confidence=0.5,
            explanation="No organic winners met paid operator thresholds (engagement/revenue/proxy).",
            winner_score=0.0,
            run_status="proposed",
        )
        db.add(run)
        await db.flush()
        runs_created = 1
        dec = compute_paid_operator_decision({}, {"cpa_actual": 999, "cpa_target": 50, "spend_7d": 0, "conversions_7d": 0, "roi_actual": 0})
        db.add(PaidOperatorDecision(
            brand_id=brand_id,
            paid_operator_run_id=run.id,
            decision_type=dec["decision_type"],
            budget_band=dec["budget_band"],
            expected_cac=dec["expected_cac"],
            expected_roi=dec["expected_roi"],
            execution_mode=dec["execution_mode"],
            confidence=dec["confidence"],
            explanation=dec["explanation"],
        ))
        decisions_created += 1

    await db.flush()
    return {"brand_id": str(brand_id), "paid_runs_created": runs_created, "decisions_created": decisions_created}


async def list_paid_operator(db: AsyncSession, brand_id: uuid.UUID, limit: int = 100) -> dict[str, Any]:
    runs = list(
        (await db.execute(
            select(PaidOperatorRun).where(
                PaidOperatorRun.brand_id == brand_id,
                PaidOperatorRun.is_active.is_(True),
            ).order_by(PaidOperatorRun.created_at.desc()).limit(limit)
        )).scalars().all()
    )
    decisions = list(
        (await db.execute(
            select(PaidOperatorDecision).where(
                PaidOperatorDecision.brand_id == brand_id,
                PaidOperatorDecision.is_active.is_(True),
            ).order_by(PaidOperatorDecision.created_at.desc()).limit(limit)
        )).scalars().all()
    )
    return {
        "runs": [_paid_run_out(r) for r in runs],
        "decisions": [_paid_dec_out(d) for d in decisions],
    }


# --- Sponsor ---

async def recompute_sponsor_autonomy(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    from packages.db.models.offers import SponsorOpportunity, SponsorProfile

    # Real inventory completeness — ratio of sponsor profiles with at least one opportunity
    total_profiles = (await db.execute(
        select(func.count()).select_from(SponsorProfile).where(SponsorProfile.brand_id == brand_id)
    )).scalar() or 0
    profiles_with_opps = (await db.execute(
        select(func.count(func.distinct(SponsorOpportunity.sponsor_id))).where(
            SponsorOpportunity.brand_id == brand_id,
        )
    )).scalar() or 0
    inv_completeness = min(1.0, profiles_with_opps / max(total_profiles, 1))

    # Real pipeline depth — count of active non-closed opportunities
    pipeline_count = (await db.execute(
        select(func.count()).select_from(SponsorOpportunity).where(
            SponsorOpportunity.brand_id == brand_id,
            SponsorOpportunity.status.notin_(["closed", "lost"]),
        )
    )).scalar() or 0

    # Renewals — opportunities with status 'renewal' or 'active' (proxy for renewal window)
    renewals_due = (await db.execute(
        select(func.count()).select_from(SponsorOpportunity).where(
            SponsorOpportunity.brand_id == brand_id,
            SponsorOpportunity.status == "active",
        )
    )).scalar() or 0

    ctx = {
        "sponsor_inventory_completeness": inv_completeness,
        "sponsor_pipeline_count": pipeline_count,
        "sponsor_renewals_due_30d": renewals_due,
    }
    actions = compute_sponsor_autonomous_actions(ctx)

    await db.execute(
        update(SponsorAutonomousAction)
        .where(SponsorAutonomousAction.brand_id == brand_id, SponsorAutonomousAction.is_active.is_(True))
        .values(is_active=False)
    )

    n = 0
    for a in actions:
        db.add(SponsorAutonomousAction(
            brand_id=brand_id,
            sponsor_action=a["sponsor_action"],
            package_json=a.get("package_json"),
            target_category=a["target_category"],
            target_list_json=a.get("target_list_json"),
            pipeline_stage=a["pipeline_stage"],
            expected_deal_value=a["expected_deal_value"],
            confidence=a["confidence"],
            explanation=a["explanation"],
        ))
        n += 1
    await db.flush()
    return {"brand_id": str(brand_id), "sponsor_actions_created": n}


async def list_sponsor_autonomy(db: AsyncSession, brand_id: uuid.UUID, limit: int = 100) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(SponsorAutonomousAction).where(
                SponsorAutonomousAction.brand_id == brand_id,
                SponsorAutonomousAction.is_active.is_(True),
            ).order_by(SponsorAutonomousAction.created_at.desc()).limit(limit)
        )).scalars().all()
    )
    return [_sponsor_out(a) for a in rows]


# --- Retention ---

async def recompute_retention_autonomy(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    agg = (
        await db.execute(
            select(func.avg(PerformanceMetric.engagement_rate)).where(PerformanceMetric.brand_id == brand_id)
        )
    ).scalar()
    eng = float(agg or 0.02)
    churn_proxy = max(0.0, min(1.0, 0.55 - eng * 8))

    signals = {
        "churn_risk_score": churn_proxy,
        "upsell_window_score": 0.45 if eng > 0.03 else 0.25,
        "repeat_purchase_window_score": 0.4,
        "ltv_tier": "high" if eng > 0.04 else "mid",
    }
    actions = compute_retention_actions(signals)

    await db.execute(
        update(RetentionAutomationAction)
        .where(RetentionAutomationAction.brand_id == brand_id, RetentionAutomationAction.is_active.is_(True))
        .values(is_active=False)
    )

    n = 0
    for a in actions:
        db.add(RetentionAutomationAction(
            brand_id=brand_id,
            retention_action=a["retention_action"],
            target_segment=a["target_segment"],
            cohort_key=a.get("cohort_key"),
            expected_incremental_value=a["expected_incremental_value"],
            confidence=a["confidence"],
            explanation=a["explanation"],
        ))
        n += 1
    await db.flush()
    return {"brand_id": str(brand_id), "retention_actions_created": n}


async def list_retention_autonomy(db: AsyncSession, brand_id: uuid.UUID, limit: int = 100) -> list[dict[str, Any]]:
    rows = list(
        (await db.execute(
            select(RetentionAutomationAction).where(
                RetentionAutomationAction.brand_id == brand_id,
                RetentionAutomationAction.is_active.is_(True),
            ).order_by(RetentionAutomationAction.created_at.desc()).limit(limit)
        )).scalars().all()
    )
    return [_retention_out(a) for a in rows]


# --- Recovery + self-healing ---

async def recompute_recovery_autonomy(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    supp = list(
        (await db.execute(
            select(SuppressionExecution).where(
                SuppressionExecution.brand_id == brand_id,
                SuppressionExecution.is_active.is_(True),
            ).limit(20)
        )).scalars().all()
    )
    congested = len(supp) >= 5

    agg = (
        await db.execute(
            select(func.avg(PerformanceMetric.engagement_rate)).where(PerformanceMetric.brand_id == brand_id)
        )
    ).scalar()
    eng = float(agg or 0.02)
    conv_drop = 0.25 if eng < 0.015 else 0.05

    ar = (
        await db.execute(
            select(AutonomousRun).where(
                AutonomousRun.brand_id == brand_id,
                AutonomousRun.error_message.isnot(None),
            ).limit(1)
        )
    ).scalar_one_or_none()

    signals = {
        "provider_failure": False,
        "publishing_failure_rate": 0.08,
        "conversion_drop_pct": conv_drop,
        "fatigue_spike": 0.15 if eng < 0.02 else 0.05,
        "queue_congestion_score": 0.75 if congested else 0.3,
        "budget_overspend_pct": 0.0,
        "sponsor_underperformance": False,
        "account_stagnation": eng < 0.012,
        "weak_offer_economics": False,
    }

    incidents = detect_recovery_incidents(signals)

    await db.execute(
        update(RecoveryEscalation)
        .where(RecoveryEscalation.brand_id == brand_id, RecoveryEscalation.is_active.is_(True))
        .values(is_active=False)
    )
    await db.execute(
        update(SelfHealingAction)
        .where(SelfHealingAction.brand_id == brand_id, SelfHealingAction.is_active.is_(True))
        .values(is_active=False)
    )

    esc_n = 0
    heal_n = 0
    related = ar.id if ar else None

    for inc in incidents:
        rec = RecoveryEscalation(
            brand_id=brand_id,
            incident_type=inc["incident_type"],
            escalation_requirement=inc["escalation_requirement"],
            severity=inc["severity"],
            explanation=inc["explanation"],
            related_autonomous_run_id=related,
            status="open",
        )
        db.add(rec)
        await db.flush()
        esc_n += 1
        heal = compute_self_healing_action(inc)
        db.add(SelfHealingAction(
            brand_id=brand_id,
            recovery_escalation_id=rec.id,
            incident_type=heal["incident_type"],
            action_taken=heal["action_taken"],
            action_mode=heal["action_mode"],
            escalation_requirement=heal["escalation_requirement"],
            expected_mitigation=heal["expected_mitigation"],
            confidence=heal["confidence"],
            explanation=heal["explanation"],
        ))
        heal_n += 1

    if esc_n == 0:
        rec = RecoveryEscalation(
            brand_id=brand_id,
            incident_type="healthy_baseline",
            escalation_requirement="none",
            severity="low",
            explanation="No recovery incidents detected this cycle.",
            status="resolved",
            resolved_at=_utc_now(),
        )
        db.add(rec)
        await db.flush()
        esc_n = 1
        db.add(SelfHealingAction(
            brand_id=brand_id,
            recovery_escalation_id=rec.id,
            incident_type="healthy_baseline",
            action_taken="monitor",
            action_mode="autonomous",
            escalation_requirement="none",
            expected_mitigation="Continue scheduled observation",
            confidence=0.6,
            explanation="System within guardrails.",
        ))
        heal_n = 1

    await db.flush()
    return {"brand_id": str(brand_id), "escalations_created": esc_n, "self_healing_created": heal_n}


async def list_recovery_autonomy(db: AsyncSession, brand_id: uuid.UUID, limit: int = 100) -> dict[str, Any]:
    esc = list(
        (await db.execute(
            select(RecoveryEscalation).where(
                RecoveryEscalation.brand_id == brand_id,
                RecoveryEscalation.is_active.is_(True),
            ).order_by(RecoveryEscalation.created_at.desc()).limit(limit)
        )).scalars().all()
    )
    heal = list(
        (await db.execute(
            select(SelfHealingAction).where(
                SelfHealingAction.brand_id == brand_id,
                SelfHealingAction.is_active.is_(True),
            ).order_by(SelfHealingAction.created_at.desc()).limit(limit)
        )).scalars().all()
    )
    return {
        "escalations": [_recovery_out(e) for e in esc],
        "self_healing": [_heal_out(h) for h in heal],
    }
