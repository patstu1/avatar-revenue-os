"""Unit tests for recovery engine."""
from packages.scoring.recovery_rollback_engine import (
    INCIDENT_TYPES,
    PLAYBOOKS,
    decide_recovery,
    detect_incidents,
    select_playbook,
    should_escalate,
)


class TestIncidentTypes:
    def test_10_types(self):
        assert len(INCIDENT_TYPES) == 10

    def test_all_have_playbooks(self):
        for it in INCIDENT_TYPES:
            assert it in PLAYBOOKS


class TestDetection:
    def test_provider_failure(self):
        state = {"provider_failures": [{"id": "p1", "name": "stripe", "error": "timeout"}]}
        incidents = detect_incidents(state)
        assert any(i["incident_type"] == "provider_failure" for i in incidents)

    def test_publish_failure(self):
        state = {"publish_failures": [{"id": "c1"}]}
        incidents = detect_incidents(state)
        assert any(i["incident_type"] == "publish_failure" for i in incidents)

    def test_dependency_outage(self):
        state = {"dependency_outages": [{"id": "d1", "name": "redis"}]}
        incidents = detect_incidents(state)
        assert any(i["incident_type"] == "dependency_outage" for i in incidents)

    def test_unsafe_state(self):
        state = {"unsafe_state": True}
        incidents = detect_incidents(state)
        assert any(i["incident_type"] == "unsafe_system_state" for i in incidents)
        assert not incidents[-1]["auto_recoverable"]

    def test_clean_state(self):
        assert detect_incidents({}) == []


class TestPlaybook:
    def test_selects_playbook(self):
        pb = select_playbook("provider_failure")
        assert pb is not None
        assert len(pb["steps"]) >= 2

    def test_unknown_returns_none(self):
        assert select_playbook("nonexistent") is None


class TestRecovery:
    def test_auto_recover(self):
        incident = {"incident_type": "provider_failure", "severity": "critical", "affected_scope": "provider", "detail": "Stripe down", "auto_recoverable": True}
        recovery = decide_recovery(incident)
        assert recovery["decision"] == "auto_recover"
        assert len(recovery["actions"]) >= 2

    def test_operator_review(self):
        incident = {"incident_type": "unsafe_system_state", "severity": "critical", "affected_scope": "system", "detail": "Unsafe", "auto_recoverable": False}
        recovery = decide_recovery(incident)
        assert recovery["decision"] == "operator_review"

    def test_no_playbook_escalates(self):
        incident = {"incident_type": "unknown_type", "severity": "high", "affected_scope": "test", "detail": "test"}
        recovery = decide_recovery(incident)
        assert recovery["decision"] == "escalate"

    def test_rollback_action(self):
        incident = {"incident_type": "publish_failure", "severity": "high", "affected_scope": "content_item", "detail": "Failed", "auto_recoverable": True}
        recovery = decide_recovery(incident)
        rollbacks = [a for a in recovery["actions"] if a["type"] == "rollback"]
        assert len(rollbacks) >= 1

    def test_reroute_action(self):
        incident = {"incident_type": "provider_failure", "severity": "critical", "affected_scope": "provider", "detail": "Down", "auto_recoverable": True}
        recovery = decide_recovery(incident)
        reroutes = [a for a in recovery["actions"] if a["type"] == "reroute"]
        assert len(reroutes) >= 1

    def test_throttle_action(self):
        incident = {"incident_type": "bad_scaling_push", "severity": "high", "affected_scope": "account", "detail": "Health drop", "auto_recoverable": True}
        recovery = decide_recovery(incident)
        throttles = [a for a in recovery["actions"] if a["type"] == "throttle"]
        assert len(throttles) >= 1


class TestEscalation:
    def test_critical_non_auto_escalates(self):
        assert should_escalate({"severity": "critical", "auto_recoverable": False}, {"decision": "operator_review"}) is True

    def test_auto_recoverable_no_escalation(self):
        assert should_escalate({"severity": "high", "auto_recoverable": True}, {"decision": "auto_recover"}) is False
