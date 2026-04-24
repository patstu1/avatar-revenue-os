"""Phase C execution lifecycle — advance status, dispatch executors, notify operators.

Closes the loop: proposed → operator_review → approved → executing → completed (or rejected).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from packages.db.models.autonomous_phase_c import (
    FunnelExecutionRun,
    PaidOperatorDecision,
    PaidOperatorRun,
    RecoveryEscalation,
    RetentionAutomationAction,
    SelfHealingAction,
    SponsorAutonomousAction,
)
from packages.executors.phase_c_executors import get_executor

logger = structlog.get_logger()

VALID_TRANSITIONS = {
    "proposed": {"operator_review", "approved", "rejected"},
    "active": {"operator_review", "approved", "rejected"},  # run_status alias
    "operator_review": {"approved", "rejected"},
    "approved": {"executing"},
    "executing": {"completed", "failed"},
    "failed": {"approved", "rejected"},
}

_MODEL_MAP: dict[str, tuple] = {
    "funnel_execution": (FunnelExecutionRun, "funnel"),
    "paid_operator_run": (PaidOperatorRun, None),
    "paid_operator_decision": (PaidOperatorDecision, "paid_decision"),
    "sponsor_autonomy": (SponsorAutonomousAction, "sponsor"),
    "retention_autonomy": (RetentionAutomationAction, "retention"),
    "recovery_escalation": (RecoveryEscalation, None),
    "self_healing": (SelfHealingAction, "self_healing"),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_transition(current: str, target: str) -> None:
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(
            f"Invalid transition: '{current}' → '{target}'. "
            f"Allowed: {sorted(allowed) if allowed else 'none (terminal state)'}."
        )


# ---------------------------------------------------------------------------
# Generic status advancement
# ---------------------------------------------------------------------------

async def advance_execution_status(
    db: AsyncSession,
    module: str,
    record_id: uuid.UUID,
    target_status: str,
    operator_notes: Optional[str] = None,
) -> dict[str, Any]:
    if module not in _MODEL_MAP:
        raise ValueError(f"Unknown module '{module}'. Valid: {sorted(_MODEL_MAP)}")

    model_cls, executor_key = _MODEL_MAP[module]
    record = (await db.execute(
        select(model_cls).where(model_cls.id == record_id)
    )).scalar_one_or_none()

    if not record:
        raise ValueError(f"{module} record {record_id} not found")

    current = getattr(record, "execution_status", None) or getattr(record, "run_status", None) or getattr(record, "status", "proposed")
    _validate_transition(current, target_status)

    # Apply status
    if hasattr(record, "execution_status"):
        record.execution_status = target_status
    elif hasattr(record, "run_status"):
        record.run_status = target_status
    elif hasattr(record, "status"):
        record.status = target_status

    execution_notes = operator_notes or ""

    # If transitioning to 'executing', dispatch the executor
    if target_status == "executing" and executor_key:
        try:
            executor = get_executor(executor_key)
            row_dict = _record_to_dict(record)
            success, notes = executor.execute(row_dict)
            execution_notes = notes
            if success:
                # Auto-advance to completed
                if hasattr(record, "execution_status"):
                    record.execution_status = "completed"
                elif hasattr(record, "run_status"):
                    record.run_status = "completed"
                target_status = "completed"
            else:
                if hasattr(record, "execution_status"):
                    record.execution_status = "failed"
                elif hasattr(record, "run_status"):
                    record.run_status = "failed"
                target_status = "failed"
        except Exception as exc:
            logger.exception("lifecycle.execute.error", module=module, record_id=str(record_id))
            if hasattr(record, "execution_status"):
                record.execution_status = "failed"
            elif hasattr(record, "run_status"):
                record.run_status = "failed"
            target_status = "failed"
            execution_notes = f"Execution error: {exc}"

    # For RecoveryEscalation, handle resolved_at
    if module == "recovery_escalation" and target_status == "completed":
        if hasattr(record, "resolved_at"):
            record.resolved_at = _utc_now()
        if hasattr(record, "status"):
            record.status = "resolved"

    await db.flush()

    logger.info("lifecycle.status_advanced", module=module,
                record_id=str(record_id), new_status=target_status)

    return {
        "id": str(record_id),
        "module": module,
        "previous_status": current,
        "new_status": target_status,
        "execution_notes": execution_notes,
    }


# ---------------------------------------------------------------------------
# Batch execute approved actions
# ---------------------------------------------------------------------------

async def execute_approved_actions(db: AsyncSession, brand_id: uuid.UUID) -> dict[str, Any]:
    """Find all approved actions for a brand and execute them. Used by Celery worker."""
    results: dict[str, list] = {}

    for module, (model_cls, executor_key) in _MODEL_MAP.items():
        if not executor_key:
            continue

        status_col = _get_status_col(model_cls)
        if not status_col:
            continue

        rows = list((await db.execute(
            select(model_cls).where(
                model_cls.brand_id == brand_id,
                status_col == "approved",
                model_cls.is_active.is_(True),
            )
        )).scalars().all())

        executed = []
        for record in rows:
            try:
                result = await advance_execution_status(
                    db, module, record.id, "executing"
                )
                executed.append(result)
            except Exception as exc:
                logger.exception("lifecycle.batch_execute.error",
                                 module=module, record_id=str(record.id))
                executed.append({
                    "id": str(record.id), "module": module,
                    "new_status": "failed", "execution_notes": str(exc),
                })

        if executed:
            results[module] = executed

    await db.flush()
    total = sum(len(v) for v in results.values())
    return {"brand_id": str(brand_id), "actions_executed": total, "details": results}


# ---------------------------------------------------------------------------
# Paid performance ingestion
# ---------------------------------------------------------------------------

async def ingest_paid_performance(
    db: AsyncSession,
    paid_operator_run_id: uuid.UUID,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Ingest real ad-platform metrics for a paid operator run and recompute decision."""
    from packages.scoring.autonomous_phase_c_engine import compute_paid_operator_decision

    run = (await db.execute(
        select(PaidOperatorRun).where(PaidOperatorRun.id == paid_operator_run_id)
    )).scalar_one_or_none()
    if not run:
        raise ValueError(f"PaidOperatorRun {paid_operator_run_id} not found")

    # Deactivate old decisions for this run
    await db.execute(
        update(PaidOperatorDecision).where(
            PaidOperatorDecision.paid_operator_run_id == paid_operator_run_id,
            PaidOperatorDecision.is_active.is_(True),
        ).values(is_active=False)
    )

    perf = {
        "cpa_actual": float(metrics.get("cpa_actual", 0)),
        "cpa_target": float(metrics.get("cpa_target", 55)),
        "spend_7d": float(metrics.get("spend_7d", 0)),
        "conversions_7d": int(metrics.get("conversions_7d", 0)),
        "roi_actual": float(metrics.get("roi_actual", 0)),
        "_data_source": "real_ad_platform",
    }

    dec = compute_paid_operator_decision({"run_id": str(run.id)}, perf)
    dec["explanation"] = f"[data_source=real_ad_platform] {dec['explanation']}"

    new_decision = PaidOperatorDecision(
        brand_id=run.brand_id,
        paid_operator_run_id=run.id,
        decision_type=dec["decision_type"],
        budget_band=dec["budget_band"],
        expected_cac=dec["expected_cac"],
        expected_roi=dec["expected_roi"],
        execution_mode=dec["execution_mode"],
        confidence=dec["confidence"],
        explanation=dec["explanation"],
        execution_status="proposed",
    )
    db.add(new_decision)
    await db.flush()

    return {
        "paid_operator_run_id": str(run.id),
        "decision_id": str(new_decision.id),
        "decision_type": dec["decision_type"],
        "data_source": "real_ad_platform",
        "confidence": dec["confidence"],
    }


# ---------------------------------------------------------------------------
# Operator notification dispatch
# ---------------------------------------------------------------------------

async def notify_operator_review_items(
    db: AsyncSession, brand_id: uuid.UUID,
) -> dict[str, Any]:
    """Collect all items in operator_review status and dispatch notifications."""
    from packages.notifications.adapters import NotificationPayload

    items: list[dict] = []

    for module, (model_cls, _) in _MODEL_MAP.items():
        status_col = _get_status_col(model_cls)
        if not status_col:
            continue

        rows = list((await db.execute(
            select(model_cls).where(
                model_cls.brand_id == brand_id,
                status_col == "operator_review",
                model_cls.is_active.is_(True),
            )
        )).scalars().all())

        for r in rows:
            items.append({
                "module": module,
                "id": str(r.id),
                "explanation": getattr(r, "explanation", ""),
            })

    if not items:
        return {"brand_id": str(brand_id), "notifications_sent": 0, "items": []}

    # Create notification payload
    summary = f"{len(items)} Phase C action(s) require operator review"
    payload = NotificationPayload(
        title="Phase C Operator Review Required",
        summary=summary,
        urgency=0.7,
        alert_type="phase_c_operator_review",
        brand_id=str(brand_id),
        detail_url=f"/dashboard/command-center?brand={brand_id}&tab=phase-c",
    )

    # Log notification (in-app always delivered)
    logger.info("lifecycle.operator_notification", brand_id=str(brand_id),
                items_count=len(items), payload=payload.to_dict())

    return {
        "brand_id": str(brand_id),
        "notifications_sent": len(items),
        "items": items,
        "notification_payload": payload.to_dict(),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_status_col(model_cls):
    if hasattr(model_cls, "execution_status"):
        return model_cls.execution_status
    if hasattr(model_cls, "run_status"):
        return model_cls.run_status
    if hasattr(model_cls, "status"):
        return model_cls.status
    return None


def _record_to_dict(record) -> dict[str, Any]:
    """Convert an ORM record to a dict for the executor."""
    d: dict[str, Any] = {}
    for col in record.__table__.columns:
        val = getattr(record, col.name, None)
        if isinstance(val, uuid.UUID):
            val = str(val)
        elif isinstance(val, datetime):
            val = val.isoformat()
        d[col.name] = val
    return d
