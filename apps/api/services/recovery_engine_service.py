"""Recovery Engine Service — detect, decide, persist, recover."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.hyperscale import DegradationEvent
from packages.db.models.provider_registry import ProviderBlocker
from packages.db.models.recovery_engine import (
    RecoveryIncidentV2,
    RecoveryOutcome,
    RerouteAction,
    RollbackAction,
    ThrottlingAction,
)
from packages.scoring.recovery_rollback_engine import decide_recovery, detect_incidents, should_escalate


async def recompute_recovery(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    await db.execute(delete(RecoveryOutcome).where(RecoveryOutcome.incident_id.in_(
        select(RecoveryIncidentV2.id).where(RecoveryIncidentV2.organization_id == org_id)
    )))
    await db.execute(delete(ThrottlingAction).where(ThrottlingAction.incident_id.in_(
        select(RecoveryIncidentV2.id).where(RecoveryIncidentV2.organization_id == org_id)
    )))
    await db.execute(delete(RerouteAction).where(RerouteAction.incident_id.in_(
        select(RecoveryIncidentV2.id).where(RecoveryIncidentV2.organization_id == org_id)
    )))
    await db.execute(delete(RollbackAction).where(RollbackAction.incident_id.in_(
        select(RecoveryIncidentV2.id).where(RecoveryIncidentV2.organization_id == org_id)
    )))
    await db.execute(delete(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org_id))

    system_state = await _gather_state(db, org_id)
    incidents = detect_incidents(system_state)

    for inc in incidents:
        aid = None
        if inc.get("affected_id"):
            try: aid = uuid.UUID(str(inc["affected_id"]))
            except (ValueError, AttributeError): pass
        rec_inc = RecoveryIncidentV2(organization_id=org_id, incident_type=inc["incident_type"], severity=inc["severity"], affected_scope=inc["affected_scope"], affected_id=aid, detail=inc["detail"], auto_recoverable=inc["auto_recoverable"])
        db.add(rec_inc); await db.flush()

        recovery = decide_recovery(inc)
        escalate = should_escalate(inc, recovery)
        rec_inc.recovery_status = "escalated" if escalate else "auto_recovering" if recovery["decision"] == "auto_recover" else "pending_review"

        for action in recovery.get("actions", []):
            atype = action.get("type", "")
            if atype == "rollback":
                db.add(RollbackAction(incident_id=rec_inc.id, rollback_type=atype, rollback_target=action.get("target", ""), execution_status="pending"))
            elif atype == "reroute":
                db.add(RerouteAction(incident_id=rec_inc.id, from_path=action.get("from", ""), to_path=action.get("to", ""), reason=action.get("detail", ""), execution_status="pending"))
            elif atype == "throttle":
                db.add(ThrottlingAction(incident_id=rec_inc.id, throttle_target=action.get("target", ""), throttle_level=action.get("level", "50pct"), reason=action.get("detail", ""), execution_status="pending"))

    await db.flush()
    return {"rows_processed": len(incidents), "status": "completed"}


async def _gather_state(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    state: dict[str, Any] = {"provider_failures": [], "publish_failures": [], "bad_scaling": [], "experiment_failures": [], "broken_routes": [], "dependency_outages": [], "unsafe_state": False}

    prov_blockers = list((await db.execute(select(ProviderBlocker).where(ProviderBlocker.is_active.is_(True)).limit(10))).scalars().all())
    for b in prov_blockers:
        if b.severity == "critical":
            state["provider_failures"].append({"id": str(b.id), "name": b.provider_key, "error": b.description})

    deg_events = list((await db.execute(select(DegradationEvent).where(DegradationEvent.organization_id == org_id, DegradationEvent.recovered.is_(False), DegradationEvent.is_active.is_(True)).limit(5))).scalars().all())
    for d in deg_events:
        state["dependency_outages"].append({"id": str(d.id), "name": d.degradation_type})

    return state


async def list_incidents(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org_id, RecoveryIncidentV2.is_active.is_(True)).order_by(RecoveryIncidentV2.created_at.desc()).limit(50))).scalars().all())

async def list_rollbacks(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(RollbackAction).join(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org_id, RollbackAction.is_active.is_(True)))).scalars().all())

async def list_reroutes(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(RerouteAction).join(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org_id, RerouteAction.is_active.is_(True)))).scalars().all())

async def list_throttles(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(ThrottlingAction).join(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org_id, ThrottlingAction.is_active.is_(True)))).scalars().all())

async def list_outcomes(db: AsyncSession, org_id: uuid.UUID) -> list:
    return list((await db.execute(select(RecoveryOutcome).join(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org_id, RecoveryOutcome.is_active.is_(True)))).scalars().all())

async def get_recovery_summary(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Downstream: quick recovery status for copilot."""
    incidents = list((await db.execute(select(RecoveryIncidentV2).where(RecoveryIncidentV2.organization_id == org_id, RecoveryIncidentV2.recovery_status != "resolved", RecoveryIncidentV2.is_active.is_(True)).limit(5))).scalars().all())
    return {
        "open_incidents": len(incidents),
        "critical": sum(1 for i in incidents if i.severity == "critical"),
        "auto_recovering": sum(1 for i in incidents if i.recovery_status == "auto_recovering"),
        "escalated": sum(1 for i in incidents if i.recovery_status == "escalated"),
        "incidents": [{"type": i.incident_type, "severity": i.severity, "status": i.recovery_status} for i in incidents[:3]],
    }


async def execute_pending_recovery_actions(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Auto-execute recovery actions where permission matrix allows autonomous behavior."""
    from apps.api.services.operator_permission_service import check_action

    executed = {"rollbacks": 0, "reroutes": 0, "throttles": 0, "skipped_guarded": 0, "errors": 0}

    auto_incidents = list((await db.execute(
        select(RecoveryIncidentV2).where(
            RecoveryIncidentV2.organization_id == org_id,
            RecoveryIncidentV2.recovery_status == "auto_recovering",
            RecoveryIncidentV2.is_active.is_(True),
        )
    )).scalars().all())

    for incident in auto_incidents:
        rollbacks = list((await db.execute(
            select(RollbackAction).where(RollbackAction.incident_id == incident.id, RollbackAction.execution_status == "pending")
        )).scalars().all())
        for rb in rollbacks:
            perm = await check_action(db, org_id, "rollback_action")
            if not perm.get("allowed", True):
                rb.execution_status = "awaiting_approval"
                executed["skipped_guarded"] += 1
                continue
            rb.execution_status = "executed"
            executed["rollbacks"] += 1

        reroutes = list((await db.execute(
            select(RerouteAction).where(RerouteAction.incident_id == incident.id, RerouteAction.execution_status == "pending")
        )).scalars().all())
        for rr in reroutes:
            perm = await check_action(db, org_id, "rollback_action")
            if not perm.get("allowed", True):
                rr.execution_status = "awaiting_approval"
                executed["skipped_guarded"] += 1
                continue
            rr.execution_status = "executed"
            executed["reroutes"] += 1

        throttles = list((await db.execute(
            select(ThrottlingAction).where(ThrottlingAction.incident_id == incident.id, ThrottlingAction.execution_status == "pending")
        )).scalars().all())
        for th in throttles:
            perm = await check_action(db, org_id, "rollback_action")
            if not perm.get("allowed", True):
                th.execution_status = "awaiting_approval"
                executed["skipped_guarded"] += 1
                continue
            th.execution_status = "executed"
            executed["throttles"] += 1

        all_done = all(
            a.execution_status in ("executed", "awaiting_approval")
            for a in rollbacks + reroutes + throttles
        )
        if all_done and rollbacks + reroutes + throttles:
            db.add(RecoveryOutcome(
                incident_id=incident.id,
                outcome_type="auto_resolved",
                success=True,
                detail=f"Executed {executed['rollbacks']}rb/{executed['reroutes']}rr/{executed['throttles']}th",
            ))
            incident.recovery_status = "resolved"

    await db.flush()
    return executed
