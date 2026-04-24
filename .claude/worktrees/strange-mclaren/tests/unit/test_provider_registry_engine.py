"""Unit tests for Provider Registry engine."""
import pytest

from packages.scoring.provider_registry_engine import (
    PROVIDER_INVENTORY,
    PROVIDER_DEPENDENCIES,
    audit_all_providers,
    check_provider_credentials,
    get_provider_blockers,
    get_dependency_map,
)

REQUIRED_FIELDS = {"provider_key", "display_name", "category", "provider_type"}


def test_provider_inventory_not_empty():
    assert len(PROVIDER_INVENTORY) >= 20


def test_every_provider_has_required_fields():
    for p in PROVIDER_INVENTORY:
        for field in REQUIRED_FIELDS:
            assert field in p, f"{p.get('provider_key', '??')} missing {field}"


def test_claude_is_primary_reasoning():
    claude = next((p for p in PROVIDER_INVENTORY if p["provider_key"] == "claude"), None)
    assert claude is not None, "claude entry missing"
    assert claude["is_primary"] is True
    assert claude["category"] == "ai_text"
    assert claude["provider_type"] == "primary"


def test_openai_is_fallback():
    openai = next((p for p in PROVIDER_INVENTORY if p["provider_key"] == "openai"), None)
    assert openai is not None, "openai entry missing"
    assert openai["is_fallback"] is True or openai["provider_type"] == "fallback"


def test_infrastructure_always_live():
    for key in ("postgres", "redis"):
        p = next((p for p in PROVIDER_INVENTORY if p["provider_key"] == key), None)
        assert p is not None, f"{key} entry missing"
        assert p["integration_status"] == "live", f"{key} should be live"


def test_check_credentials_no_keys_required():
    provider = {"provider_key": "test_no_keys", "env_keys": []}
    result = check_provider_credentials(provider)
    assert result["is_ready"] is True
    assert result["credential_status"] == "not_required"


def test_check_credentials_missing():
    provider = {"provider_key": "test_missing", "env_keys": ["NONEXISTENT_KEY_XYZ_123"]}
    result = check_provider_credentials(provider)
    assert result["is_ready"] is False
    assert result["credential_status"] == "not_configured"
    assert "NONEXISTENT_KEY_XYZ_123" in result["missing_keys"]


def test_check_credentials_present(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_123")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_123")
    stripe = next(p for p in PROVIDER_INVENTORY if p["provider_key"] == "stripe")
    result = check_provider_credentials(stripe)
    assert result["is_ready"] is True
    assert result["credential_status"] == "configured"


def test_audit_returns_all_providers():
    results = audit_all_providers()
    assert len(results) >= 20


def test_audit_includes_effective_status():
    results = audit_all_providers()
    for r in results:
        assert "effective_status" in r, f"{r['provider_key']} missing effective_status"


def test_blockers_generated_for_unconfigured():
    blockers = get_provider_blockers("dummy-brand-id")
    assert len(blockers) >= 1
    for b in blockers:
        assert "provider_key" in b
        assert "severity" in b
        assert "operator_action_needed" in b


def test_dependency_map_not_empty():
    deps = get_dependency_map()
    assert len(deps) >= 15


def test_each_dependency_has_module_path():
    for d in get_dependency_map():
        assert "module_path" in d, f"dependency for {d.get('provider_key', '??')} missing module_path"
        assert "provider_key" in d
