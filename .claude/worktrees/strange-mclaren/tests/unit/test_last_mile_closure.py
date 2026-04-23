"""Unit tests — last-mile closure: affiliate clients, disclosure, permission enforcement, landing page publish, recovery auto-exec."""
from __future__ import annotations
import pytest

# ── 1. Affiliate Network Clients ──

def test_impact_client_blocked_without_creds():
    import asyncio
    from packages.clients.affiliate_network_clients import ImpactClient
    c = ImpactClient()
    result = asyncio.run(c.fetch_conversions("2025-01-01", "2025-01-07"))
    assert not result["success"]
    assert "IMPACT_ACCOUNT_SID" in result["error"]


def test_shareasale_client_blocked_without_creds():
    import asyncio
    from packages.clients.affiliate_network_clients import ShareASaleClient
    c = ShareASaleClient()
    result = asyncio.run(c.fetch_activity("2025-01-01", "2025-01-07"))
    assert not result["success"]
    assert "SHAREASALE_API_TOKEN" in result["error"]


def test_cj_client_blocked_without_creds():
    import asyncio
    from packages.clients.affiliate_network_clients import CJClient
    c = CJClient()
    result = asyncio.run(c.fetch_commissions("2025-01-01", "2025-01-07"))
    assert not result["success"]
    assert "CJ_API_KEY" in result["error"]


# ── 2. Disclosure Injection ──

def test_disclosure_injection_affiliate_youtube():
    from apps.api.services.disclosure_injection_service import inject_disclosure_into_content
    result = inject_disclosure_into_content("Great product review here.", "youtube", "affiliate")
    assert result["disclosure_injected"]
    assert "affiliate links" in result["text"].lower()
    assert result["placement"] == "description_top"


def test_disclosure_injection_sponsored_instagram():
    from apps.api.services.disclosure_injection_service import inject_disclosure_into_content
    result = inject_disclosure_into_content("Check this out!", "instagram", "sponsored", "AcmeCo")
    assert result["disclosure_injected"]
    assert "AcmeCo" in result["text"]
    assert result["placement"] == "caption_start"


def test_disclosure_already_present():
    from apps.api.services.disclosure_injection_service import inject_disclosure_into_content
    result = inject_disclosure_into_content("#ad #affiliate Check this out!", "tiktok", "affiliate")
    assert not result["disclosure_injected"]
    assert result["reason"] == "already_present"


def test_disclosure_validation_present():
    from apps.api.services.disclosure_injection_service import validate_disclosure_present
    assert validate_disclosure_present("Buy now #ad", "x", "affiliate")["valid"]


def test_disclosure_validation_missing():
    from apps.api.services.disclosure_injection_service import validate_disclosure_present
    assert not validate_disclosure_present("Buy now", "x", "affiliate")["valid"]


def test_disclosure_platform_default():
    from apps.api.services.disclosure_injection_service import inject_disclosure_into_content
    result = inject_disclosure_into_content("Nice product", "unknown_platform", "affiliate")
    assert result["disclosure_injected"]
    assert "#ad" in result["text"]


# ── 3. Permission Enforcement ──

def test_permission_enforcement_action_map():
    from apps.api.services.permission_enforcement import ACTION_MAP
    assert "auto_publish" in ACTION_MAP
    assert "recovery_rollback" in ACTION_MAP
    assert ACTION_MAP["auto_publish"] == "publish"


def test_permission_denied_exception():
    from apps.api.services.permission_enforcement import PermissionDenied
    exc = PermissionDenied("test_action", "manual_only", "operator required")
    assert "manual_only" in str(exc)
    assert exc.action == "test_action"


# ── 4. Buffer Credential Consistency ──

def test_buffer_credential_unified():
    """Verify the repo uses BUFFER_API_KEY consistently."""
    from packages.scoring.platform_registry_engine import PLATFORM_REGISTRY
    from packages.scoring.provider_registry_engine import PROVIDER_INVENTORY

    for plat in PLATFORM_REGISTRY:
        cred = plat.get("credential_env") or ""
        if "buffer" in cred.lower():
            assert cred == "BUFFER_API_KEY", f"Expected BUFFER_API_KEY, got {cred} for {plat['platform_key']}"

    buffer_prov = [p for p in PROVIDER_INVENTORY if p.get("name", "").lower() == "buffer"]
    for p in buffer_prov:
        assert "BUFFER_API_KEY" in p.get("env_keys", [])


# ── 5. Landing Page Publish Adapters ──

def test_publish_adapters_defined():
    from apps.api.services.landing_page_service import PUBLISH_ADAPTERS
    assert "manual" in PUBLISH_ADAPTERS
    assert "vercel" in PUBLISH_ADAPTERS
    assert "netlify" in PUBLISH_ADAPTERS
    assert "s3_static" in PUBLISH_ADAPTERS


# ── 6. Operator Permission Engine defaults ──

def test_rollback_action_fully_autonomous_by_default():
    from packages.scoring.operator_permission_engine import can_execute_autonomously
    result = can_execute_autonomously("rollback_action", [], [])
    assert result["allowed"] is True
    assert result["needs_approval"] is False


def test_campaign_launch_guarded_by_default():
    from packages.scoring.operator_permission_engine import can_execute_autonomously
    result = can_execute_autonomously("campaign_launch", [], [])
    assert result["allowed"] is False
    assert result["needs_approval"] is True


def test_governance_override_manual_only_by_default():
    from packages.scoring.operator_permission_engine import can_execute_autonomously
    result = can_execute_autonomously("governance_override", [], [])
    assert result["allowed"] is False
    assert "manual" in result["reason"].lower()
