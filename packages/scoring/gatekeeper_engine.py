"""AI Gatekeeper Engine — hard internal control system.

Every function evaluates real system state and returns pass/fail with severity.
No soft passes. No fake approvals. If something is incomplete, say so.
"""

from __future__ import annotations

from typing import Any

# Gate severity levels
SEVERITY_CRITICAL = "critical"
SEVERITY_HIGH = "high"
SEVERITY_MEDIUM = "medium"
SEVERITY_LOW = "low"

# Required layers for a module to be considered complete
REQUIRED_LAYERS = ["model", "migration", "engine", "service", "api", "frontend", "tests", "docs"]

# Known system modules with their expected layers
SYSTEM_MODULES = {
    "revenue_ceiling_phase_a": {"has_worker": True},
    "revenue_ceiling_phase_b": {"has_worker": True},
    "revenue_ceiling_phase_c": {"has_worker": True},
    "expansion_pack2_phase_a": {"has_worker": True},
    "expansion_pack2_phase_b": {"has_worker": True},
    "expansion_pack2_phase_c": {"has_worker": True},
    "growth_commander": {"has_worker": True},
    "growth_pack": {"has_worker": True},
    "scale_alerts": {"has_worker": True},
    "buffer_distribution": {"has_worker": True},
    "live_execution_phase1": {"has_worker": True},
    "live_execution_phase2": {"has_worker": True},
    "creator_revenue": {"has_worker": True},
    "autonomous_execution": {"has_worker": True},
    "brain": {"has_worker": False},
    "copilot": {"has_worker": False},
    "provider_registry": {"has_worker": False},
    "mxp_experiments": {"has_worker": True},
    "mxp_contribution": {"has_worker": False},
    "mxp_capacity": {"has_worker": False},
    "mxp_recovery": {"has_worker": False},
    "mxp_deal_desk": {"has_worker": False},
    "mxp_kill_ledger": {"has_worker": False},
}


# ── 1. Completion Gate ─────────────────────────────────────────────────


def evaluate_completion(
    module_name: str,
    layers_present: dict[str, bool],
) -> dict[str, Any]:
    """Check if a module has all required layers."""
    missing = [l for l in REQUIRED_LAYERS if not layers_present.get(f"has_{l}", False)]

    # Worker is required only for modules that need it
    module_config = SYSTEM_MODULES.get(module_name, {})
    if module_config.get("has_worker") and not layers_present.get("has_worker", False):
        missing.append("worker")

    score = 1.0 - (len(missing) / (len(REQUIRED_LAYERS) + 1))
    passed = len(missing) == 0
    severity = SEVERITY_CRITICAL if len(missing) > 3 else SEVERITY_HIGH if missing else SEVERITY_LOW

    return {
        "module_name": module_name,
        "completion_score": round(max(0, score), 3),
        "missing_layers": missing,
        "gate_passed": passed,
        "severity": severity,
        "explanation": (
            f"Module '{module_name}' is complete"
            if passed
            else f"Module '{module_name}' is incomplete — missing: {', '.join(missing)}"
        ),
        **{f"has_{l}": layers_present.get(f"has_{l}", False) for l in REQUIRED_LAYERS + ["worker"]},
    }


# ── 2. Truth Gate ──────────────────────────────────────────────────────


def evaluate_truth(
    module_name: str,
    claimed_status: str,
    actual_status: str,
    has_live_data: bool = False,
    has_real_client: bool = False,
) -> dict[str, Any]:
    """Detect truth mismatches — things labeled live that aren't."""
    mismatch = claimed_status != actual_status
    mislabeled_live = claimed_status == "live" and actual_status in ("stubbed", "partial", "planned")
    synthetic_unlabeled = actual_status == "synthetic" and claimed_status == "live"

    passed = not mismatch and not mislabeled_live
    severity = SEVERITY_CRITICAL if mislabeled_live else SEVERITY_HIGH if mismatch else SEVERITY_LOW

    return {
        "module_name": module_name,
        "claimed_status": claimed_status,
        "actual_status": actual_status,
        "truth_mismatch": mismatch,
        "mislabeled_as_live": mislabeled_live,
        "synthetic_without_label": synthetic_unlabeled,
        "gate_passed": passed,
        "severity": severity,
        "explanation": (
            f"TRUTH VIOLATION: '{module_name}' claims '{claimed_status}' but is actually '{actual_status}'"
            if mismatch
            else f"'{module_name}' truth status verified: {actual_status}"
        ),
    }


# ── 3. Execution Closure Gate ──────────────────────────────────────────


def evaluate_execution_closure(
    module_name: str,
    has_execution_path: bool,
    has_downstream_action: bool,
    has_blocker_handling: bool,
    pending_actions_count: int = 0,
    stale_blocker_count: int = 0,
    orphaned_recommendations: int = 0,
) -> dict[str, Any]:
    """Detect dead-end flows, stale blockers, orphaned recommendations."""
    dead_end = not has_execution_path and pending_actions_count > 0
    stale = stale_blocker_count > 0
    orphaned = orphaned_recommendations > 0

    passed = has_execution_path and has_downstream_action and not dead_end and not stale and not orphaned
    severity = (
        SEVERITY_CRITICAL if dead_end else SEVERITY_HIGH if stale else SEVERITY_MEDIUM if orphaned else SEVERITY_LOW
    )

    issues = []
    if dead_end:
        issues.append(f"{pending_actions_count} pending actions with no execution path")
    if stale:
        issues.append(f"{stale_blocker_count} stale blockers unresolved")
    if orphaned:
        issues.append(f"{orphaned_recommendations} orphaned recommendations with no follow-through")
    if not has_blocker_handling:
        issues.append("no blocker handling path")

    return {
        "module_name": module_name,
        "has_execution_path": has_execution_path,
        "has_downstream_action": has_downstream_action,
        "has_blocker_handling": has_blocker_handling,
        "dead_end_detected": dead_end,
        "stale_blocker_detected": stale,
        "orphaned_recommendation": orphaned > 0,
        "gate_passed": passed,
        "severity": severity,
        "explanation": "; ".join(issues) if issues else f"'{module_name}' execution closure verified",
    }


# ── 4. Test Sufficiency Gate ──────────────────────────────────────────


def evaluate_test_sufficiency(
    module_name: str,
    unit_test_count: int,
    integration_test_count: int,
    has_critical_path_tests: bool,
    has_high_risk_tests: bool,
) -> dict[str, Any]:
    """Check test coverage — zero tests on high-risk flows is a gate failure."""
    total = unit_test_count + integration_test_count
    passed = total >= 3 and has_critical_path_tests
    severity = (
        SEVERITY_CRITICAL
        if total == 0
        else SEVERITY_HIGH
        if not has_critical_path_tests
        else SEVERITY_MEDIUM
        if not has_high_risk_tests
        else SEVERITY_LOW
    )

    return {
        "module_name": module_name,
        "unit_test_count": unit_test_count,
        "integration_test_count": integration_test_count,
        "critical_paths_covered": has_critical_path_tests,
        "high_risk_flows_tested": has_high_risk_tests,
        "gate_passed": passed,
        "severity": severity,
        "explanation": (
            f"'{module_name}' has {total} tests (unit: {unit_test_count}, integration: {integration_test_count}). "
            + ("Critical paths covered." if has_critical_path_tests else "MISSING critical path tests.")
        ),
    }


# ── 5. Dependency Readiness Gate ──────────────────────────────────────


def evaluate_dependency_readiness(
    module_name: str,
    provider_key: str,
    credential_present: bool,
    integration_live: bool,
) -> dict[str, Any]:
    """Check if a module's external dependencies are ready."""
    blocked_by_external = not credential_present and not integration_live
    met = credential_present and integration_live

    severity = SEVERITY_HIGH if blocked_by_external else SEVERITY_MEDIUM if not met else SEVERITY_LOW

    return {
        "module_name": module_name,
        "provider_key": provider_key,
        "dependency_met": met,
        "credential_present": credential_present,
        "integration_live": integration_live,
        "blocked_by_external": blocked_by_external,
        "gate_passed": met or not blocked_by_external,
        "severity": severity,
        "explanation": (
            f"'{module_name}' dependency on '{provider_key}': "
            + (
                "ready"
                if met
                else f"blocked — credential={'present' if credential_present else 'MISSING'}, integration={'live' if integration_live else 'NOT LIVE'}"
            )
        ),
    }


# ── 6. Contradiction Detection ────────────────────────────────────────


def detect_contradictions(
    states: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find contradictory states across modules.

    Each state dict: {"module": str, "status": str, "claims": dict}
    """
    contradictions = []

    for i, a in enumerate(states):
        for b in states[i + 1 :]:
            # Module claims live but dependency says blocked
            if a.get("status") == "live" and b.get("status") == "blocked" and a.get("depends_on") == b.get("module"):
                contradictions.append(
                    {
                        "module_a": a["module"],
                        "module_b": b["module"],
                        "contradiction_type": "live_depends_on_blocked",
                        "description": f"'{a['module']}' claims live but depends on '{b['module']}' which is blocked",
                        "severity": SEVERITY_CRITICAL,
                        "gate_passed": False,
                    }
                )

            # Both claim primary for same capability
            if (
                a.get("claims", {}).get("capability") == b.get("claims", {}).get("capability")
                and a.get("claims", {}).get("role") == "primary"
                and b.get("claims", {}).get("role") == "primary"
            ):
                contradictions.append(
                    {
                        "module_a": a["module"],
                        "module_b": b["module"],
                        "contradiction_type": "duplicate_primary",
                        "description": f"Both '{a['module']}' and '{b['module']}' claim primary for '{a['claims']['capability']}'",
                        "severity": SEVERITY_HIGH,
                        "gate_passed": False,
                    }
                )

    return contradictions


# ── 7. Operator Command Quality Gate ──────────────────────────────────


def evaluate_operator_command_quality(
    command_source: str,
    command_text: str,
    has_target: bool = False,
    has_metric: bool = False,
    has_deadline: bool = False,
) -> dict[str, Any]:
    """Grade operator command quality — reject vague/weak commands."""
    is_actionable = len(command_text.strip()) > 10 and has_target
    is_specific = has_target and (has_metric or has_deadline)
    has_measurable = has_metric
    quality = 0.3 * is_actionable + 0.4 * is_specific + 0.3 * has_measurable
    passed = quality >= 0.5

    severity = SEVERITY_HIGH if quality < 0.3 else SEVERITY_MEDIUM if not passed else SEVERITY_LOW

    return {
        "command_source": command_source,
        "command_summary": command_text[:200],
        "is_actionable": is_actionable,
        "is_specific": is_specific,
        "has_measurable_outcome": has_measurable,
        "quality_score": round(quality, 3),
        "gate_passed": passed,
        "severity": severity,
        "explanation": (
            f"Command quality {quality:.0%}: "
            + ("actionable" if is_actionable else "NOT actionable")
            + (", specific" if is_specific else ", NOT specific")
            + (", measurable" if has_measurable else ", NOT measurable")
        ),
    }


# ── 8. Expansion Permission Gate ─────────────────────────────────────


def evaluate_expansion_permission(
    expansion_target: str,
    prerequisites_met: bool,
    blockers_resolved: bool,
    test_coverage_sufficient: bool,
    dependencies_ready: bool,
    critical_gates_passing: bool = True,
) -> dict[str, Any]:
    """Hard gate — expansion is blocked unless ALL conditions pass."""
    blocking = []
    if not prerequisites_met:
        blocking.append("prerequisites not met")
    if not blockers_resolved:
        blocking.append("unresolved blockers")
    if not test_coverage_sufficient:
        blocking.append("insufficient test coverage")
    if not dependencies_ready:
        blocking.append("dependencies not ready")
    if not critical_gates_passing:
        blocking.append("critical gates failing")

    granted = len(blocking) == 0
    severity = SEVERITY_CRITICAL if len(blocking) >= 3 else SEVERITY_HIGH if blocking else SEVERITY_LOW

    return {
        "expansion_target": expansion_target,
        "prerequisites_met": prerequisites_met,
        "blockers_resolved": blockers_resolved,
        "test_coverage_sufficient": test_coverage_sufficient,
        "dependencies_ready": dependencies_ready,
        "permission_granted": granted,
        "blocking_reasons": blocking,
        "severity": severity,
        "explanation": (
            f"Expansion to '{expansion_target}': {'PERMITTED' if granted else 'BLOCKED — ' + '; '.join(blocking)}"
        ),
    }


# ── 9. Alert Generation ──────────────────────────────────────────────


def generate_gatekeeper_alerts(
    completion_reports: list[dict],
    truth_reports: list[dict],
    closure_reports: list[dict],
    test_reports: list[dict],
    dependency_reports: list[dict],
    contradiction_reports: list[dict],
) -> list[dict[str, Any]]:
    """Generate alerts from all gate failures."""
    alerts = []

    for r in completion_reports:
        if not r.get("gate_passed"):
            alerts.append(
                {
                    "gate_type": "completion",
                    "severity": r.get("severity", SEVERITY_HIGH),
                    "title": f"Incomplete module: {r.get('module_name', '?')}",
                    "description": r.get("explanation", ""),
                    "source_module": r.get("module_name"),
                    "operator_action": f"Complete missing layers: {', '.join(r.get('missing_layers', []))}",
                }
            )

    for r in truth_reports:
        if not r.get("gate_passed"):
            alerts.append(
                {
                    "gate_type": "truth",
                    "severity": r.get("severity", SEVERITY_CRITICAL),
                    "title": f"Truth mismatch: {r.get('module_name', '?')}",
                    "description": r.get("explanation", ""),
                    "source_module": r.get("module_name"),
                    "operator_action": "Fix truth label to match actual status",
                }
            )

    for r in closure_reports:
        if not r.get("gate_passed"):
            alerts.append(
                {
                    "gate_type": "execution_closure",
                    "severity": r.get("severity", SEVERITY_HIGH),
                    "title": f"Execution gap: {r.get('module_name', '?')}",
                    "description": r.get("explanation", ""),
                    "source_module": r.get("module_name"),
                    "operator_action": "Resolve dead-end flows and stale blockers",
                }
            )

    for r in test_reports:
        if not r.get("gate_passed"):
            alerts.append(
                {
                    "gate_type": "test_sufficiency",
                    "severity": r.get("severity", SEVERITY_MEDIUM),
                    "title": f"Insufficient tests: {r.get('module_name', '?')}",
                    "description": r.get("explanation", ""),
                    "source_module": r.get("module_name"),
                    "operator_action": "Add critical path tests",
                }
            )

    for r in dependency_reports:
        if not r.get("gate_passed"):
            alerts.append(
                {
                    "gate_type": "dependency",
                    "severity": r.get("severity", SEVERITY_HIGH),
                    "title": f"Dependency blocked: {r.get('module_name', '?')} → {r.get('provider_key', '?')}",
                    "description": r.get("explanation", ""),
                    "source_module": r.get("module_name"),
                    "operator_action": f"Set credentials for {r.get('provider_key', '?')}",
                }
            )

    for r in contradiction_reports:
        alerts.append(
            {
                "gate_type": "contradiction",
                "severity": r.get("severity", SEVERITY_CRITICAL),
                "title": f"Contradiction: {r.get('module_a', '?')} ↔ {r.get('module_b', '?')}",
                "description": r.get("description", ""),
                "source_module": f"{r.get('module_a')},{r.get('module_b')}",
                "operator_action": "Resolve contradictory state",
            }
        )

    alerts.sort(
        key=lambda a: {SEVERITY_CRITICAL: 0, SEVERITY_HIGH: 1, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 3}.get(
            a.get("severity", "medium"), 2
        )
    )
    return alerts


# ── 10. Audit Ledger ──────────────────────────────────────────────────


def build_audit_entry(
    gate_type: str,
    action: str,
    module_name: str,
    result: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "gate_type": gate_type,
        "action": action,
        "module_name": module_name,
        "result": result,
        "details_json": details or {},
    }
