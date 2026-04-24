"""Deterministic gate evaluation for autonomous execution (no ML)."""
from __future__ import annotations

from typing import Any

# Canonical 14-step loop keys (control plane references these; step workers use same names).
AUTONOMOUS_LOOP_STEPS: tuple[str, ...] = (
    "scan_opportunities",
    "choose_account_platform_niche",
    "generate_content",
    "platform_variants",
    "warm_accounts",
    "ramp_output",
    "publish_queue",
    "monetization_route",
    "follow_up_trigger",
    "monitor_performance",
    "scale_winners",
    "suppress_losers",
    "self_heal",
    "operator_notify_if_blocked",
)

PUBLISH_RELATED_STEPS: frozenset[str] = frozenset(
    {"publish_queue", "platform_variants", "ramp_output", "warm_accounts"}
)


def evaluate_execution_gate(
    *,
    operating_mode: str,
    kill_switch_engaged: bool,
    loop_step: str,
    confidence: float,
    estimated_cost_usd: float | None,
    min_confidence_auto_execute: float,
    min_confidence_publish: float,
    max_auto_cost_usd_per_action: float | None,
    require_approval_above_cost_usd: float | None,
) -> dict[str, Any]:
    """
    Returns a decision dict:
    - decision: allow | require_approval | blocked | manual_only
    - reasons: list[str]
    - guardrail: optional dict (thresholds applied)
    """
    reasons: list[str] = []
    conf = max(0.0, min(1.0, float(confidence)))
    cost = float(estimated_cost_usd) if estimated_cost_usd is not None else None

    if kill_switch_engaged:
        return {
            "decision": "blocked",
            "reasons": ["kill_switch_engaged"],
            "guardrail": {"kill_switch": True},
        }

    if operating_mode == "escalation_only":
        return {
            "decision": "manual_only",
            "reasons": ["operating_mode_is_escalation_only"],
            "guardrail": {"mode": operating_mode},
        }

    thresh_exec = float(min_confidence_auto_execute)
    thresh_pub = float(min_confidence_publish)
    step_publish_sensitive = loop_step in PUBLISH_RELATED_STEPS or loop_step == "publish_queue"
    effective_thresh = thresh_pub if step_publish_sensitive else thresh_exec

    if conf < effective_thresh:
        reasons.append(f"confidence_below_threshold:{conf:.3f}<{effective_thresh:.3f}")

    if operating_mode == "guarded_autonomous":
        if cost is not None and require_approval_above_cost_usd is not None:
            if cost > float(require_approval_above_cost_usd):
                reasons.append(f"cost_above_guarded_cap:{cost}>{require_approval_above_cost_usd}")

    if cost is not None and max_auto_cost_usd_per_action is not None:
        if cost > float(max_auto_cost_usd_per_action):
            reasons.append(f"cost_above_hard_cap:{cost}>{max_auto_cost_usd_per_action}")

    if reasons:
        if any("hard_cap" in r for r in reasons):
            return {
                "decision": "blocked",
                "reasons": reasons,
                "guardrail": {
                    "effective_threshold": effective_thresh,
                    "confidence": conf,
                    "cost": cost,
                },
            }
        return {
            "decision": "require_approval",
            "reasons": reasons,
            "guardrail": {
                "effective_threshold": effective_thresh,
                "confidence": conf,
                "cost": cost,
            },
        }

    if operating_mode == "fully_autonomous":
        return {
            "decision": "allow",
            "reasons": [],
            "guardrail": {"effective_threshold": effective_thresh, "confidence": conf, "cost": cost},
        }

    # guarded_autonomous with no blocking reasons
    return {
        "decision": "allow",
        "reasons": [],
        "guardrail": {"effective_threshold": effective_thresh, "confidence": conf, "cost": cost},
    }
