"""Brain Architecture Phase D — service layer for meta-monitoring, self-correction, readiness, escalation."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.brain_architecture import BrainMemoryEntry
from packages.db.models.brain_phase_b import BrainDecision, ConfidenceReport, PolicyEvaluation
from packages.db.models.brain_phase_c import AgentRunV2, SharedContextEvent
from packages.db.models.brain_phase_d import (
    BrainEscalation,
    MetaMonitoringReport,
    ReadinessBrainReport,
    SelfCorrectionAction,
)
from packages.db.models.offers import Offer
from packages.scoring.brain_phase_d_engine import (
    compute_brain_escalations,
    compute_meta_monitoring,
    compute_readiness_brain,
    compute_self_corrections,
)


# ── List helpers ──────────────────────────────────────────────────────

async def list_meta_monitoring(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 20) -> list[dict]:
    q = await db.execute(
        select(MetaMonitoringReport)
        .where(MetaMonitoringReport.brand_id == brand_id, MetaMonitoringReport.is_active.is_(True))
        .order_by(MetaMonitoringReport.created_at.desc()).limit(limit)
    )
    return [_mm_out(r) for r in q.scalars().all()]


async def list_self_corrections(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict]:
    q = await db.execute(
        select(SelfCorrectionAction)
        .where(SelfCorrectionAction.brand_id == brand_id, SelfCorrectionAction.is_active.is_(True))
        .order_by(SelfCorrectionAction.created_at.desc()).limit(limit)
    )
    return [_sc_out(r) for r in q.scalars().all()]


async def list_readiness_brain(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 10) -> list[dict]:
    q = await db.execute(
        select(ReadinessBrainReport)
        .where(ReadinessBrainReport.brand_id == brand_id, ReadinessBrainReport.is_active.is_(True))
        .order_by(ReadinessBrainReport.created_at.desc()).limit(limit)
    )
    return [_rb_out(r) for r in q.scalars().all()]


async def list_brain_escalations(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict]:
    q = await db.execute(
        select(BrainEscalation)
        .where(BrainEscalation.brand_id == brand_id, BrainEscalation.is_active.is_(True))
        .order_by(BrainEscalation.created_at.desc()).limit(limit)
    )
    return [_be_out(r) for r in q.scalars().all()]


# ── Full recompute pipeline ──────────────────────────────────────────

async def recompute_meta_monitoring(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, int]:
    _health_map = {"healthy": 1.0, "warning": 0.6, "degraded": 0.35, "critical": 0.15, "suspended": 0.05}

    # Gather stats for meta-monitoring
    decisions_q = await db.execute(
        select(BrainDecision).where(BrainDecision.brand_id == brand_id, BrainDecision.is_active.is_(True))
    )
    decisions = decisions_q.scalars().all()
    low_conf_decisions = sum(1 for d in decisions if d.confidence < 0.5)

    policies_q = await db.execute(
        select(PolicyEvaluation).where(PolicyEvaluation.brand_id == brand_id, PolicyEvaluation.is_active.is_(True))
    )
    policies = policies_q.scalars().all()
    manual_count = sum(1 for p in policies if p.policy_mode == "manual")

    memory_q = await db.execute(
        select(BrainMemoryEntry).where(BrainMemoryEntry.brand_id == brand_id, BrainMemoryEntry.is_active.is_(True))
    )
    memories = memory_q.scalars().all()

    agent_runs_q = await db.execute(
        select(AgentRunV2).where(AgentRunV2.brand_id == brand_id, AgentRunV2.is_active.is_(True))
    )
    agent_runs = agent_runs_q.scalars().all()
    dead_agents = sum(1 for r in agent_runs if r.run_status == "error")
    low_signal = sum(1 for r in agent_runs if r.confidence < 0.3)

    ctx_events_q = await db.execute(
        select(SharedContextEvent).where(SharedContextEvent.brand_id == brand_id, SharedContextEvent.is_active.is_(True))
    )
    ctx_events = ctx_events_q.scalars().all()
    escalation_events = sum(1 for e in ctx_events if e.event_type in ("launch_blocked", "system_throttle"))

    accts_q = await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )
    accts = accts_q.scalars().all()

    offers_q = await db.execute(select(Offer).where(Offer.brand_id == brand_id, Offer.is_active.is_(True)))
    offers = offers_q.scalars().all()

    monitoring_ctx: dict[str, Any] = {
        "total_decisions": len(decisions),
        "low_confidence_decisions": low_conf_decisions,
        "manual_mode_count": manual_count,
        "total_policies": len(policies),
        "execution_failures": 0,
        "total_executions": max(len(agent_runs), 1),
        "memory_entries": len(memories),
        "stale_memory_entries": 0,
        "escalation_count": escalation_events,
        "agent_run_count": len(agent_runs),
        "dead_agent_count": dead_agents,
        "low_signal_agent_count": low_signal,
        "wasted_action_count": 0,
        "queue_depth": 0,
    }

    mon_result = compute_meta_monitoring(monitoring_ctx)

    # Deactivate old records
    await db.execute(update(MetaMonitoringReport).where(MetaMonitoringReport.brand_id == brand_id, MetaMonitoringReport.is_active.is_(True)).values(is_active=False))
    await db.execute(update(SelfCorrectionAction).where(SelfCorrectionAction.brand_id == brand_id, SelfCorrectionAction.is_active.is_(True)).values(is_active=False))
    await db.execute(update(ReadinessBrainReport).where(ReadinessBrainReport.brand_id == brand_id, ReadinessBrainReport.is_active.is_(True)).values(is_active=False))
    await db.execute(update(BrainEscalation).where(BrainEscalation.brand_id == brand_id, BrainEscalation.is_active.is_(True)).values(is_active=False))

    mm = MetaMonitoringReport(
        brand_id=brand_id,
        health_score=mon_result["health_score"],
        health_band=mon_result["health_band"],
        decision_quality_score=mon_result["decision_quality_score"],
        confidence_drift_score=mon_result["confidence_drift_score"],
        policy_drift_score=mon_result["policy_drift_score"],
        execution_failure_rate=mon_result["execution_failure_rate"],
        memory_quality_score=mon_result["memory_quality_score"],
        escalation_rate=mon_result["escalation_rate"],
        queue_congestion=mon_result["queue_congestion"],
        dead_agent_count=mon_result["dead_agent_count"],
        low_signal_count=mon_result["low_signal_count"],
        wasted_action_count=mon_result["wasted_action_count"],
        weak_areas_json=mon_result["weak_areas"],
        recommended_corrections_json=mon_result["recommended_corrections"],
        inputs_json=monitoring_ctx,
        confidence=mon_result["confidence"],
        explanation=mon_result["explanation"],
    )
    db.add(mm)

    # Self-corrections
    corrections = compute_self_corrections(mon_result)
    corrections_created = 0
    for c in corrections:
        sc = SelfCorrectionAction(
            brand_id=brand_id,
            correction_type=c["correction_type"],
            reason=c["reason"],
            effect_target=c["effect_target"],
            severity=c["severity"],
            confidence=c["confidence"],
            explanation=c["explanation"],
        )
        db.add(sc)
        corrections_created += 1

    # Readiness brain
    acct_health_avg = 0.5
    if accts:
        scores = [_health_map.get(a.account_health.value if a.account_health else "healthy", 0.5) for a in accts]
        acct_health_avg = sum(scores) / len(scores)

    conf_avg = 0.5
    if decisions:
        conf_avg = sum(d.confidence for d in decisions) / len(decisions)

    readiness_ctx: dict[str, Any] = {
        "health_score": mon_result["health_score"],
        "has_offers": len(offers) > 0,
        "has_accounts": len(accts) > 0,
        "has_warmup_plans": len(accts) > 0,
        "has_memory": len(memories) > 0,
        "account_health_avg": acct_health_avg,
        "execution_failure_rate": mon_result["execution_failure_rate"],
        "confidence_avg": conf_avg,
        "has_platform_credentials": False,
        "active_blocker_count": dead_agents,
        "escalation_rate": mon_result["escalation_rate"],
    }

    rd_result = compute_readiness_brain(readiness_ctx)

    rb = ReadinessBrainReport(
        brand_id=brand_id,
        readiness_score=rd_result["readiness_score"],
        readiness_band=rd_result["readiness_band"],
        blockers_json=rd_result["blockers"],
        allowed_actions_json=rd_result["allowed_actions"],
        forbidden_actions_json=rd_result["forbidden_actions"],
        inputs_json=readiness_ctx,
        confidence=rd_result["confidence"],
        explanation=rd_result["explanation"],
    )
    db.add(rb)

    # Brain escalations
    esc_ctx = {
        **readiness_ctx,
        "blockers": rd_result["blockers"],
        "forbidden_actions": rd_result["forbidden_actions"],
    }
    escalations = compute_brain_escalations(esc_ctx)
    esc_created = 0
    for e in escalations:
        be = BrainEscalation(
            brand_id=brand_id,
            escalation_type=e["escalation_type"],
            command=e["command"],
            urgency=e["urgency"],
            expected_upside_unlocked=e["expected_upside_unlocked"],
            expected_cost_of_delay=e["expected_cost_of_delay"],
            affected_scope=e["affected_scope"],
            confidence=e["confidence"],
            explanation=e["explanation"],
        )
        db.add(be)
        esc_created += 1

    await db.flush()
    return {
        "monitoring_reports_created": 1,
        "corrections_created": corrections_created,
        "readiness_reports_created": 1,
        "escalations_created": esc_created,
    }


# ── Serialization helpers ─────────────────────────────────────────────

def _mm_out(r: MetaMonitoringReport) -> dict[str, Any]:
    return {
        "id": r.id, "brand_id": r.brand_id,
        "health_score": r.health_score, "health_band": r.health_band,
        "decision_quality_score": r.decision_quality_score,
        "confidence_drift_score": r.confidence_drift_score,
        "policy_drift_score": r.policy_drift_score,
        "execution_failure_rate": r.execution_failure_rate,
        "memory_quality_score": r.memory_quality_score,
        "escalation_rate": r.escalation_rate,
        "queue_congestion": r.queue_congestion,
        "dead_agent_count": r.dead_agent_count,
        "low_signal_count": r.low_signal_count,
        "wasted_action_count": r.wasted_action_count,
        "weak_areas_json": r.weak_areas_json,
        "recommended_corrections_json": r.recommended_corrections_json,
        "inputs_json": r.inputs_json,
        "confidence": r.confidence, "explanation": r.explanation,
        "is_active": r.is_active, "created_at": r.created_at, "updated_at": r.updated_at,
    }


def _sc_out(r: SelfCorrectionAction) -> dict[str, Any]:
    return {
        "id": r.id, "brand_id": r.brand_id,
        "correction_type": r.correction_type, "reason": r.reason,
        "effect_target": r.effect_target, "severity": r.severity,
        "applied": r.applied, "payload_json": r.payload_json,
        "confidence": r.confidence, "explanation": r.explanation,
        "is_active": r.is_active, "created_at": r.created_at, "updated_at": r.updated_at,
    }


def _rb_out(r: ReadinessBrainReport) -> dict[str, Any]:
    return {
        "id": r.id, "brand_id": r.brand_id,
        "readiness_score": r.readiness_score, "readiness_band": r.readiness_band,
        "blockers_json": r.blockers_json,
        "allowed_actions_json": r.allowed_actions_json,
        "forbidden_actions_json": r.forbidden_actions_json,
        "inputs_json": r.inputs_json,
        "confidence": r.confidence, "explanation": r.explanation,
        "is_active": r.is_active, "created_at": r.created_at, "updated_at": r.updated_at,
    }


def _be_out(r: BrainEscalation) -> dict[str, Any]:
    return {
        "id": r.id, "brand_id": r.brand_id,
        "escalation_type": r.escalation_type, "command": r.command,
        "urgency": r.urgency,
        "expected_upside_unlocked": r.expected_upside_unlocked,
        "expected_cost_of_delay": r.expected_cost_of_delay,
        "affected_scope": r.affected_scope,
        "supporting_data_json": r.supporting_data_json,
        "confidence": r.confidence, "resolved": r.resolved,
        "explanation": r.explanation,
        "is_active": r.is_active, "created_at": r.created_at, "updated_at": r.updated_at,
    }
