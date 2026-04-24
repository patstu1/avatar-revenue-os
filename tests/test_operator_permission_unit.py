"""Unit tests for operator permission engine."""
from packages.scoring.operator_permission_engine import (
    ACTION_CLASSES,
    AUTONOMY_MODES,
    DEFAULT_POLICIES,
    can_execute_autonomously,
    detect_policy_conflicts,
    evaluate_action_policy,
    evaluate_override_eligibility,
    seed_default_matrix,
)


class TestTypes:
    def test_15_action_classes(self):
        assert len(ACTION_CLASSES) == 15
    def test_4_modes(self):
        assert len(AUTONOMY_MODES) == 4
    def test_all_have_defaults(self):
        for ac in ACTION_CLASSES:
            assert ac in DEFAULT_POLICIES


class TestPolicyEval:
    def test_matrix_overrides_default(self):
        matrix = [{"action_class": "content_generation", "autonomy_mode": "manual_only", "is_active": True}]
        r = evaluate_action_policy("content_generation", matrix, [])
        assert r["mode"] == "manual_only"
        assert r["source"] == "matrix"

    def test_default_when_no_matrix(self):
        r = evaluate_action_policy("content_generation", [], [])
        assert r["mode"] == "fully_autonomous"
        assert r["source"] == "default"

    def test_policy_fallback(self):
        policies = [{"action_class": "content_generation", "default_mode": "guarded_approval", "is_active": True}]
        r = evaluate_action_policy("content_generation", [], policies)
        assert r["mode"] == "guarded_approval"
        assert r["source"] == "policy"


class TestAutonomy:
    def test_fully_autonomous(self):
        r = can_execute_autonomously("content_generation", [], [])
        assert r["allowed"] is True
        assert r["needs_approval"] is False

    def test_autonomous_notify(self):
        r = can_execute_autonomously("content_publish", [], [])
        assert r["allowed"] is True
        assert r["needs_notification"] is True

    def test_guarded_approval(self):
        r = can_execute_autonomously("campaign_launch", [], [])
        assert r["allowed"] is False
        assert r["needs_approval"] is True

    def test_manual_only(self):
        r = can_execute_autonomously("governance_override", [], [])
        assert r["allowed"] is False


class TestOverride:
    def test_super_admin_can_override(self):
        matrix = [{"action_class": "governance_override", "autonomy_mode": "manual_only", "override_allowed": True, "override_role": "super_admin", "is_active": True}]
        r = evaluate_override_eligibility("governance_override", "super_admin", matrix, [])
        assert r["can_override"] is True

    def test_viewer_cannot_override(self):
        matrix = [{"action_class": "content_publish", "autonomy_mode": "guarded_approval", "override_allowed": True, "override_role": "org_admin", "is_active": True}]
        r = evaluate_override_eligibility("content_publish", "viewer", matrix, [])
        assert r["can_override"] is False

    def test_override_disabled(self):
        matrix = [{"action_class": "test", "autonomy_mode": "manual_only", "override_allowed": False, "is_active": True}]
        r = evaluate_override_eligibility("test", "super_admin", matrix, [])
        assert r["can_override"] is False


class TestConflicts:
    def test_detects_conflict(self):
        matrix = [
            {"action_class": "content_publish", "autonomy_mode": "fully_autonomous", "is_active": True},
            {"action_class": "content_publish", "autonomy_mode": "manual_only", "is_active": True},
        ]
        conflicts = detect_policy_conflicts(matrix)
        assert len(conflicts) == 1

    def test_no_conflict(self):
        matrix = [
            {"action_class": "content_publish", "autonomy_mode": "guarded_approval", "is_active": True},
            {"action_class": "campaign_launch", "autonomy_mode": "manual_only", "is_active": True},
        ]
        assert detect_policy_conflicts(matrix) == []


class TestSeed:
    def test_seeds_all(self):
        rows = seed_default_matrix("org_123")
        assert len(rows) == 15
        actions = {r["action_class"] for r in rows}
        assert "content_generation" in actions
        assert "governance_override" in actions
