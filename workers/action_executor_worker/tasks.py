"""Action Executor Worker — the bridge between recommendations and real mutations.

Reads pending actions from every intelligence module, passes each through the
autonomous execution gate, and dispatches real downstream mutations:
  - Deactivate offers (kill ledger, offer lifecycle)
  - Suppress content (suppression engine)
  - Execute recovery actions
  - Enforce capacity throttle on queues
  - Create reputation → recovery cross-links
  - Advance experiment outcome actions
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog

from workers.base_task import TrackedTask
from workers.celery_app import app

logger = structlog.get_logger()


def _evaluate_gate(session, brand_id: uuid.UUID, loop_step: str, confidence: float, cost=None) -> dict:
    """Check the autonomous execution policy gate for a brand."""
    from packages.db.models.autonomous_execution import AutomationExecutionPolicy
    from packages.scoring.autonomous_execution_engine import evaluate_execution_gate

    policy = session.query(AutomationExecutionPolicy).filter(
        AutomationExecutionPolicy.brand_id == brand_id,
        AutomationExecutionPolicy.is_active.is_(True),
    ).first()

    if not policy:
        return {"decision": "require_approval", "reasons": ["no_active_policy"]}

    return evaluate_execution_gate(
        operating_mode=policy.operating_mode,
        kill_switch_engaged=policy.kill_switch_engaged,
        loop_step=loop_step,
        confidence=confidence,
        estimated_cost_usd=cost,
        min_confidence_auto_execute=policy.min_confidence_auto_execute,
        min_confidence_publish=policy.min_confidence_publish,
        max_auto_cost_usd_per_action=policy.max_auto_cost_usd_per_action,
        require_approval_above_cost_usd=policy.require_approval_above_cost_usd,
    )


def _record_run(session, brand_id, loop_step, status, confidence, input_payload, output_payload=None):
    """Persist an execution run record for audit trail."""
    from packages.db.models.autonomous_execution import AutomationExecutionPolicy, AutomationExecutionRun

    policy = session.query(AutomationExecutionPolicy).filter(
        AutomationExecutionPolicy.brand_id == brand_id,
        AutomationExecutionPolicy.is_active.is_(True),
    ).first()

    snap = {}
    if policy:
        snap = {
            "operating_mode": policy.operating_mode,
            "min_confidence_auto_execute": policy.min_confidence_auto_execute,
            "kill_switch_engaged": policy.kill_switch_engaged,
        }

    run = AutomationExecutionRun(
        brand_id=brand_id,
        loop_step=loop_step,
        status=status,
        confidence_score=float(confidence),
        policy_snapshot_json=snap,
        input_payload_json=input_payload or {},
        output_payload_json=output_payload or {},
    )
    session.add(run)
    return run


# ─────────────────────────────────────────────────────────────────────────────
# 1. Kill Ledger → Deactivate offers, accounts, content
# ─────────────────────────────────────────────────────────────────────────────

@app.task(base=TrackedTask, bind=True, name="workers.action_executor_worker.tasks.execute_kill_ledger_actions")
def execute_kill_ledger_actions(self) -> dict:
    """Read active KillLedgerEntry rows that haven't been executed and deactivate targets."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.accounts import CreatorAccount
    from packages.db.models.content import ContentItem
    from packages.db.models.kill_ledger import KillLedgerEntry
    from packages.db.models.offers import Offer
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    executed = 0
    skipped = 0

    with Session(engine) as session:
        entries = session.execute(
            select(KillLedgerEntry).where(
                KillLedgerEntry.is_active.is_(True),
                KillLedgerEntry.killed_at.is_(None),
            ).limit(100)
        ).scalars().all()

        for entry in entries:
            gate = _evaluate_gate(session, entry.brand_id, "suppress_losers", entry.confidence_score or 0.6)

            if gate["decision"] not in ("allow",):
                _record_run(
                    session, entry.brand_id, "suppress_losers", "blocked",
                    entry.confidence_score or 0.6,
                    {"kill_entry_id": str(entry.id), "scope_type": entry.scope_type},
                    {"gate_decision": gate["decision"], "reasons": gate.get("reasons", [])},
                )
                skipped += 1
                continue

            target_deactivated = False
            if entry.scope_type == "offer" and entry.scope_id:
                offer = session.get(Offer, entry.scope_id)
                if offer and offer.is_active:
                    offer.is_active = False
                    target_deactivated = True
            elif entry.scope_type == "account" and entry.scope_id:
                account = session.get(CreatorAccount, entry.scope_id)
                if account and account.is_active:
                    account.is_active = False
                    target_deactivated = True
            elif entry.scope_type == "content" and entry.scope_id:
                content = session.get(ContentItem, entry.scope_id)
                if content and content.status not in ("suppressed", "killed"):
                    content.status = "suppressed"
                    target_deactivated = True

            entry.killed_at = datetime.now(timezone.utc)

            _record_run(
                session, entry.brand_id, "suppress_losers", "completed",
                entry.confidence_score or 0.6,
                {"kill_entry_id": str(entry.id), "scope_type": entry.scope_type, "scope_id": str(entry.scope_id)},
                {"deactivated": target_deactivated},
            )
            executed += 1

        session.commit()

    return {"executed": executed, "skipped": skipped, "total_entries": len(entries)}


# ─────────────────────────────────────────────────────────────────────────────
# 2. Offer Lifecycle → Deactivate sunset/killed offers
# ─────────────────────────────────────────────────────────────────────────────

@app.task(base=TrackedTask, bind=True, name="workers.action_executor_worker.tasks.execute_offer_lifecycle_transitions")
def execute_offer_lifecycle_transitions(self) -> dict:
    """When offers transition to sunset/killed, deactivate them in the offers table."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.offer_lifecycle import OfferLifecycleEvent
    from packages.db.models.offers import Offer
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    deactivated = 0

    with Session(engine) as session:
        events = session.execute(
            select(OfferLifecycleEvent).where(
                OfferLifecycleEvent.to_state.in_(["sunset", "killed", "deprecated"]),
            ).limit(200)
        ).scalars().all()

        processed_offers: set = set()
        for event in events:
            if not event.offer_id or event.offer_id in processed_offers:
                continue

            offer = session.get(Offer, event.offer_id)
            if not offer or not offer.is_active:
                continue

            gate = _evaluate_gate(session, event.brand_id, "suppress_losers", 0.75)
            if gate["decision"] not in ("allow",):
                continue

            offer.is_active = False
            processed_offers.add(event.offer_id)
            deactivated += 1

            _record_run(
                session, event.brand_id, "suppress_losers", "completed", 0.75,
                {"event_id": str(event.id), "to_state": event.to_state, "offer_id": str(event.offer_id)},
                {"deactivated": True},
            )

        session.commit()

    return {"events_scanned": len(events), "offers_deactivated": deactivated}


# ─────────────────────────────────────────────────────────────────────────────
# 3. Recovery Actions → Execute auto-mode actions
# ─────────────────────────────────────────────────────────────────────────────

@app.task(base=TrackedTask, bind=True, name="workers.action_executor_worker.tasks.execute_recovery_actions")
def execute_recovery_actions(self) -> dict:
    """Execute pending recovery actions where action_mode is 'auto'."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.recovery import RecoveryAction, RecoveryIncident
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    executed = 0

    with Session(engine) as session:
        actions = session.execute(
            select(RecoveryAction).where(
                RecoveryAction.executed.is_(False),
                RecoveryAction.action_mode == "auto",
            ).limit(50)
        ).scalars().all()

        for action in actions:
            gate = _evaluate_gate(session, action.brand_id, "self_heal", action.confidence_score or 0.5)

            if gate["decision"] not in ("allow",):
                _record_run(
                    session, action.brand_id, "self_heal", "blocked",
                    action.confidence_score or 0.5,
                    {"action_id": str(action.id), "action_type": action.action_type},
                    {"gate_decision": gate["decision"]},
                )
                continue

            action.executed = True
            action.result_json = {
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "executor": "action_executor_worker",
                "gate_decision": gate["decision"],
            }

            incident = session.get(RecoveryIncident, action.incident_id) if action.incident_id else None
            if incident:
                incident.automatic_action_taken = action.action_type

            _record_run(
                session, action.brand_id, "self_heal", "completed",
                action.confidence_score or 0.5,
                {"action_id": str(action.id), "action_type": action.action_type},
                {"executed": True},
            )
            executed += 1

        session.commit()

    return {"actions_processed": len(actions), "executed": executed}


# ─────────────────────────────────────────────────────────────────────────────
# 4. Capacity Throttle → Apply rate limits
# ─────────────────────────────────────────────────────────────────────────────

@app.task(base=TrackedTask, bind=True, name="workers.action_executor_worker.tasks.enforce_capacity_throttle")
def enforce_capacity_throttle(self) -> dict:
    """Read capacity recommendations and log throttle enforcement decisions."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.capacity import CapacityReport
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    throttles_applied = 0

    with Session(engine) as session:
        reports = session.execute(
            select(CapacityReport).where(
                CapacityReport.is_active.is_(True),
            ).order_by(CapacityReport.created_at.desc()).limit(50)
        ).scalars().all()

        seen_brands: set = set()
        for report in reports:
            if report.brand_id in seen_brands:
                continue
            seen_brands.add(report.brand_id)

            throttle = report.recommended_throttle
            if throttle is not None and throttle < 1.0:
                app.control.rate_limit(
                    "workers.generation_worker.generate_script",
                    f"{max(1, int(throttle * 10))}/m",
                )
                _record_run(
                    session, report.brand_id, "ramp_output", "completed", 0.8,
                    {"capacity_report_id": str(report.id), "recommended_throttle": throttle},
                    {"throttle_target": throttle, "applied": True},
                )
                throttles_applied += 1

        session.commit()

    return {"brands_evaluated": len(seen_brands), "throttles_applied": throttles_applied}


# ─────────────────────────────────────────────────────────────────────────────
# 5. Reputation → Recovery cross-link
# ─────────────────────────────────────────────────────────────────────────────

@app.task(base=TrackedTask, bind=True, name="workers.action_executor_worker.tasks.link_reputation_to_recovery")
def link_reputation_to_recovery(self) -> dict:
    """Create RecoveryIncident from high-severity ReputationReport rows."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.recovery import RecoveryIncident
    from packages.db.models.reputation import ReputationReport
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    incidents_created = 0

    with Session(engine) as session:
        reports = session.execute(
            select(ReputationReport).where(
                ReputationReport.is_active.is_(True),
                ReputationReport.reputation_risk_score >= 0.75,
            ).limit(50)
        ).scalars().all()

        for report in reports:
            existing = session.execute(
                select(RecoveryIncident.id).where(
                    RecoveryIncident.brand_id == report.brand_id,
                    RecoveryIncident.incident_type == "reputation_risk",
                    RecoveryIncident.scope_type == report.scope_type,
                    RecoveryIncident.status == "open",
                ).limit(1)
            ).scalar_one_or_none()
            if existing:
                continue

            incident = RecoveryIncident(
                brand_id=report.brand_id,
                incident_type="reputation_risk",
                severity="critical" if report.reputation_risk_score >= 0.9 else "high",
                scope_type=report.scope_type,
                scope_id=report.scope_id,
                detected_at=datetime.now(timezone.utc),
                explanation_json={"source": "reputation_monitor", "risk_score": report.reputation_risk_score},
                recommended_recovery_action="review_and_mitigate",
                automatic_action_taken="recovery_incident_created_from_reputation",
            )
            session.add(incident)
            incidents_created += 1

        session.commit()

    return {"reports_evaluated": len(reports), "incidents_created": incidents_created}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Experiment Outcome Actions → Advance through gate
# ─────────────────────────────────────────────────────────────────────────────

@app.task(base=TrackedTask, bind=True, name="workers.action_executor_worker.tasks.advance_experiment_outcome_actions")
def advance_experiment_outcome_actions(self) -> dict:
    """Process pending experiment outcome actions through the execution gate."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.experiment_decisions import ExperimentOutcomeAction
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    advanced = 0
    blocked = 0

    with Session(engine) as session:
        actions = session.execute(
            select(ExperimentOutcomeAction).where(
                ExperimentOutcomeAction.execution_status == "pending_operator",
            ).limit(100)
        ).scalars().all()

        for action in actions:
            step = "scale_winners" if action.action_kind == "promote" else "suppress_losers"
            gate = _evaluate_gate(session, action.brand_id, step, 0.65)

            if gate["decision"] == "allow":
                action.execution_status = "auto_executed"
                _record_run(
                    session, action.brand_id, step, "completed", 0.65,
                    {"action_id": str(action.id), "action_kind": action.action_kind},
                    {"gate": "allow", "executed": True},
                )
                advanced += 1
            else:
                action.execution_status = "awaiting_approval"
                blocked += 1

        session.commit()

    return {"total_actions": len(actions), "auto_executed": advanced, "awaiting_approval": blocked}


# ─────────────────────────────────────────────────────────────────────────────
# 7. Brain Decisions → Downstream Actions
# ─────────────────────────────────────────────────────────────────────────────

@app.task(base=TrackedTask, bind=True, name="workers.action_executor_worker.tasks.execute_brain_decisions")
def execute_brain_decisions(self) -> dict:
    """Read brain decisions with downstream_action set and create executable artifacts."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from packages.db.models.brain_phase_b import BrainDecision
    from packages.db.models.scale_alerts import OperatorAlert
    from packages.db.session import get_sync_engine

    engine = get_sync_engine()
    processed = 0
    created = 0
    skipped = 0

    with Session(engine) as session:
        decisions = session.execute(
            select(BrainDecision).where(
                BrainDecision.is_active.is_(True),
                BrainDecision.downstream_action.isnot(None),
                BrainDecision.downstream_action != "",
            )
        ).scalars().all()

        for d in decisions:
            processed += 1
            gate = _evaluate_gate(session, d.brand_id, "brain_decision", d.confidence)

            if gate["decision"] in ("auto_execute", "execute"):
                session.add(OperatorAlert(
                    brand_id=d.brand_id,
                    alert_type=f"brain_decision_{d.decision_class}",
                    title=f"Brain decision: {d.selected_action[:200]}",
                    summary=d.objective[:500],
                    explanation=d.explanation,
                    recommended_action=d.downstream_action[:500] if d.downstream_action else "",
                    confidence=d.confidence,
                    urgency=min(100.0, d.expected_upside / 10.0) if d.expected_upside else 50.0,
                    expected_upside=d.expected_upside,
                    expected_cost=d.expected_cost,
                ))
                d.is_active = False
                created += 1
                _record_run(session, d.brand_id, "brain_decision", "executed", d.confidence,
                            {"decision_class": d.decision_class, "objective": d.objective},
                            {"action": d.downstream_action})
            else:
                skipped += 1
                _record_run(session, d.brand_id, "brain_decision", "awaiting_approval", d.confidence,
                            {"decision_class": d.decision_class}, {"gate": gate})

        session.commit()

    return {"decisions_processed": processed, "actions_created": created, "awaiting_approval": skipped}
