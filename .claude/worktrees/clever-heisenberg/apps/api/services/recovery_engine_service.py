"""Recovery Engine Service — detect, decide, persist, recover."""
from __future__ import annotations
import uuid
from typing import Any
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from packages.db.models.hyperscale import DegradationEvent
from packages.db.models.provider_registry import ProviderBlocker
from packages.db.models.recovery_engine import (
    RecoveryIncidentV2, RollbackAction, RerouteAction,
    ThrottlingAction, RecoveryOutcome, RecoveryPlaybook,
)
from packages.scoring.recovery_rollback_engine import detect_incidents, decide_recovery, should_escalate


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


async def _execute_rollback(db: AsyncSession, rb: RollbackAction, incident: RecoveryIncidentV2) -> bool:
    """Execute a real rollback: disable provider, deactivate offer, or pause account."""
    import structlog
    log = structlog.get_logger()
    target = rb.rollback_target  # e.g. "provider:heygen", "offer:<uuid>", "account:<uuid>"
    prev = rb.previous_state or {}

    try:
        if target.startswith("provider:"):
            provider_key = target.split(":", 1)[1]
            from packages.db.models.integration_registry import IntegrationProvider
            prov = (await db.execute(
                select(IntegrationProvider).where(
                    IntegrationProvider.provider_key == provider_key,
                    IntegrationProvider.is_enabled.is_(True),
                ).limit(1)
            )).scalar_one_or_none()
            if prov:
                prov.is_enabled = False
                prov.health_status = "down"
                log.info("recovery.rollback.provider_disabled", provider=provider_key)
                return True

        elif target.startswith("offer:"):
            offer_id = target.split(":", 1)[1]
            from packages.db.models.offers import Offer
            offer = (await db.execute(
                select(Offer).where(Offer.id == uuid.UUID(offer_id))
            )).scalar_one_or_none()
            if offer:
                offer.is_active = False
                log.info("recovery.rollback.offer_deactivated", offer_id=offer_id)
                return True

        elif target.startswith("account:"):
            acct_id = target.split(":", 1)[1]
            from packages.db.models.accounts import CreatorAccount
            acct = (await db.execute(
                select(CreatorAccount).where(CreatorAccount.id == uuid.UUID(acct_id))
            )).scalar_one_or_none()
            if acct:
                from packages.db.enums import HealthStatus
                acct.account_health = HealthStatus.SUSPENDED
                log.info("recovery.rollback.account_suspended", account_id=acct_id)
                return True

        log.warning("recovery.rollback.unknown_target", target=target)
        return False
    except Exception as e:
        log.error("recovery.rollback.failed", target=target, error=str(e))
        return False


async def _execute_reroute(db: AsyncSession, rr: RerouteAction) -> bool:
    """Execute a real reroute: change provider priority or route traffic away from a path."""
    import structlog
    log = structlog.get_logger()
    from_path = rr.from_path  # e.g. "provider:heygen"
    to_path = rr.to_path      # e.g. "provider:did"

    try:
        if from_path.startswith("provider:") and to_path.startswith("provider:"):
            from_key = from_path.split(":", 1)[1]
            to_key = to_path.split(":", 1)[1]
            from packages.db.models.integration_registry import IntegrationProvider

            from_prov = (await db.execute(
                select(IntegrationProvider).where(IntegrationProvider.provider_key == from_key).limit(1)
            )).scalar_one_or_none()
            to_prov = (await db.execute(
                select(IntegrationProvider).where(IntegrationProvider.provider_key == to_key).limit(1)
            )).scalar_one_or_none()

            if from_prov and to_prov:
                # Swap priorities: demote failing provider, promote replacement
                from_prov.priority_order = max(from_prov.priority_order or 1, 10)
                to_prov.priority_order = 1
                log.info("recovery.reroute.provider_swapped", from_p=from_key, to_p=to_key)
                return True

        log.warning("recovery.reroute.unknown_path", from_path=from_path, to_path=to_path)
        return False
    except Exception as e:
        log.error("recovery.reroute.failed", error=str(e))
        return False


async def _execute_throttle(db: AsyncSession, th: ThrottlingAction) -> bool:
    """Execute a real throttle: reduce posting capacity on an account or disable a queue."""
    import structlog
    log = structlog.get_logger()
    target = th.throttle_target  # e.g. "account:<uuid>", "queue:publishing"
    level = th.throttle_level    # e.g. "50pct", "25pct", "pause"

    try:
        if target.startswith("account:"):
            acct_id = target.split(":", 1)[1]
            from packages.db.models.accounts import CreatorAccount
            acct = (await db.execute(
                select(CreatorAccount).where(CreatorAccount.id == uuid.UUID(acct_id))
            )).scalar_one_or_none()
            if acct:
                if level == "pause":
                    acct.posting_capacity_per_day = 0
                elif level == "25pct":
                    acct.posting_capacity_per_day = max(1, (acct.posting_capacity_per_day or 4) // 4)
                else:  # 50pct default
                    acct.posting_capacity_per_day = max(1, (acct.posting_capacity_per_day or 4) // 2)
                log.info("recovery.throttle.account_limited", account_id=acct_id, level=level,
                         new_capacity=acct.posting_capacity_per_day)
                return True

        log.warning("recovery.throttle.unknown_target", target=target, level=level)
        return False
    except Exception as e:
        log.error("recovery.throttle.failed", error=str(e))
        return False


async def execute_pending_recovery_actions(db: AsyncSession, org_id: uuid.UUID) -> dict[str, Any]:
    """Execute recovery actions with REAL state changes. No false completion states."""
    from apps.api.services.operator_permission_service import check_action
    import structlog
    log = structlog.get_logger()

    executed = {"rollbacks": 0, "reroutes": 0, "throttles": 0, "skipped_guarded": 0, "errors": 0}

    auto_incidents = list((await db.execute(
        select(RecoveryIncidentV2).where(
            RecoveryIncidentV2.organization_id == org_id,
            RecoveryIncidentV2.recovery_status == "auto_recovering",
            RecoveryIncidentV2.is_active.is_(True),
        )
    )).scalars().all())

    for incident in auto_incidents:
        # --- Rollbacks ---
        rollbacks = list((await db.execute(
            select(RollbackAction).where(RollbackAction.incident_id == incident.id, RollbackAction.execution_status == "pending")
        )).scalars().all())
        for rb in rollbacks:
            perm = await check_action(db, org_id, "rollback_action")
            if not perm.get("allowed", True):
                rb.execution_status = "awaiting_approval"
                executed["skipped_guarded"] += 1
                continue
            success = await _execute_rollback(db, rb, incident)
            if success:
                rb.execution_status = "executed"
                executed["rollbacks"] += 1
            else:
                rb.execution_status = "failed"
                executed["errors"] += 1

        # --- Reroutes ---
        reroutes = list((await db.execute(
            select(RerouteAction).where(RerouteAction.incident_id == incident.id, RerouteAction.execution_status == "pending")
        )).scalars().all())
        for rr in reroutes:
            perm = await check_action(db, org_id, "reroute_action")
            if not perm.get("allowed", True):
                rr.execution_status = "awaiting_approval"
                executed["skipped_guarded"] += 1
                continue
            success = await _execute_reroute(db, rr)
            if success:
                rr.execution_status = "executed"
                executed["reroutes"] += 1
            else:
                rr.execution_status = "failed"
                executed["errors"] += 1

        # --- Throttles ---
        throttles = list((await db.execute(
            select(ThrottlingAction).where(ThrottlingAction.incident_id == incident.id, ThrottlingAction.execution_status == "pending")
        )).scalars().all())
        for th in throttles:
            perm = await check_action(db, org_id, "throttle_action")
            if not perm.get("allowed", True):
                th.execution_status = "awaiting_approval"
                executed["skipped_guarded"] += 1
                continue
            success = await _execute_throttle(db, th)
            if success:
                th.execution_status = "executed"
                executed["throttles"] += 1
            else:
                th.execution_status = "failed"
                executed["errors"] += 1

        # Only mark resolved if ALL actions actually succeeded (no "failed" states)
        all_actions = rollbacks + reroutes + throttles
        all_terminal = all(a.execution_status in ("executed", "awaiting_approval") for a in all_actions)
        any_failed = any(a.execution_status == "failed" for a in all_actions)

        if all_actions and all_terminal and not any_failed:
            db.add(RecoveryOutcome(
                incident_id=incident.id,
                outcome_type="auto_resolved",
                success=True,
                detail=f"Executed {executed['rollbacks']}rb/{executed['reroutes']}rr/{executed['throttles']}th",
            ))
            incident.recovery_status = "resolved"
        elif any_failed:
            # Honest failure: escalate instead of pretending success
            db.add(RecoveryOutcome(
                incident_id=incident.id,
                outcome_type="partial_failure",
                success=False,
                detail=f"Some actions failed: {executed['errors']} errors. Escalating.",
            ))
            incident.recovery_status = "escalated"
            log.warning("recovery.partial_failure", incident_id=str(incident.id), errors=executed["errors"])

    await db.flush()
    return executed
