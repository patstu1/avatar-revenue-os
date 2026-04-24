"""Unit tests for workflow engine."""
from packages.scoring.workflow_engine import (
    BUILT_IN_TEMPLATES,
    STEP_TYPES,
    WORKFLOW_TYPES,
    apply_template,
    evaluate_workflow_step,
    get_next_step,
    get_pending_actions,
    process_approval,
    process_override,
    process_rejection,
)


class TestWorkflowTypes:
    def test_types_exist(self):
        assert len(WORKFLOW_TYPES) >= 7
        assert "content_generation" in WORKFLOW_TYPES
        assert "campaign_launch" in WORKFLOW_TYPES

    def test_step_types(self):
        assert len(STEP_TYPES) >= 7

    def test_templates_exist(self):
        assert "content_publish" in BUILT_IN_TEMPLATES
        assert "campaign_launch" in BUILT_IN_TEMPLATES
        assert "risk_override" in BUILT_IN_TEMPLATES


class TestEvaluation:
    STEPS = [
        {"step_order": 1, "step_name": "Draft", "step_type": "draft_review", "required_role": "generator", "required_action": "approve"},
        {"step_order": 2, "step_name": "Brand", "step_type": "brand_review", "required_role": "brand_admin", "required_action": "approve"},
        {"step_order": 3, "step_name": "Publish", "step_type": "publish_approval", "required_role": "publisher", "required_action": "approve"},
    ]

    def test_correct_role_can_act(self):
        r = evaluate_workflow_step({"current_step_order": 1}, self.STEPS, "generator")
        assert r["can_act"] is True

    def test_wrong_role_blocked(self):
        r = evaluate_workflow_step({"current_step_order": 1}, self.STEPS, "viewer")
        assert r["can_act"] is False

    def test_super_admin_always_can(self):
        r = evaluate_workflow_step({"current_step_order": 2}, self.STEPS, "super_admin")
        assert r["can_act"] is True

    def test_no_step_found(self):
        r = evaluate_workflow_step({"current_step_order": 99}, self.STEPS, "generator")
        assert r["can_act"] is False


class TestAdvancement:
    STEPS = [{"step_order": 1, "step_name": "A"}, {"step_order": 2, "step_name": "B"}, {"step_order": 3, "step_name": "C"}]

    def test_advances_to_next(self):
        r = process_approval({"current_step_order": 1}, self.STEPS)
        assert r["action"] == "advance"
        assert r["next_step_order"] == 2

    def test_completes_at_last(self):
        r = process_approval({"current_step_order": 3}, self.STEPS)
        assert r["action"] == "complete"
        assert r["status"] == "completed"

    def test_get_next_step(self):
        s = get_next_step(self.STEPS, 1)
        assert s["step_order"] == 2

    def test_no_next_at_end(self):
        assert get_next_step(self.STEPS, 3) is None


class TestRejectionOverride:
    def test_rejection_rolls_back(self):
        r = process_rejection({"current_step_order": 2})
        assert r["action"] == "rollback"
        assert r["status"] == "rejected"

    def test_override_completes(self):
        r = process_override({"current_step_order": 1})
        assert r["action"] == "override_complete"
        assert r["status"] == "completed"


class TestTemplates:
    def test_content_publish(self):
        t = apply_template("content_publish")
        assert t is not None
        assert len(t["steps"]) == 3

    def test_unknown_template(self):
        assert apply_template("nonexistent") is None


class TestPendingActions:
    def test_finds_pending(self):
        instances = [{"id": "i1", "definition_id": "d1", "current_step_order": 1, "status": "in_progress", "resource_type": "content_item", "resource_id": "r1"}]
        steps_map = {"d1": [{"step_order": 1, "step_name": "Draft", "step_type": "draft_review", "required_role": "generator", "required_action": "approve"}]}
        pending = get_pending_actions(instances, steps_map, "generator")
        assert len(pending) == 1

    def test_skips_completed(self):
        instances = [{"id": "i1", "definition_id": "d1", "current_step_order": 1, "status": "completed"}]
        pending = get_pending_actions(instances, {}, "generator")
        assert len(pending) == 0
