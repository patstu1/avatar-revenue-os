"""Brain Architecture Phase B — service layer for decisions, policies, confidence, cost/upside, arbitration."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.brain_architecture import (
    AccountStateSnapshot,
    BrainMemoryEntry,
    ExecutionStateSnapshot,
    OpportunityStateSnapshot,
)
from packages.db.models.brain_phase_b import (
    ArbitrationReport,
    BrainDecision,
    ConfidenceReport,
    PolicyEvaluation,
    UpsideCostEstimate,
)
from packages.db.models.offers import Offer
from packages.scoring.brain_phase_b_engine import (
    compute_arbitration,
    compute_brain_decision,
    compute_confidence_report,
    compute_policy_evaluation,
    compute_upside_cost_estimate,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ── serializer helpers ────────────────────────────────────────────────

def _decision_out(d: BrainDecision) -> dict[str, Any]:
    return {
        "id": d.id, "brand_id": d.brand_id,
        "decision_class": d.decision_class, "objective": d.objective,
        "target_scope": d.target_scope, "target_id": d.target_id,
        "selected_action": d.selected_action, "alternatives_json": d.alternatives_json,
        "confidence": d.confidence, "policy_mode": d.policy_mode,
        "expected_upside": d.expected_upside, "expected_cost": d.expected_cost,
        "downstream_action": d.downstream_action, "inputs_json": d.inputs_json,
        "explanation": d.explanation, "is_active": d.is_active,
        "created_at": d.created_at, "updated_at": d.updated_at,
    }


def _policy_out(p: PolicyEvaluation) -> dict[str, Any]:
    return {
        "id": p.id, "brand_id": p.brand_id, "decision_id": p.decision_id,
        "action_ref": p.action_ref, "policy_mode": p.policy_mode,
        "reason": p.reason, "approval_needed": p.approval_needed,
        "hard_stop_rule": p.hard_stop_rule, "rollback_rule": p.rollback_rule,
        "risk_score": p.risk_score, "cost_impact": p.cost_impact,
        "inputs_json": p.inputs_json, "explanation": p.explanation,
        "is_active": p.is_active, "created_at": p.created_at, "updated_at": p.updated_at,
    }


def _conf_out(c: ConfidenceReport) -> dict[str, Any]:
    return {
        "id": c.id, "brand_id": c.brand_id, "decision_id": c.decision_id,
        "scope_label": c.scope_label,
        "confidence_score": c.confidence_score, "confidence_band": c.confidence_band,
        "signal_strength": c.signal_strength,
        "historical_precedent": c.historical_precedent,
        "saturation_risk": c.saturation_risk, "memory_support": c.memory_support,
        "data_completeness": c.data_completeness,
        "execution_history": c.execution_history,
        "blocker_severity": c.blocker_severity,
        "uncertainty_factors_json": c.uncertainty_factors_json,
        "explanation": c.explanation, "is_active": c.is_active,
        "created_at": c.created_at, "updated_at": c.updated_at,
    }


def _uc_out(u: UpsideCostEstimate) -> dict[str, Any]:
    return {
        "id": u.id, "brand_id": u.brand_id, "decision_id": u.decision_id,
        "scope_label": u.scope_label,
        "expected_upside": u.expected_upside, "expected_cost": u.expected_cost,
        "expected_payback_days": u.expected_payback_days,
        "operational_burden": u.operational_burden,
        "concentration_risk": u.concentration_risk,
        "net_value": u.net_value, "inputs_json": u.inputs_json,
        "explanation": u.explanation, "is_active": u.is_active,
        "created_at": u.created_at, "updated_at": u.updated_at,
    }


def _arb_out(a: ArbitrationReport) -> dict[str, Any]:
    return {
        "id": a.id, "brand_id": a.brand_id,
        "ranked_priorities_json": a.ranked_priorities_json,
        "chosen_winner_class": a.chosen_winner_class,
        "chosen_winner_label": a.chosen_winner_label,
        "rejected_actions_json": a.rejected_actions_json,
        "competing_count": a.competing_count,
        "net_value_chosen": a.net_value_chosen,
        "inputs_json": a.inputs_json, "explanation": a.explanation,
        "is_active": a.is_active, "created_at": a.created_at, "updated_at": a.updated_at,
    }


# =====================================================================
# List helpers
# =====================================================================

async def list_brain_decisions(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict]:
    q = await db.execute(
        select(BrainDecision).where(BrainDecision.brand_id == brand_id, BrainDecision.is_active.is_(True))
        .order_by(BrainDecision.created_at.desc()).limit(limit)
    )
    return [_decision_out(r) for r in q.scalars().all()]


async def list_policy_evaluations(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict]:
    q = await db.execute(
        select(PolicyEvaluation).where(PolicyEvaluation.brand_id == brand_id, PolicyEvaluation.is_active.is_(True))
        .order_by(PolicyEvaluation.created_at.desc()).limit(limit)
    )
    return [_policy_out(r) for r in q.scalars().all()]


async def list_confidence_reports(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict]:
    q = await db.execute(
        select(ConfidenceReport).where(ConfidenceReport.brand_id == brand_id, ConfidenceReport.is_active.is_(True))
        .order_by(ConfidenceReport.created_at.desc()).limit(limit)
    )
    return [_conf_out(r) for r in q.scalars().all()]


async def list_upside_cost_estimates(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 100) -> list[dict]:
    q = await db.execute(
        select(UpsideCostEstimate).where(UpsideCostEstimate.brand_id == brand_id, UpsideCostEstimate.is_active.is_(True))
        .order_by(UpsideCostEstimate.created_at.desc()).limit(limit)
    )
    return [_uc_out(r) for r in q.scalars().all()]


async def list_arbitration_reports(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict]:
    q = await db.execute(
        select(ArbitrationReport).where(ArbitrationReport.brand_id == brand_id, ArbitrationReport.is_active.is_(True))
        .order_by(ArbitrationReport.created_at.desc()).limit(limit)
    )
    return [_arb_out(r) for r in q.scalars().all()]


# =====================================================================
# Recompute: full pipeline (decisions → policy → confidence → cost → arbitration)
# =====================================================================

async def recompute_brain_decisions(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    _health_map = {"healthy": 1.0, "warning": 0.6, "degraded": 0.35, "critical": 0.15, "suspended": 0.05}

    accts_q = await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )
    accts = accts_q.scalars().all()

    acct_states_q = await db.execute(
        select(AccountStateSnapshot)
        .where(AccountStateSnapshot.brand_id == brand_id, AccountStateSnapshot.is_active.is_(True))
    )
    acct_states = {str(s.account_id): s for s in acct_states_q.scalars().all()}

    opp_states_q = await db.execute(
        select(OpportunityStateSnapshot)
        .where(OpportunityStateSnapshot.brand_id == brand_id, OpportunityStateSnapshot.is_active.is_(True))
        .order_by(OpportunityStateSnapshot.created_at.desc()).limit(20)
    )
    opp_states = opp_states_q.scalars().all()

    exec_states_q = await db.execute(
        select(ExecutionStateSnapshot)
        .where(ExecutionStateSnapshot.brand_id == brand_id, ExecutionStateSnapshot.is_active.is_(True))
        .order_by(ExecutionStateSnapshot.created_at.desc()).limit(20)
    )
    exec_states = exec_states_q.scalars().all()

    memory_q = await db.execute(
        select(BrainMemoryEntry)
        .where(BrainMemoryEntry.brand_id == brand_id, BrainMemoryEntry.is_active.is_(True))
        .order_by(BrainMemoryEntry.created_at.desc()).limit(20)
    )
    memories = memory_q.scalars().all()
    memory_support = min(1.0, len(memories) / 10)

    offers_q = await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))
    offers = offers_q.scalars().all()

    await db.execute(update(BrainDecision).where(BrainDecision.brand_id == brand_id, BrainDecision.is_active.is_(True)).values(is_active=False))
    await db.execute(update(PolicyEvaluation).where(PolicyEvaluation.brand_id == brand_id, PolicyEvaluation.is_active.is_(True)).values(is_active=False))
    await db.execute(update(ConfidenceReport).where(ConfidenceReport.brand_id == brand_id, ConfidenceReport.is_active.is_(True)).values(is_active=False))
    await db.execute(update(UpsideCostEstimate).where(UpsideCostEstimate.brand_id == brand_id, UpsideCostEstimate.is_active.is_(True)).values(is_active=False))
    await db.execute(update(ArbitrationReport).where(ArbitrationReport.brand_id == brand_id, ArbitrationReport.is_active.is_(True)).values(is_active=False))

    decisions_created = 0
    policies_created = 0
    confidence_created = 0
    estimates_created = 0
    arb_candidates: list[dict[str, Any]] = []

    for a in accts:
        health_val = a.account_health.value if a.account_health else "healthy"
        health_num = _health_map.get(health_val, 0.5)
        a_state = acct_states.get(str(a.id))
        saturation = float(a.saturation_score or 0)
        fatigue = float(a.fatigue_score or 0)

        ctx = {
            "account_state": a_state.current_state if a_state else "warming",
            "opportunity_state": opp_states[0].current_state if opp_states else "monitor",
            "execution_state": exec_states[0].current_state if exec_states else "queued",
            "audience_state": "unaware",
            "profit_per_post": float(getattr(a, "profit_per_post", 0) or 0),
            "saturation_score": saturation,
            "fatigue_score": fatigue,
            "has_blocker": False,
            "confidence": 0.5,
            "churn_risk": 0.0,
        }
        dec_result = compute_brain_decision(ctx)

        conf_ctx = {
            "signal_strength": min(1.0, float(getattr(a, "avg_engagement", 0) or 0) * 20),
            "historical_precedent": min(1.0, 0.3 + memory_support * 0.4),
            "saturation_risk": saturation,
            "memory_support": memory_support,
            "data_completeness": 0.6 if offers else 0.3,
            "execution_history": min(1.0, 0.3 + len(exec_states) * 0.05),
            "blocker_severity": 0.0,
        }
        conf_result = compute_confidence_report(conf_ctx)
        dec_result["confidence"] = conf_result["confidence_score"]

        plat = a.platform.value if a.platform else "unknown"
        plat_sensitivity = 0.5 if plat in ("tiktok", "instagram") else 0.3
        policy_ctx = {
            "confidence": conf_result["confidence_score"],
            "risk_score": saturation * 0.5 + fatigue * 0.3,
            "cost": 15.0,
            "platform_sensitivity": plat_sensitivity,
            "compliance_sensitivity": 0.1,
            "account_health_score": health_num,
            "budget_impact": 0.0,
        }
        pol_result = compute_policy_evaluation(policy_ctx)

        epc = float(offers[0].epc or 0) if offers else 1.0
        cvr = float(offers[0].conversion_rate or 0) if offers else 0.02
        uc_ctx = {
            "revenue_potential": epc,
            "conversion_rate": cvr,
            "traffic_estimate": 1000,
            "content_cost": 10.0,
            "platform_cost": 0.0,
            "paid_spend": 0.0,
            "tool_cost": 5.0,
            "time_to_revenue_days": 30,
            "concentration_share": 1.0 / max(len(accts), 1),
        }
        uc_result = compute_upside_cost_estimate(uc_ctx)

        dec = BrainDecision(
            brand_id=brand_id,
            decision_class=dec_result["decision_class"],
            objective=dec_result["objective"],
            target_scope=f"account:{plat}",
            target_id=a.id,
            selected_action=dec_result["selected_action"],
            alternatives_json=dec_result["alternatives"],
            confidence=conf_result["confidence_score"],
            policy_mode=pol_result["policy_mode"],
            expected_upside=uc_result["expected_upside"],
            expected_cost=uc_result["expected_cost"],
            downstream_action=dec_result["downstream_action"],
            inputs_json=ctx,
            explanation=dec_result["explanation"],
        )
        db.add(dec)
        await db.flush()
        await db.refresh(dec)
        decisions_created += 1

        pol = PolicyEvaluation(
            brand_id=brand_id, decision_id=dec.id,
            action_ref=f"{dec_result['decision_class']}:account:{a.id}",
            policy_mode=pol_result["policy_mode"], reason=pol_result["reason"],
            approval_needed=pol_result["approval_needed"],
            hard_stop_rule=pol_result["hard_stop_rule"],
            rollback_rule=pol_result["rollback_rule"],
            risk_score=pol_result["risk_score"], cost_impact=pol_result["cost_impact"],
            inputs_json=policy_ctx, explanation=pol_result["explanation"],
        )
        db.add(pol)
        policies_created += 1

        cr = ConfidenceReport(
            brand_id=brand_id, decision_id=dec.id,
            scope_label=f"account:{plat}:{a.id}",
            confidence_score=conf_result["confidence_score"],
            confidence_band=conf_result["confidence_band"],
            signal_strength=conf_result["signal_strength"],
            historical_precedent=conf_result["historical_precedent"],
            saturation_risk=conf_result["saturation_risk"],
            memory_support=conf_result["memory_support"],
            data_completeness=conf_result["data_completeness"],
            execution_history=conf_result["execution_history"],
            blocker_severity=conf_result["blocker_severity"],
            uncertainty_factors_json=conf_result["uncertainty_factors"],
            explanation=conf_result["explanation"],
        )
        db.add(cr)
        confidence_created += 1

        uc = UpsideCostEstimate(
            brand_id=brand_id, decision_id=dec.id,
            scope_label=f"account:{plat}:{a.id}",
            expected_upside=uc_result["expected_upside"],
            expected_cost=uc_result["expected_cost"],
            expected_payback_days=uc_result["expected_payback_days"],
            operational_burden=uc_result["operational_burden"],
            concentration_risk=uc_result["concentration_risk"],
            net_value=uc_result["net_value"],
            inputs_json=uc_ctx, explanation=uc_result["explanation"],
        )
        db.add(uc)
        estimates_created += 1

        cat_map = {
            "launch": "new_launch", "scale": "more_output", "monetize": "monetization_fix",
            "recover": "recovery_action", "suppress": "funnel_fix", "throttle": "funnel_fix",
            "test": "new_launch", "escalate": "recovery_action",
        }
        arb_candidates.append({
            "category": cat_map.get(dec_result["decision_class"], "more_output"),
            "label": f"{dec_result['decision_class']} — {plat} account {str(a.id)[:8]}",
            "net_value": uc_result["net_value"],
            "confidence": conf_result["confidence_score"],
            "urgency": min(1.0, saturation * 0.5 + fatigue * 0.3 + (0.5 if dec_result["decision_class"] in ("recover", "escalate") else 0)),
        })

    arb_result = compute_arbitration(arb_candidates)
    arb = ArbitrationReport(
        brand_id=brand_id,
        ranked_priorities_json=arb_result["ranked_priorities"],
        chosen_winner_class=arb_result["chosen_winner_class"],
        chosen_winner_label=arb_result["chosen_winner_label"],
        rejected_actions_json=arb_result["rejected_actions"],
        competing_count=arb_result["competing_count"],
        net_value_chosen=arb_result["net_value_chosen"],
        inputs_json={"candidates_count": len(arb_candidates)},
        explanation=arb_result["explanation"],
    )
    db.add(arb)

    await db.flush()
    return {
        "decisions_created": decisions_created,
        "policies_created": policies_created,
        "confidence_reports_created": confidence_created,
        "estimates_created": estimates_created,
        "arbitration_reports_created": 1 if arb_candidates else 0,
    }
