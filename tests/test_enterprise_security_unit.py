"""Unit tests for enterprise security engine."""

from packages.scoring.enterprise_security_engine import (
    SYSTEM_ROLES,
    assess_compliance,
    build_audit_event,
    evaluate_model_isolation,
    evaluate_permission,
    evaluate_scope,
    evaluate_sensitive_data,
)


class TestRBAC:
    def test_system_roles_count(self):
        assert len(SYSTEM_ROLES) == 8

    def test_super_admin_can_do_anything(self):
        for action in ("generate", "approve", "publish", "admin", "delete", "override_risk", "view"):
            r = evaluate_permission("super_admin", 100, action)
            assert r["allowed"] is True

    def test_viewer_can_only_view(self):
        r = evaluate_permission("viewer", 10, "view")
        assert r["allowed"] is True
        for action in ("generate", "approve", "publish", "admin", "delete"):
            r = evaluate_permission("viewer", 10, action)
            assert r["allowed"] is False

    def test_generator_can_generate(self):
        r = evaluate_permission("generator", 40, "generate")
        assert r["allowed"] is True

    def test_generator_cannot_approve(self):
        r = evaluate_permission("generator", 40, "approve")
        assert r["allowed"] is False

    def test_unknown_action(self):
        r = evaluate_permission("super_admin", 100, "nonexistent")
        assert r["allowed"] is False


class TestScope:
    def test_org_scope_grants_all(self):
        scopes = [{"scope_type": "org", "scope_id": None}]
        r = evaluate_scope(scopes, "brand", "brand_123")
        assert r["allowed"] is True

    def test_matching_scope(self):
        scopes = [{"scope_type": "brand", "scope_id": "brand_123"}]
        r = evaluate_scope(scopes, "brand", "brand_123")
        assert r["allowed"] is True

    def test_non_matching_scope(self):
        scopes = [{"scope_type": "brand", "scope_id": "brand_456"}]
        r = evaluate_scope(scopes, "brand", "brand_123")
        assert r["allowed"] is False


class TestSensitiveData:
    def test_private_mode_blocks_model(self):
        policies = [
            {
                "data_class": "pii",
                "private_mode": True,
                "model_restriction": "dedicated_only",
                "is_active": True,
                "training_leak_prevention": True,
            }
        ]
        r = evaluate_sensitive_data("pii", policies, "send_to_model")
        assert r["allowed"] is False
        assert r["private_mode"] is True

    def test_training_blocked(self):
        policies = [
            {"data_class": "confidential", "private_mode": False, "training_leak_prevention": True, "is_active": True}
        ]
        r = evaluate_sensitive_data("confidential", policies, "send_to_training")
        assert r["allowed"] is False

    def test_public_allowed(self):
        policies = [{"data_class": "pii", "private_mode": True, "is_active": True}]
        r = evaluate_sensitive_data("public", policies, "send_to_model")
        assert r["allowed"] is True


class TestModelIsolation:
    def test_dedicated_required(self):
        policies = [
            {
                "provider_key": "claude",
                "isolation_mode": "dedicated",
                "dedicated_instance_id": "inst-123",
                "data_residency": "us-east",
                "is_active": True,
            }
        ]
        r = evaluate_model_isolation("claude", policies)
        assert r["isolation_required"] is True
        assert r["mode"] == "dedicated"

    def test_shared_default(self):
        r = evaluate_model_isolation("gemini", [])
        assert r["isolation_required"] is False


class TestCompliance:
    def test_gdpr_assessment(self):
        state = {
            "data_policies_configured": True,
            "audit_trail_active": True,
            "erasure_capability": True,
            "consent_tracking": False,
            "data_residency_set": True,
            "rbac_configured": True,
            "scopes_assigned": True,
            "model_isolation_set": True,
        }
        results = assess_compliance("gdpr", state)
        assert len(results) == 5
        met = [r for r in results if r["status"] == "met"]
        assert len(met) >= 3

    def test_soc2_assessment(self):
        results = assess_compliance(
            "soc2",
            {
                "rbac_configured": True,
                "scopes_assigned": False,
                "audit_trail_active": True,
                "data_policies_configured": False,
            },
        )
        assert len(results) == 5

    def test_unknown_framework(self):
        assert assess_compliance("unknown", {}) == []


class TestAuditEvent:
    def test_builds_event(self):
        e = build_audit_event("user1", "publish", "content_item", "ci1", "Published content")
        assert e["action"] == "publish"
        assert e["user_id"] == "user1"
