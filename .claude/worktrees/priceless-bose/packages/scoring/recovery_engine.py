"""MXP Recovery Engine — detect incidents and recommend recovery actions.

This is the original MXP recovery module used by recovery_service.py and MXP workers.
The newer Recovery/Rollback Engine lives in recovery_rollback_engine.py.
"""
from __future__ import annotations
from typing import Any

RECOVERY = {
    "provider_outage": {"severity": "critical", "actions": ["switch_fallback_provider", "alert_operator"], "action_mode": "automatic"},
    "publishing_failure_spike": {"severity": "high", "actions": ["force_guarded_review", "pause_auto_publish"], "action_mode": "automatic"},
    "engagement_collapse": {"severity": "high", "actions": ["force_guarded_review", "creative_refresh"], "action_mode": "guarded"},
    "conversion_decline": {"severity": "high", "actions": ["force_guarded_review", "audit_offers", "test_new_angle"], "action_mode": "guarded"},
    "revenue_decline": {"severity": "critical", "actions": ["force_guarded_review", "audit_offers", "escalate"], "action_mode": "guarded"},
    "email_deliverability_issue": {"severity": "high", "actions": ["force_guarded_review", "pause_email_sends"], "action_mode": "automatic"},
    "cac_spike": {"severity": "medium", "actions": ["audit_paid_spend", "reduce_paid_budget"], "action_mode": "guarded"},
    "landing_page_failure_rate": {"severity": "high", "actions": ["pause_landing_pages", "alert_operator"], "action_mode": "automatic"},
    "ltv_decline": {"severity": "medium", "actions": ["audit_retention", "reactivation_campaign"], "action_mode": "guarded"},
    "sponsor_roi_drop": {"severity": "medium", "actions": ["renegotiate_terms", "pause_outreach"], "action_mode": "guarded"},
    "account_health_critical": {"severity": "critical", "actions": ["pause_monetization", "trust_repair"], "action_mode": "automatic"},
    "content_quality_collapse": {"severity": "high", "actions": ["force_guarded_review", "creative_refresh", "quality_audit"], "action_mode": "guarded"},
}


def detect_recovery_incidents(state: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect recovery-worthy incidents from MXP system state."""
    incidents = []
    for key, details in state.items():
        if key in RECOVERY:
            recovery_info = RECOVERY[key]
            metric_val = details.get("metric_value", 0) if isinstance(details, dict) else 0
            scope_type = details.get("scope_type", "brand") if isinstance(details, dict) else "brand"
            scope_id = details.get("scope_id") if isinstance(details, dict) else None

            confidence = min(1.0, 0.5 + abs(metric_val) * 0.5)
            explanation = f"{key}: metric_value={metric_val:.2f}, severity={recovery_info['severity']}, scope={scope_type}"

            incidents.append({
                "incident_type": key,
                "severity": recovery_info["severity"],
                "metric_value": metric_val,
                "scope_type": scope_type,
                "scope_id": scope_id,
                "confidence": round(confidence, 3),
                "explanation": explanation,
            })
    return incidents


def recommend_recovery_actions(incidents: list[dict[str, Any]], context: dict[str, Any]) -> list[dict[str, Any]]:
    """Recommend recovery actions for detected incidents."""
    actions = []
    for inc in incidents:
        itype = inc.get("incident_type", "")
        recovery_info = RECOVERY.get(itype, {"actions": ["alert_operator"], "action_mode": "guarded", "severity": "medium"})
        for action in recovery_info.get("actions", []):
            confidence = inc.get("confidence", 0.5)
            explanation = f"Action '{action}' for {itype} (severity={inc.get('severity', 'medium')})"
            actions.append({
                "action_type": action,
                "action_mode": recovery_info.get("action_mode", "guarded"),
                "incident_type": itype,
                "severity": inc.get("severity", "medium"),
                "scope_type": inc.get("scope_type", "brand"),
                "scope_id": inc.get("scope_id"),
                "confidence": round(confidence, 3),
                "explanation": explanation,
            })
    return actions
