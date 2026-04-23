"""Recovery / Rollback Engine — detect, decide, recover. Pure functions."""
from __future__ import annotations
from typing import Any, Optional

INCIDENT_TYPES = [
    "provider_failure", "publish_failure", "bad_scaling_push", "experiment_failure_cluster",
    "broken_routing_path", "weak_content_push", "campaign_failure", "dependency_outage",
    "retry_exhaustion", "unsafe_system_state",
]

PLAYBOOKS = {
    "provider_failure": {"steps": [{"action": "reroute", "target": "fallback_provider"}, {"action": "throttle", "level": "50pct"}, {"action": "alert_operator"}], "auto_execute": True},
    "publish_failure": {"steps": [{"action": "retry", "max": 3}, {"action": "rollback", "target": "draft_status"}, {"action": "alert_operator"}], "auto_execute": True},
    "bad_scaling_push": {"steps": [{"action": "throttle", "level": "25pct"}, {"action": "rollback", "target": "previous_cadence"}, {"action": "alert_operator"}], "auto_execute": True},
    "experiment_failure_cluster": {"steps": [{"action": "suppress_experiment"}, {"action": "rollback", "target": "control_variant"}, {"action": "alert_operator"}], "auto_execute": True},
    "broken_routing_path": {"steps": [{"action": "reroute", "target": "default_path"}, {"action": "alert_operator"}], "auto_execute": True},
    "weak_content_push": {"steps": [{"action": "throttle", "level": "50pct"}, {"action": "suppress_content_family"}, {"action": "alert_operator"}], "auto_execute": False},
    "campaign_failure": {"steps": [{"action": "pause_campaign"}, {"action": "reroute", "target": "safer_campaign"}, {"action": "alert_operator"}], "auto_execute": True},
    "dependency_outage": {"steps": [{"action": "reroute", "target": "fallback"}, {"action": "throttle", "level": "minimal"}, {"action": "escalate"}], "auto_execute": True},
    "retry_exhaustion": {"steps": [{"action": "rollback", "target": "last_good_state"}, {"action": "alert_operator"}], "auto_execute": True},
    "unsafe_system_state": {"steps": [{"action": "pause_all"}, {"action": "escalate"}], "auto_execute": False},
}


def detect_incidents(system_state: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect recovery-worthy incidents from system state."""
    incidents = []

    for pf in system_state.get("provider_failures", []):
        incidents.append(_incident("provider_failure", "critical", "provider", pf, f"Provider {pf.get('name', '')} failed: {pf.get('error', '')}", True))

    for pf in system_state.get("publish_failures", []):
        incidents.append(_incident("publish_failure", "high", "content_item", pf, f"Publish failed for content {pf.get('id', '')[:8]}", True))

    for bf in system_state.get("bad_scaling", []):
        incidents.append(_incident("bad_scaling_push", "high", "account", bf, f"Account {bf.get('name', '')} health dropped after scaling push", True))

    for ef in system_state.get("experiment_failures", []):
        incidents.append(_incident("experiment_failure_cluster", "medium", "experiment", ef, f"Experiment cluster failure on {ef.get('variable', '')}", True))

    for brk in system_state.get("broken_routes", []):
        incidents.append(_incident("broken_routing_path", "high", "routing", brk, f"Route broken: {brk.get('path', '')}", True))

    for dep in system_state.get("dependency_outages", []):
        incidents.append(_incident("dependency_outage", "critical", "dependency", dep, f"Dependency outage: {dep.get('name', '')}", True))

    if system_state.get("unsafe_state"):
        incidents.append(_incident("unsafe_system_state", "critical", "system", {}, "System in unsafe state — operator escalation required", False))

    return incidents


def _incident(itype: str, severity: str, scope: str, item: dict, detail: str, auto: bool) -> dict[str, Any]:
    return {"incident_type": itype, "severity": severity, "affected_scope": scope, "affected_id": item.get("id"), "detail": detail, "auto_recoverable": auto}


def select_playbook(incident_type: str) -> Optional[dict[str, Any]]:
    """Select the recovery playbook for an incident type."""
    return PLAYBOOKS.get(incident_type)


def decide_recovery(incident: dict[str, Any], playbook: dict[str, Any] = None) -> dict[str, Any]:
    """Decide recovery actions for an incident."""
    if not playbook:
        playbook = select_playbook(incident.get("incident_type", ""))

    if not playbook:
        return {"decision": "escalate", "actions": [], "reason": "No playbook for this incident type"}

    actions = []
    for step in playbook.get("steps", []):
        action = step.get("action", "")
        if action == "rollback":
            actions.append({"type": "rollback", "target": step.get("target", "previous_state"), "detail": f"Roll back {incident['affected_scope']} to {step.get('target', 'safe state')}"})
        elif action == "reroute":
            actions.append({"type": "reroute", "from": incident.get("affected_scope", ""), "to": step.get("target", "fallback"), "detail": f"Reroute from {incident['affected_scope']} to {step.get('target', 'fallback')}"})
        elif action == "throttle":
            actions.append({"type": "throttle", "target": incident.get("affected_scope", ""), "level": step.get("level", "50pct"), "detail": f"Throttle {incident['affected_scope']} to {step.get('level', '50%')}"})
        elif action in ("alert_operator", "escalate"):
            actions.append({"type": "escalate", "detail": f"Escalate to operator: {incident['detail']}"})
        elif action == "retry":
            actions.append({"type": "retry", "max_retries": step.get("max", 3), "detail": f"Retry up to {step.get('max', 3)} times"})
        elif action == "pause_all":
            actions.append({"type": "pause", "target": "all", "detail": "Pause all operations"})
        else:
            actions.append({"type": action, "detail": f"Execute: {action}"})

    auto = playbook.get("auto_execute", False) and incident.get("auto_recoverable", False)
    return {"decision": "auto_recover" if auto else "operator_review", "actions": actions, "reason": f"Playbook: {incident['incident_type']}"}


def should_escalate(incident: dict[str, Any], recovery: dict[str, Any]) -> bool:
    """Determine if the incident requires operator escalation."""
    if incident.get("severity") == "critical" and not incident.get("auto_recoverable"):
        return True
    if recovery.get("decision") == "operator_review":
        return True
    return False
