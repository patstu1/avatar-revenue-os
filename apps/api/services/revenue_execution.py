"""Revenue Execution — the action engine that makes the machine DO things.

This service translates intelligence into real system actions with
3-tier governance: surface → assisted → autonomous.

Every action has: source engine, confidence, expected upside, risk score,
approval requirement, execution state, audit trail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.services.event_bus import emit_action, emit_event
from apps.api.services import revenue_maximizer as rev_max
from apps.api.services import revenue_engines_extended as rev_ext
from apps.api.services.action_confidence import compute_action_confidence
from apps.api.services.autonomy_policy import check_autonomy_grant

logger = structlog.get_logger()

# Autonomy levels
SURFACE_ONLY = "surface"     # Create action for operator review
ASSISTED = "assisted"        # Prepare action, require approval
AUTONOMOUS = "autonomous"    # Execute automatically if confidence + governance allow

# Action definitions with default autonomy levels
ACTION_REGISTRY = {
    "attach_offer_to_content": {"default_level": AUTONOMOUS, "min_confidence": 0.6},
    "create_content_for_offer": {"default_level": ASSISTED, "min_confidence": 0.5},
    "launch_packaging_test": {"default_level": ASSISTED, "min_confidence": 0.5},
    "launch_offer_test": {"default_level": ASSISTED, "min_confidence": 0.5},
    "create_upsell_path": {"default_level": ASSISTED, "min_confidence": 0.5},
    "create_bundle": {"default_level": ASSISTED, "min_confidence": 0.5},
    "promote_winning_offer": {"default_level": AUTONOMOUS, "min_confidence": 0.7},
    "suppress_losing_offer": {"default_level": AUTONOMOUS, "min_confidence": 0.7},
    "shift_monetization_mix": {"default_level": SURFACE_ONLY, "min_confidence": 0.6},
    "escalate_sponsor_opportunity": {"default_level": ASSISTED, "min_confidence": 0.4},
    "create_productization_flow": {"default_level": SURFACE_ONLY, "min_confidence": 0.5},
    "open_service_monetization": {"default_level": SURFACE_ONLY, "min_confidence": 0.5},
    "queue_cross_platform_replication": {"default_level": ASSISTED, "min_confidence": 0.6},
    "repair_broken_attribution": {"default_level": AUTONOMOUS, "min_confidence": 0.5},
    "recover_failed_webhook": {"default_level": AUTONOMOUS, "min_confidence": 0.5},
    "follow_up_unpaid_milestone": {"default_level": ASSISTED, "min_confidence": 0.4},
    "deprioritize_low_margin": {"default_level": AUTONOMOUS, "min_confidence": 0.7},
    "scale_high_yield_creator": {"default_level": ASSISTED, "min_confidence": 0.6},
    "scale_high_yield_offer": {"default_level": ASSISTED, "min_confidence": 0.6},
    "reduce_dead_channel": {"default_level": AUTONOMOUS, "min_confidence": 0.7},
    "launch_compounding_sequence": {"default_level": ASSISTED, "min_confidence": 0.5},
}


async def execute_revenue_actions(
    db: AsyncSession, org_id: uuid.UUID, brand_id: uuid.UUID,
    *, autonomy_override: Optional[str] = None,
) -> dict:
    """Master execution function: run all engines, produce actions with governance.

    Returns actions categorized by execution tier:
    - autonomous: executed immediately (logged + audited)
    - assisted: prepared, awaiting approval
    - surfaced: presented to operator for review
    """
    executed = []
    awaiting_approval = []
    surfaced = []

    # --- Gather intelligence from all engines ---
    next_actions = await rev_max.get_next_best_revenue_actions(db, brand_id, org_id)
    leaks = await rev_ext.detect_revenue_leaks(db, brand_id)
    compounding = await rev_ext.detect_compounding_opportunities(db, brand_id)
    suppressions = await rev_max.compute_suppression_targets(db, brand_id)

    # --- Process next-best actions ---
    for action_data in next_actions[:10]:
        action_type = action_data.get("action", "pursue_opportunity")
        reg = ACTION_REGISTRY.get(action_type, {"default_level": SURFACE_ONLY, "min_confidence": 0.5})
        level = autonomy_override or reg["default_level"]
        expected_value = action_data.get("expected_value", 0)
        risk_score = action_data.get("risk_score")

        # Compute confidence from real signals instead of hardcoded thresholds.
        # 4-signal model: data completeness, action history, expected value, risk.
        conf_result = await compute_action_confidence(
            db, brand_id, action_type,
            expected_value=expected_value,
            risk_score=risk_score,
        )
        confidence = conf_result["confidence"]

        result = await _create_governed_action(
            db, org_id=org_id, brand_id=brand_id,
            action_type=action_type,
            title=action_data.get("description", action_type)[:200],
            expected_value=expected_value,
            confidence=confidence,
            level=level,
            source_engine="next_best_action",
            entity_type=action_data.get("entity_type"),
            entity_id=action_data.get("entity_id"),
        )
        _categorize(result, executed, awaiting_approval, surfaced)

    # --- Process leak repairs ---
    for leak in leaks[:5]:
        result = await _create_governed_action(
            db, org_id=org_id, brand_id=brand_id,
            action_type=leak.get("action", "repair_leak"),
            title=f"Leak: {leak['leak_type']} — ${leak.get('estimated_lost', 0):.0f}",
            expected_value=leak.get("estimated_lost", 0),
            confidence=0.8,
            level=AUTONOMOUS if leak["severity"] == "high" else ASSISTED,
            source_engine="leak_detector",
        )
        _categorize(result, executed, awaiting_approval, surfaced)

    # --- Process compounding opportunities ---
    for comp in compounding[:3]:
        comp_ev = comp.get("source_revenue", 0) * comp.get("expected_uplift_pct", 10) / 100
        comp_action = comp.get("action", "launch_compounding_sequence")
        comp_conf = await compute_action_confidence(
            db, brand_id, comp_action, expected_value=comp_ev,
        )
        result = await _create_governed_action(
            db, org_id=org_id, brand_id=brand_id,
            action_type=comp_action,
            title=comp.get("description", "Compounding opportunity")[:200],
            expected_value=comp_ev,
            confidence=comp_conf["confidence"],
            level=ASSISTED,
            source_engine="compounding_engine",
        )
        _categorize(result, executed, awaiting_approval, surfaced)

    # --- Process suppressions ---
    for supp in suppressions[:3]:
        if supp["type"] != "active_suppression":
            result = await _create_governed_action(
                db, org_id=org_id, brand_id=brand_id,
                action_type="suppress_losing_offer",
                title=f"Suppress: {supp.get('name', supp.get('family_key', 'unknown'))}",
                expected_value=0,
                confidence=0.8,
                level=AUTONOMOUS,
                source_engine="suppression_engine",
            )
            _categorize(result, executed, awaiting_approval, surfaced)

    await db.flush()

    # Emit summary event
    await emit_event(
        db, domain="monetization", event_type="revenue.execution_cycle",
        summary=f"Revenue execution: {len(executed)} auto, {len(awaiting_approval)} assisted, {len(surfaced)} surfaced",
        org_id=org_id, brand_id=brand_id,
        details={"autonomous": len(executed), "assisted": len(awaiting_approval), "surfaced": len(surfaced)},
    )

    return {
        "autonomous_executed": executed,
        "awaiting_approval": awaiting_approval,
        "surfaced_for_review": surfaced,
        "total_actions": len(executed) + len(awaiting_approval) + len(surfaced),
    }


async def _create_governed_action(
    db: AsyncSession, *, org_id: uuid.UUID, brand_id: uuid.UUID,
    action_type: str, title: str, expected_value: float, confidence: float,
    level: str, source_engine: str,
    entity_type: Optional[str] = None, entity_id: Optional[str] = None,
) -> dict:
    """Create a governed action with the appropriate autonomy tier."""
    reg = ACTION_REGISTRY.get(action_type, {"default_level": SURFACE_ONLY, "min_confidence": 0.5})

    # Governance check: downgrade if confidence too low
    if confidence < reg["min_confidence"]:
        level = SURFACE_ONLY

    # Auto-promotion: if the action defaults to ASSISTED, check if the brand
    # has earned an autonomy grant for this action type. If so, promote to
    # AUTONOMOUS (within the grant's daily cap).
    was_auto_approved = False
    if level == ASSISTED:
        grant = await check_autonomy_grant(db, brand_id, action_type)
        if grant:
            level = AUTONOMOUS
            was_auto_approved = True

    action = await emit_action(
        db, org_id=org_id,
        action_type=action_type,
        title=title,
        description=f"Expected value: ${expected_value:.0f}. Confidence: {confidence:.0%}. Engine: {source_engine}.",
        category="monetization",
        priority="high" if expected_value > 200 else "medium" if expected_value > 50 else "low",
        brand_id=brand_id,
        entity_type=entity_type,
        entity_id=uuid.UUID(entity_id) if entity_id else None,
        source_module=f"revenue_execution.{source_engine}",
        action_payload={
            "autonomy_level": level,
            "confidence": confidence,
            "expected_value": expected_value,
            "source_engine": source_engine,
            "was_auto_approved": was_auto_approved,
        },
    )

    return {
        "action_id": str(action.id),
        "action_type": action_type,
        "title": title,
        "autonomy_level": level,
        "confidence": confidence,
        "expected_value": expected_value,
        "source_engine": source_engine,
    }


def _categorize(result, executed, awaiting, surfaced):
    level = result["autonomy_level"]
    if level == AUTONOMOUS:
        executed.append(result)
    elif level == ASSISTED:
        awaiting.append(result)
    else:
        surfaced.append(result)
