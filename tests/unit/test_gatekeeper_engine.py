"""Unit tests for AI Gatekeeper engine."""

from packages.scoring.gatekeeper_engine import (
    REQUIRED_LAYERS,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    build_audit_entry,
    detect_contradictions,
    evaluate_completion,
    evaluate_dependency_readiness,
    evaluate_execution_closure,
    evaluate_expansion_permission,
    evaluate_operator_command_quality,
    evaluate_test_sufficiency,
    evaluate_truth,
    generate_gatekeeper_alerts,
)

# ── Completion Gate ────────────────────────────────────────────────────


def _all_layers_true() -> dict[str, bool]:
    return {f"has_{l}": True for l in REQUIRED_LAYERS + ["worker"]}


def test_completion_all_layers_present():
    r = evaluate_completion("growth_commander", _all_layers_true())
    assert r["gate_passed"] is True
    assert r["completion_score"] == 1.0
    assert r["missing_layers"] == []
    assert r["severity"] != SEVERITY_CRITICAL


def test_completion_missing_model():
    layers = _all_layers_true()
    layers["has_model"] = False
    r = evaluate_completion("growth_commander", layers)
    assert r["gate_passed"] is False
    assert "model" in r["missing_layers"]


def test_completion_missing_multiple_triggers_critical():
    layers = {f"has_{l}": False for l in REQUIRED_LAYERS + ["worker"]}
    layers["has_model"] = True
    layers["has_migration"] = True
    r = evaluate_completion("growth_commander", layers)
    assert r["gate_passed"] is False
    assert len(r["missing_layers"]) >= 4
    assert r["severity"] == SEVERITY_CRITICAL


def test_completion_score_between_0_and_1():
    for present_count in range(len(REQUIRED_LAYERS) + 1):
        layers = {}
        for i, l in enumerate(REQUIRED_LAYERS):
            layers[f"has_{l}"] = i < present_count
        layers["has_worker"] = present_count > len(REQUIRED_LAYERS) - 1
        r = evaluate_completion("brain", layers)
        assert 0 <= r["completion_score"] <= 1.0


def test_completion_worker_not_required_for_non_worker_module():
    layers = {f"has_{l}": True for l in REQUIRED_LAYERS}
    layers["has_worker"] = False
    r = evaluate_completion("brain", layers)
    assert r["gate_passed"] is True
    assert "worker" not in r["missing_layers"]


def test_completion_worker_required_for_worker_module():
    layers = {f"has_{l}": True for l in REQUIRED_LAYERS}
    layers["has_worker"] = False
    r = evaluate_completion("growth_commander", layers)
    assert r["gate_passed"] is False
    assert "worker" in r["missing_layers"]


# ── Truth Gate ─────────────────────────────────────────────────────────


def test_truth_match():
    r = evaluate_truth("brain", "live", "live")
    assert r["gate_passed"] is True
    assert r["truth_mismatch"] is False
    assert r["mislabeled_as_live"] is False


def test_truth_mismatch_live_vs_stubbed():
    r = evaluate_truth("brain", "live", "stubbed")
    assert r["gate_passed"] is False
    assert r["mislabeled_as_live"] is True
    assert r["severity"] == SEVERITY_CRITICAL


def test_truth_partial_not_mislabeled():
    r = evaluate_truth("brain", "partial", "partial")
    assert r["gate_passed"] is True
    assert r["mislabeled_as_live"] is False


def test_truth_synthetic_unlabeled():
    r = evaluate_truth("brain", "live", "synthetic")
    assert r["synthetic_without_label"] is True
    assert r["gate_passed"] is False


# ── Execution Closure Gate ─────────────────────────────────────────────


def test_closure_complete():
    r = evaluate_execution_closure(
        "brain", has_execution_path=True, has_downstream_action=True, has_blocker_handling=True
    )
    assert r["gate_passed"] is True
    assert r["dead_end_detected"] is False


def test_closure_dead_end():
    r = evaluate_execution_closure(
        "brain",
        has_execution_path=False,
        has_downstream_action=True,
        has_blocker_handling=True,
        pending_actions_count=5,
    )
    assert r["dead_end_detected"] is True
    assert r["gate_passed"] is False
    assert r["severity"] == SEVERITY_CRITICAL


def test_closure_stale_blocker():
    r = evaluate_execution_closure(
        "brain",
        has_execution_path=True,
        has_downstream_action=True,
        has_blocker_handling=True,
        stale_blocker_count=3,
    )
    assert r["stale_blocker_detected"] is True
    assert r["gate_passed"] is False


def test_closure_orphaned_recommendation():
    r = evaluate_execution_closure(
        "brain",
        has_execution_path=True,
        has_downstream_action=True,
        has_blocker_handling=True,
        orphaned_recommendations=2,
    )
    assert r["orphaned_recommendation"] is True
    assert r["gate_passed"] is False


# ── Test Sufficiency Gate ──────────────────────────────────────────────


def test_tests_sufficient():
    r = evaluate_test_sufficiency(
        "brain", unit_test_count=5, integration_test_count=2, has_critical_path_tests=True, has_high_risk_tests=True
    )
    assert r["gate_passed"] is True


def test_tests_zero():
    r = evaluate_test_sufficiency(
        "brain", unit_test_count=0, integration_test_count=0, has_critical_path_tests=False, has_high_risk_tests=False
    )
    assert r["gate_passed"] is False
    assert r["severity"] == SEVERITY_CRITICAL


def test_tests_no_critical_path():
    r = evaluate_test_sufficiency(
        "brain", unit_test_count=10, integration_test_count=0, has_critical_path_tests=False, has_high_risk_tests=True
    )
    assert r["gate_passed"] is False


def test_tests_below_minimum_total():
    r = evaluate_test_sufficiency(
        "brain", unit_test_count=1, integration_test_count=0, has_critical_path_tests=True, has_high_risk_tests=True
    )
    assert r["gate_passed"] is False


# ── Dependency Readiness Gate ──────────────────────────────────────────


def test_dependency_met():
    r = evaluate_dependency_readiness("live_execution_phase2", "stripe", credential_present=True, integration_live=True)
    assert r["gate_passed"] is True
    assert r["dependency_met"] is True
    assert r["blocked_by_external"] is False


def test_dependency_blocked():
    r = evaluate_dependency_readiness(
        "live_execution_phase2", "stripe", credential_present=False, integration_live=False
    )
    assert r["blocked_by_external"] is True
    assert r["gate_passed"] is False


def test_dependency_credential_present_but_not_live():
    r = evaluate_dependency_readiness("buffer_distribution", "buffer", credential_present=True, integration_live=False)
    assert r["dependency_met"] is False
    assert r["blocked_by_external"] is False
    assert r["gate_passed"] is True


# ── Contradiction Detection ────────────────────────────────────────────


def test_no_contradictions():
    states = [
        {"module": "brain", "status": "live", "claims": {}, "depends_on": None},
        {"module": "copilot", "status": "live", "claims": {}, "depends_on": None},
    ]
    assert detect_contradictions(states) == []


def test_contradiction_live_depends_blocked():
    states = [
        {"module": "module_a", "status": "live", "claims": {}, "depends_on": "module_b"},
        {"module": "module_b", "status": "blocked", "claims": {}, "depends_on": None},
    ]
    contras = detect_contradictions(states)
    assert len(contras) == 1
    assert contras[0]["contradiction_type"] == "live_depends_on_blocked"
    assert contras[0]["severity"] == SEVERITY_CRITICAL
    assert contras[0]["gate_passed"] is False


def test_contradiction_duplicate_primary():
    states = [
        {"module": "module_a", "status": "live", "claims": {"capability": "analytics", "role": "primary"}},
        {"module": "module_b", "status": "live", "claims": {"capability": "analytics", "role": "primary"}},
    ]
    contras = detect_contradictions(states)
    assert len(contras) == 1
    assert contras[0]["contradiction_type"] == "duplicate_primary"
    assert contras[0]["severity"] == SEVERITY_HIGH


# ── Operator Command Quality Gate ──────────────────────────────────────


def test_command_quality_good():
    r = evaluate_operator_command_quality(
        "growth_commander",
        "Scale YouTube channel to 50k subs by Q3",
        has_target=True,
        has_metric=True,
        has_deadline=True,
    )
    assert r["gate_passed"] is True
    assert r["is_actionable"] is True
    assert r["is_specific"] is True
    assert r["has_measurable_outcome"] is True


def test_command_quality_vague():
    r = evaluate_operator_command_quality(
        "copilot",
        "do stuff",
        has_target=False,
        has_metric=False,
        has_deadline=False,
    )
    assert r["gate_passed"] is False
    assert r["is_actionable"] is False
    assert r["quality_score"] == 0.0


def test_command_quality_partial():
    r = evaluate_operator_command_quality(
        "scale_alerts",
        "Add 2 new TikTok accounts for fitness niche",
        has_target=True,
        has_metric=False,
        has_deadline=False,
    )
    assert r["is_actionable"] is True
    assert r["has_measurable_outcome"] is False


# ── Expansion Permission Gate ──────────────────────────────────────────


def test_expansion_granted():
    r = evaluate_expansion_permission(
        "next_phase",
        prerequisites_met=True,
        blockers_resolved=True,
        test_coverage_sufficient=True,
        dependencies_ready=True,
        critical_gates_passing=True,
    )
    assert r["permission_granted"] is True
    assert r["blocking_reasons"] == []


def test_expansion_blocked_prerequisites():
    r = evaluate_expansion_permission(
        "next_phase",
        prerequisites_met=False,
        blockers_resolved=True,
        test_coverage_sufficient=True,
        dependencies_ready=True,
    )
    assert r["permission_granted"] is False
    assert "prerequisites not met" in r["blocking_reasons"]


def test_expansion_blocked_multiple_reasons():
    r = evaluate_expansion_permission(
        "production_deploy",
        prerequisites_met=False,
        blockers_resolved=False,
        test_coverage_sufficient=False,
        dependencies_ready=False,
        critical_gates_passing=False,
    )
    assert r["permission_granted"] is False
    assert len(r["blocking_reasons"]) == 5
    assert r["severity"] == SEVERITY_CRITICAL


# ── Alert Generation ──────────────────────────────────────────────────


def test_alerts_from_failures():
    comp_fail = [evaluate_completion("brain", {f"has_{l}": False for l in REQUIRED_LAYERS})]
    truth_fail = [evaluate_truth("brain", "live", "stubbed")]
    alerts = generate_gatekeeper_alerts(comp_fail, truth_fail, [], [], [], [])
    gate_types = {a["gate_type"] for a in alerts}
    assert "completion" in gate_types
    assert "truth" in gate_types
    assert all("title" in a and "severity" in a for a in alerts)


def test_alerts_sorted_by_severity():
    comp_fail = [evaluate_completion("brain", {f"has_{l}": (l == "model") for l in REQUIRED_LAYERS})]
    truth_fail = [evaluate_truth("brain", "live", "stubbed")]
    closure_fail = [evaluate_execution_closure("brain", False, True, True, orphaned_recommendations=1)]
    alerts = generate_gatekeeper_alerts(comp_fail, truth_fail, closure_fail, [], [], [])
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    for i in range(len(alerts) - 1):
        assert severity_order[alerts[i]["severity"]] <= severity_order[alerts[i + 1]["severity"]]


def test_alerts_empty_when_all_pass():
    comp_pass = [evaluate_completion("brain", _all_layers_true())]
    truth_pass = [evaluate_truth("brain", "live", "live")]
    alerts = generate_gatekeeper_alerts(comp_pass, truth_pass, [], [], [], [])
    assert alerts == []


def test_alerts_include_contradictions():
    states = [
        {"module": "a", "status": "live", "claims": {}, "depends_on": "b"},
        {"module": "b", "status": "blocked", "claims": {}, "depends_on": None},
    ]
    contras = detect_contradictions(states)
    alerts = generate_gatekeeper_alerts([], [], [], [], [], contras)
    assert len(alerts) == 1
    assert alerts[0]["gate_type"] == "contradiction"


# ── Audit Ledger ──────────────────────────────────────────────────────


def test_audit_entry_structure():
    entry = build_audit_entry("completion", "recompute", "brain", "passed", {"score": 1.0})
    assert entry["gate_type"] == "completion"
    assert entry["action"] == "recompute"
    assert entry["module_name"] == "brain"
    assert entry["result"] == "passed"
    assert entry["details_json"] == {"score": 1.0}


def test_audit_entry_defaults_empty_details():
    entry = build_audit_entry("truth", "recompute", "copilot", "failed")
    assert entry["details_json"] == {}


# ── Cross-gate integration detection ─────────────────────────────────


def test_detect_module_lacking_layer():
    layers = _all_layers_true()
    layers["has_api"] = False
    r = evaluate_completion("brain", layers)
    assert "api" in r["missing_layers"]


def test_detect_mislabeled_live():
    r = evaluate_truth("copilot", "live", "stubbed")
    assert r["mislabeled_as_live"] is True
    assert r["severity"] == SEVERITY_CRITICAL


def test_detect_queued_no_execution():
    r = evaluate_execution_closure(
        "autonomous_execution",
        has_execution_path=False,
        has_downstream_action=True,
        has_blocker_handling=True,
        pending_actions_count=10,
    )
    assert r["dead_end_detected"] is True
    assert r["gate_passed"] is False


def test_detect_blocker_prevents_expansion():
    r = evaluate_expansion_permission(
        "new_pack",
        prerequisites_met=True,
        blockers_resolved=False,
        test_coverage_sufficient=True,
        dependencies_ready=True,
    )
    assert r["permission_granted"] is False
    assert "unresolved blockers" in r["blocking_reasons"]
