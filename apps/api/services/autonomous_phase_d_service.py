"""Autonomous Execution Phase D — agent orchestration, revenue pressure, overrides, blockers, escalations."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.accounts import CreatorAccount
from packages.db.models.autonomous_phase_b import MonetizationRoute, SuppressionExecution
from packages.db.models.autonomous_phase_d import (
    AgentMessage,
    AgentRun,
    BlockerDetectionReport,
    EscalationEvent,
    OperatorCommand,
    OverridePolicy,
    RevenuePressureReport,
)
from packages.db.models.offers import Offer
from packages.scoring.autonomous_phase_d_engine import (
    compute_override_policies,
    compute_revenue_pressure,
    detect_blockers,
    generate_escalations,
    run_agent_cycle,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Serializer helpers (sync — no await)
# ---------------------------------------------------------------------------

def _agent_run_out(r: AgentRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "agent_type": r.agent_type,
        "run_status": r.run_status,
        "started_at": r.started_at,
        "completed_at": r.completed_at,
        "input_context_json": r.input_context_json,
        "output_json": r.output_json,
        "commands_json": r.commands_json,
        "error_message": r.error_message,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _agent_message_out(m: AgentMessage) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "agent_run_id": str(m.agent_run_id),
        "sender_agent": m.sender_agent,
        "receiver_agent": m.receiver_agent,
        "message_type": m.message_type,
        "payload_json": m.payload_json,
        "explanation": m.explanation,
        "is_active": m.is_active,
        "created_at": m.created_at,
        "updated_at": m.updated_at,
    }


def _pressure_out(r: RevenuePressureReport) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "brand_id": str(r.brand_id),
        "next_commands_json": r.next_commands_json,
        "next_launches_json": r.next_launches_json,
        "biggest_blocker": r.biggest_blocker,
        "biggest_missed_opportunity": r.biggest_missed_opportunity,
        "biggest_weak_lane_to_kill": r.biggest_weak_lane_to_kill,
        "underused_monetization_class": r.underused_monetization_class,
        "underbuilt_platform": r.underbuilt_platform,
        "missing_account_suggestion": r.missing_account_suggestion,
        "unexploited_winner": r.unexploited_winner,
        "leaking_funnel": r.leaking_funnel,
        "inactive_asset_class": r.inactive_asset_class,
        "pressure_score": r.pressure_score,
        "explanation": r.explanation,
        "is_active": r.is_active,
        "created_at": r.created_at,
        "updated_at": r.updated_at,
    }


def _override_out(p: OverridePolicy) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "brand_id": str(p.brand_id),
        "action_ref": p.action_ref,
        "override_mode": p.override_mode,
        "confidence_threshold": p.confidence_threshold,
        "approval_needed": p.approval_needed,
        "rollback_available": p.rollback_available,
        "rollback_plan": p.rollback_plan,
        "hard_stop_rule": p.hard_stop_rule,
        "audit_trail_json": p.audit_trail_json,
        "explanation": p.explanation,
        "is_active": p.is_active,
        "created_at": p.created_at,
        "updated_at": p.updated_at,
    }


def _blocker_out(b: BlockerDetectionReport) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "brand_id": str(b.brand_id),
        "blocker": b.blocker,
        "severity": b.severity,
        "affected_scope": b.affected_scope,
        "operator_action_needed": b.operator_action_needed,
        "deadline_or_urgency": b.deadline_or_urgency,
        "consequence_if_ignored": b.consequence_if_ignored,
        "explanation": b.explanation,
        "status": b.status,
        "resolved_at": b.resolved_at,
        "is_active": b.is_active,
        "created_at": b.created_at,
        "updated_at": b.updated_at,
    }


def _escalation_out(e: EscalationEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "brand_id": str(e.brand_id),
        "command": e.command,
        "reason": e.reason,
        "supporting_data_json": e.supporting_data_json,
        "confidence": e.confidence,
        "urgency": e.urgency,
        "expected_upside": e.expected_upside,
        "expected_cost": e.expected_cost,
        "time_to_signal": e.time_to_signal,
        "time_to_profit": e.time_to_profit,
        "risk": e.risk,
        "required_resources": e.required_resources,
        "consequence_if_ignored": e.consequence_if_ignored,
        "status": e.status,
        "resolved_at": e.resolved_at,
        "is_active": e.is_active,
        "created_at": e.created_at,
        "updated_at": e.updated_at,
    }


def _command_out(c: OperatorCommand) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "brand_id": str(c.brand_id),
        "escalation_event_id": str(c.escalation_event_id) if c.escalation_event_id else None,
        "blocker_report_id": str(c.blocker_report_id) if c.blocker_report_id else None,
        "command_text": c.command_text,
        "command_type": c.command_type,
        "urgency": c.urgency,
        "status": c.status,
        "resolved_at": c.resolved_at,
        "is_active": c.is_active,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
    }


# ---------------------------------------------------------------------------
# Context builder (gathers signals across existing models)
# ---------------------------------------------------------------------------

async def _build_brand_context(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    accts_count = (await db.execute(
        select(func.count()).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalar_one()

    offers_count = (await db.execute(
        select(func.count()).where(Offer.brand_id == brand_id, Offer.is_active.is_(True))
    )).scalar_one()

    supp_count = (await db.execute(
        select(func.count()).where(SuppressionExecution.brand_id == brand_id, SuppressionExecution.is_active.is_(True))
    )).scalar_one()

    accounts = (await db.execute(
        select(CreatorAccount).where(CreatorAccount.brand_id == brand_id, CreatorAccount.is_active.is_(True))
    )).scalars().all()

    _health_map = {"healthy": 1.0, "warning": 0.6, "degraded": 0.35, "critical": 0.15, "suspended": 0.05}
    avg_health = 0.5
    active_platforms: list[str] = []
    accounts_not_ready: list[str] = []
    if accounts:
        healths = [_health_map.get(str(a.account_health.value).lower(), 0.5) if a.account_health else 0.5 for a in accounts]
        avg_health = sum(healths) / len(healths)
        for a in accounts:
            plat = str(a.platform).lower() if a.platform else ""
            if plat and plat not in active_platforms:
                active_platforms.append(plat)
            h = _health_map.get(str(a.account_health.value).lower(), 0.5) if a.account_health else 0.5
            if h < 0.3:
                accounts_not_ready.append(str(a.id))

    active_mon: list[str] = []
    routes = (await db.execute(
        select(MonetizationRoute).where(MonetizationRoute.brand_id == brand_id, MonetizationRoute.is_active.is_(True))
    )).scalars().all()
    for r in routes:
        rc = str(r.route_class or "")
        if rc and rc not in active_mon:
            active_mon.append(rc)

    return {
        "accounts_count": accts_count,
        "offers_count": offers_count,
        "queue_depth": 0,
        "avg_health": round(avg_health, 4),
        "avg_engagement": 0.02,
        "revenue_trend": "flat",
        "suppression_count": supp_count,
        "funnel_leak_score": 0.3,
        "paid_active": False,
        "sponsor_pipeline": 0,
        "retention_risk": 0.2,
        "provider_failures": False,
        "active_monetization_classes": active_mon,
        "active_platforms": active_platforms,
        "accounts": accts_count,
        "queue_winners_unexploited": 0,
        "inactive_asset_classes": [],
        "next_launch_candidates": [],
        "credentials_missing": [],
        "accounts_not_ready": accounts_not_ready,
        "budget_remaining": 1000,
        "compliance_holds": [],
        "platform_capacity": {},
        "provider_available": True,
        "queue_failure_rate": 0.0,
        "policy_sensitive_lanes": [],
        "default_mode": "guarded",
    }


# ---------------------------------------------------------------------------
# Agent orchestration
# ---------------------------------------------------------------------------

async def recompute_agent_orchestration(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _build_brand_context(db, brand_id)
    results = run_agent_cycle(ctx)
    batch = results[0]

    await db.execute(
        update(AgentRun).where(AgentRun.brand_id == brand_id, AgentRun.is_active.is_(True)).values(is_active=False)
    )

    runs_created = 0
    msgs_created = 0
    for rd in batch["runs"]:
        run = AgentRun(
            brand_id=brand_id,
            agent_type=rd["agent_type"],
            run_status=rd["run_status"],
            started_at=datetime.fromisoformat(rd["started_at"]),
            completed_at=datetime.fromisoformat(rd["completed_at"]),
            input_context_json=rd.get("input_context_json"),
            output_json=rd.get("output_json"),
            commands_json=rd.get("commands_json"),
        )
        db.add(run)
        await db.flush()
        runs_created += 1

        for md in batch["messages"]:
            if md.get("sender_agent") == rd["agent_type"]:
                msg = AgentMessage(
                    agent_run_id=run.id,
                    sender_agent=md["sender_agent"],
                    receiver_agent=md.get("receiver_agent"),
                    message_type=md.get("message_type", "recommendation"),
                    payload_json=md.get("payload_json"),
                    explanation=md.get("explanation"),
                )
                db.add(msg)
                msgs_created += 1

    return {"agent_runs_created": runs_created, "messages_created": msgs_created}


async def list_agent_runs(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> dict[str, Any]:
    runs = (await db.execute(
        select(AgentRun).where(AgentRun.brand_id == brand_id, AgentRun.is_active.is_(True))
        .order_by(AgentRun.created_at.desc()).limit(limit)
    )).scalars().all()

    run_ids = [r.id for r in runs]
    messages: list[AgentMessage] = []
    if run_ids:
        messages = list((await db.execute(
            select(AgentMessage).where(AgentMessage.agent_run_id.in_(run_ids), AgentMessage.is_active.is_(True))
            .order_by(AgentMessage.created_at.desc())
        )).scalars().all())

    return {
        "runs": [_agent_run_out(r) for r in runs],
        "messages": [_agent_message_out(m) for m in messages],
    }


# ---------------------------------------------------------------------------
# Revenue pressure
# ---------------------------------------------------------------------------

async def recompute_revenue_pressure(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _build_brand_context(db, brand_id)
    result = compute_revenue_pressure(ctx)

    await db.execute(
        update(RevenuePressureReport).where(
            RevenuePressureReport.brand_id == brand_id, RevenuePressureReport.is_active.is_(True)
        ).values(is_active=False)
    )

    rp = RevenuePressureReport(
        brand_id=brand_id,
        next_commands_json=result["next_commands_json"],
        next_launches_json=result["next_launches_json"],
        biggest_blocker=result["biggest_blocker"],
        biggest_missed_opportunity=result["biggest_missed_opportunity"],
        biggest_weak_lane_to_kill=result["biggest_weak_lane_to_kill"],
        underused_monetization_class=result.get("underused_monetization_class"),
        underbuilt_platform=result.get("underbuilt_platform"),
        missing_account_suggestion=result.get("missing_account_suggestion"),
        unexploited_winner=result.get("unexploited_winner"),
        leaking_funnel=result.get("leaking_funnel"),
        inactive_asset_class=result.get("inactive_asset_class"),
        pressure_score=result["pressure_score"],
        explanation=result["explanation"],
    )
    db.add(rp)
    return {"pressure_reports_created": 1}


async def list_revenue_pressure(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 10) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(RevenuePressureReport).where(
            RevenuePressureReport.brand_id == brand_id, RevenuePressureReport.is_active.is_(True)
        ).order_by(RevenuePressureReport.created_at.desc()).limit(limit)
    )).scalars().all()
    return [_pressure_out(r) for r in rows]


# ---------------------------------------------------------------------------
# Override policies
# ---------------------------------------------------------------------------

_DEFAULT_ACTION_REFS = [
    "publish_content", "increase_paid_spend", "pause_account",
    "launch_new_account", "approve_sponsor_deal", "send_outreach_email",
    "change_pricing", "suppress_lane", "scale_winner",
    "emergency_budget_cap", "create_content_brief", "trigger_reactivation",
]


async def recompute_override_policies(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _build_brand_context(db, brand_id)
    policies = compute_override_policies(_DEFAULT_ACTION_REFS, ctx)

    await db.execute(
        update(OverridePolicy).where(
            OverridePolicy.brand_id == brand_id, OverridePolicy.is_active.is_(True)
        ).values(is_active=False)
    )

    created = 0
    for p in policies:
        obj = OverridePolicy(
            brand_id=brand_id,
            action_ref=p["action_ref"],
            override_mode=p["override_mode"],
            confidence_threshold=p["confidence_threshold"],
            approval_needed=p["approval_needed"],
            rollback_available=p["rollback_available"],
            rollback_plan=p.get("rollback_plan"),
            hard_stop_rule=p.get("hard_stop_rule"),
            audit_trail_json=p.get("audit_trail_json"),
            explanation=p.get("explanation"),
        )
        db.add(obj)
        created += 1

    return {"override_policies_created": created}


async def list_override_policies(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(OverridePolicy).where(
            OverridePolicy.brand_id == brand_id, OverridePolicy.is_active.is_(True)
        ).order_by(OverridePolicy.created_at.desc()).limit(limit)
    )).scalars().all()
    return [_override_out(p) for p in rows]


# ---------------------------------------------------------------------------
# Blocker detection
# ---------------------------------------------------------------------------

async def recompute_blocker_detection(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _build_brand_context(db, brand_id)
    blockers = detect_blockers(ctx)

    await db.execute(
        update(BlockerDetectionReport).where(
            BlockerDetectionReport.brand_id == brand_id,
            BlockerDetectionReport.is_active.is_(True),
            BlockerDetectionReport.status == "open",
        ).values(is_active=False)
    )

    created = 0
    for b in blockers:
        obj = BlockerDetectionReport(
            brand_id=brand_id,
            blocker=b["blocker"],
            severity=b["severity"],
            affected_scope=b["affected_scope"],
            operator_action_needed=b["operator_action_needed"],
            deadline_or_urgency=b["deadline_or_urgency"],
            consequence_if_ignored=b["consequence_if_ignored"],
            explanation=b.get("explanation"),
        )
        db.add(obj)
        created += 1

    return {"blockers_created": created}


async def list_blocker_detection(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(BlockerDetectionReport).where(
            BlockerDetectionReport.brand_id == brand_id, BlockerDetectionReport.is_active.is_(True)
        ).order_by(BlockerDetectionReport.created_at.desc()).limit(limit)
    )).scalars().all()
    return [_blocker_out(b) for b in rows]


# ---------------------------------------------------------------------------
# Operator escalation
# ---------------------------------------------------------------------------

async def recompute_escalations(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    ctx = await _build_brand_context(db, brand_id)
    blockers = detect_blockers(ctx)
    pressure = compute_revenue_pressure(ctx)
    escalation_dicts = generate_escalations(blockers, pressure)

    await db.execute(
        update(EscalationEvent).where(
            EscalationEvent.brand_id == brand_id,
            EscalationEvent.is_active.is_(True),
            EscalationEvent.status == "pending",
        ).values(is_active=False)
    )

    esc_created = 0
    cmd_created = 0
    for e in escalation_dicts:
        evt = EscalationEvent(
            brand_id=brand_id,
            command=e["command"],
            reason=e["reason"],
            supporting_data_json=e.get("supporting_data_json"),
            confidence=e["confidence"],
            urgency=e["urgency"],
            expected_upside=e["expected_upside"],
            expected_cost=e["expected_cost"],
            time_to_signal=e.get("time_to_signal"),
            time_to_profit=e.get("time_to_profit"),
            risk=e.get("risk", "low"),
            required_resources=e.get("required_resources"),
            consequence_if_ignored=e.get("consequence_if_ignored"),
        )
        db.add(evt)
        await db.flush()
        esc_created += 1

        cmd = OperatorCommand(
            brand_id=brand_id,
            escalation_event_id=evt.id,
            command_text=e["command"],
            command_type=e.get("supporting_data_json", {}).get("blocker", "revenue_pressure"),
            urgency=e["urgency"],
        )
        db.add(cmd)
        cmd_created += 1

    return {"escalations_created": esc_created, "operator_commands_created": cmd_created}


async def list_escalations(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(EscalationEvent).where(
            EscalationEvent.brand_id == brand_id, EscalationEvent.is_active.is_(True)
        ).order_by(EscalationEvent.created_at.desc()).limit(limit)
    )).scalars().all()
    return [_escalation_out(e) for e in rows]


async def list_operator_commands(db: AsyncSession, brand_id: uuid.UUID, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = (await db.execute(
        select(OperatorCommand).where(
            OperatorCommand.brand_id == brand_id, OperatorCommand.is_active.is_(True)
        ).order_by(OperatorCommand.created_at.desc()).limit(limit)
    )).scalars().all()
    return [_command_out(c) for c in rows]
