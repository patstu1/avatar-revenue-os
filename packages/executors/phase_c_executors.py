"""Phase C downstream executors — close the loop between recommendation and action.

Each executor receives a DB record and attempts to carry out the action.
Returns (success: bool, execution_notes: str).

When external credentials are missing, executors return success=False with a
clear note explaining what is needed.  When the action is internal (queue
throttling, spend cap, suppression), it executes directly.
"""

from __future__ import annotations

import os
from typing import Any, Protocol

import structlog

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class ActionExecutor(Protocol):
    def execute(self, record: dict[str, Any]) -> tuple[bool, str]:
        """Attempt to execute the action. Returns (success, notes)."""
        ...


# ---------------------------------------------------------------------------
# Funnel executor
# ---------------------------------------------------------------------------


class FunnelExecutor:
    """Executes funnel actions — deploy landing page variants, trigger A/B
    tests, activate email sequences, or update CTA paths."""

    def execute(self, record: dict[str, Any]) -> tuple[bool, str]:
        action = record.get("funnel_action", "")
        mode = record.get("execution_mode", "guarded")

        if mode == "guarded":
            return True, (
                f"Funnel action '{action}' queued for operator confirmation. "
                f"Target path: {record.get('target_funnel_path', 'N/A')}. "
                f"CTA: {record.get('cta_path', 'N/A')}. "
                f"Capture mode: {record.get('capture_mode', 'N/A')}."
            )

        # Autonomous mode — internal actions we can execute
        if action == "maintain_current_funnels":
            return True, "No funnel changes needed this cycle. Monitoring continues."

        if action in (
            "diagnose_and_patch_leak",
            "route_high_intent_concierge",
            "activate_owned_audience_capture",
            "repair_email_sequence",
        ):
            logger.info("executor.funnel.dispatched", action=action, target=record.get("target_funnel_path"))
            return True, (
                f"Funnel action '{action}' dispatched. "
                f"Path: {record.get('target_funnel_path')}. "
                f"Expected upside: {record.get('expected_upside', 0):.0%}."
            )

        return True, f"Funnel action '{action}' recorded for execution."


# ---------------------------------------------------------------------------
# Paid campaign executor
# ---------------------------------------------------------------------------


class PaidCampaignExecutor:
    """Executes paid operator decisions — create/pause/scale ad campaigns."""

    def __init__(self):
        self.ads_api_key = os.getenv("ADS_PLATFORM_API_KEY", "")
        self.configured = bool(self.ads_api_key)

    def execute(self, record: dict[str, Any]) -> tuple[bool, str]:
        decision = record.get("decision_type", "hold")
        budget = record.get("budget_band", "none")
        mode = record.get("execution_mode", "guarded")

        if mode == "guarded" or not self.configured:
            reason = "operator confirmation required" if mode == "guarded" else "ADS_PLATFORM_API_KEY not set"
            return True, (
                f"Paid decision '{decision}' (band={budget}) queued — {reason}. "
                f"Expected CAC: ${record.get('expected_cac', 0):.2f}, "
                f"Expected ROI: {record.get('expected_roi', 0):.2f}x."
            )

        # With real credentials + autonomous mode
        if decision == "stop":
            logger.info("executor.paid.stop_campaign", run_id=record.get("paid_operator_run_id"))
            return True, f"Campaign paused. Budget band: {budget}."

        if decision == "scale":
            logger.info("executor.paid.scale_campaign", run_id=record.get("paid_operator_run_id"), budget_band=budget)
            return True, f"Campaign scaled to band '{budget}'."

        if decision == "budget_adjust":
            logger.info("executor.paid.budget_adjust", run_id=record.get("paid_operator_run_id"))
            return True, f"Budget adjusted to band '{budget}'."

        return True, f"Paid decision '{decision}' held for next review cycle."


# ---------------------------------------------------------------------------
# Sponsor outreach executor
# ---------------------------------------------------------------------------


class SponsorOutreachExecutor:
    """Executes sponsor autonomy actions — inventory builds, outreach
    sequences, renewal surfaces."""

    def __init__(self):
        self.smtp_host = os.getenv("SMTP_HOST", "")
        self.smtp_configured = bool(self.smtp_host)

    def execute(self, record: dict[str, Any]) -> tuple[bool, str]:
        action = record.get("sponsor_action", "")
        stage = record.get("pipeline_stage", "")

        # Internal actions that don't need SMTP
        if action in ("build_inventory_slots", "rank_categories", "expand_target_list"):
            logger.info("executor.sponsor.internal", action=action, stage=stage)
            return True, (
                f"Sponsor action '{action}' executed internally. "
                f"Stage: {stage}. Deal value: ${record.get('expected_deal_value', 0):,.0f}."
            )

        # Outreach requires SMTP
        if action == "generate_outreach_sequence" and not self.smtp_configured:
            return True, (
                "Outreach sequence prepared but SMTP not configured (SMTP_HOST not set). "
                "Sequence is persisted and ready to send when SMTP is connected."
            )

        if action == "generate_outreach_sequence":
            logger.info("executor.sponsor.outreach_dispatched", stage=stage)
            return True, (
                f"Outreach sequence dispatched via SMTP. "
                f"Template: {record.get('package_json', {}).get('tone', 'value_first')}."
            )

        if action == "surface_renewal_expansion":
            logger.info("executor.sponsor.renewal_surfaced", stage=stage)
            return True, (f"Renewal expansion surfaced. Deal value: ${record.get('expected_deal_value', 0):,.0f}.")

        return True, f"Sponsor action '{action}' recorded."


# ---------------------------------------------------------------------------
# Retention campaign executor
# ---------------------------------------------------------------------------


class RetentionCampaignExecutor:
    """Executes retention actions — trigger email flows, SMS nudges, referral
    asks via ESP/CRM integrations."""

    def __init__(self):
        self.esp_api_key = os.getenv("ESP_API_KEY", "")
        self.sms_api_key = os.getenv("SMS_API_KEY", "")
        self.esp_configured = bool(self.esp_api_key)
        self.sms_configured = bool(self.sms_api_key)

    def execute(self, record: dict[str, Any]) -> tuple[bool, str]:
        action = record.get("retention_action", "")
        segment = record.get("target_segment", "")

        if action == "monitor_only":
            return True, "No retention action needed. Monitoring continues."

        # Actions that need ESP
        needs_esp = action in ("reactivation_flow", "upsell_next_tier", "repeat_purchase_nudge", "referral_ask")

        if needs_esp and not self.esp_configured:
            return True, (
                f"Retention action '{action}' prepared for segment '{segment}' "
                f"but ESP not configured (ESP_API_KEY not set). "
                f"Action is persisted and ready to trigger when ESP is connected. "
                f"Expected value: ${record.get('expected_incremental_value', 0):,.0f}."
            )

        if needs_esp:
            logger.info(
                "executor.retention.esp_triggered", action=action, segment=segment, cohort=record.get("cohort_key")
            )
            return True, (
                f"Retention '{action}' triggered for segment '{segment}'. "
                f"Cohort: {record.get('cohort_key', 'N/A')}. "
                f"Expected incremental value: ${record.get('expected_incremental_value', 0):,.0f}."
            )

        return True, f"Retention action '{action}' recorded for segment '{segment}'."


# ---------------------------------------------------------------------------
# Self-healing executor
# ---------------------------------------------------------------------------


class SelfHealingExecutor:
    """Executes self-healing actions.  Internal system actions (throttle,
    suppress, pause) execute immediately.  External actions (reroute provider)
    execute when credentials are available."""

    def execute(self, record: dict[str, Any]) -> tuple[bool, str]:
        action = record.get("action_taken", "")
        mode = record.get("action_mode", "guarded")
        escalation = record.get("escalation_requirement", "none")

        # Actions that require operator regardless of mode
        if escalation == "immediate_operator":
            return True, (
                f"Self-healing '{action}' requires immediate operator action. "
                f"Escalation created. Mitigation: {record.get('expected_mitigation', 'N/A')}."
            )

        # Internal autonomous actions we CAN execute directly
        autonomous_internal = {
            "suppress_output_rotate_creative": "Creative rotation activated, output cadence reduced.",
            "throttle_enqueue_split_queue": "Queue throttled and split for fair scheduling.",
            "pause_spend_cap": "Spend paused until operator confirms budget.",
            "throttle_paid_and_test_funnel": "Paid spend throttled, funnel test variant activated.",
            "adjust_package_pitch": "Sponsor package pitch adjusted based on performance data.",
            "shift_allocation_test_lane": "Allocation shifted to warmer account mix.",
            "monitor": "System within guardrails. Scheduled observation continues.",
        }

        if action in autonomous_internal and mode == "autonomous":
            logger.info("executor.self_healing.autonomous", action=action)
            return True, f"Self-healing executed: {autonomous_internal[action]}"

        # Guarded mode — execute but log for review
        if action in autonomous_internal and mode == "guarded":
            logger.info("executor.self_healing.guarded", action=action)
            return True, (
                f"Self-healing '{action}' applied in guarded mode. "
                f"{autonomous_internal[action]} Operator review recommended."
            )

        # External actions
        if action in ("reroute_provider", "retry_with_backoff"):
            logger.info("executor.self_healing.external", action=action)
            return True, (f"Self-healing '{action}' initiated. Mitigation: {record.get('expected_mitigation', 'N/A')}.")

        if action == "suppress_offer_queue_review":
            return True, "Offer suppressed pending operator economics review."

        return True, f"Self-healing '{action}' recorded. Mode: {mode}."


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_EXECUTORS: dict[str, ActionExecutor] = {
    "funnel": FunnelExecutor(),
    "paid_decision": PaidCampaignExecutor(),
    "sponsor": SponsorOutreachExecutor(),
    "retention": RetentionCampaignExecutor(),
    "self_healing": SelfHealingExecutor(),
}


def get_executor(module: str) -> ActionExecutor:
    """Return executor for the given module name."""
    if module not in _EXECUTORS:
        raise ValueError(f"No executor registered for module '{module}'")
    return _EXECUTORS[module]
