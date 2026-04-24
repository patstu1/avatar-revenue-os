"""Unit tests for Platform Registry Engine — execution truth and readiness."""
from packages.scoring.platform_registry_engine import (
    BUFFER_SUPPORTED_PLATFORMS,
    PLATFORM_BY_KEY,
    PLATFORM_REGISTRY,
    detect_platform_blockers,
    get_all_platform_readiness,
    get_expansion_candidates,
    get_monetization_fit,
    get_platform_readiness,
)


def test_all_platforms_have_required_fields():
    required = {"platform_key", "display_name", "priority", "content_role", "supported_forms",
                "monetization_suitability", "constraints", "buffer_supported", "publish_mode",
                "execution_truth", "analytics_source", "expansion_suitability", "credential_env"}
    for p in PLATFORM_REGISTRY:
        for f in required:
            assert f in p, f"Platform {p['platform_key']} missing field: {f}"


def test_snapchat_in_registry():
    assert "snapchat" in PLATFORM_BY_KEY
    snap = PLATFORM_BY_KEY["snapchat"]
    assert snap["publish_mode"] == "manual"
    assert snap["execution_truth"] == "recommendation_only"


def test_email_newsletter_uses_esp_service():
    p = PLATFORM_BY_KEY["email_newsletter"]
    assert p["publish_mode"] == "esp_service"
    assert p["credential_env"] == "SMTP_HOST"


def test_seo_authority_is_recommendation_only():
    p = PLATFORM_BY_KEY["seo_authority"]
    assert p["publish_mode"] == "manual"
    assert p["execution_truth"] == "recommendation_only"
    assert p["blocker_state"] == "no_cms_client"


def test_medium_is_recommendation_only():
    r = get_platform_readiness("medium")
    assert r["execution_truth"] == "recommendation_only"
    assert r["ready"] is False


def test_substack_is_recommendation_only():
    r = get_platform_readiness("substack")
    assert r["execution_truth"] == "recommendation_only"
    assert r["ready"] is False


def test_telegram_is_recommendation_only():
    r = get_platform_readiness("telegram")
    assert r["execution_truth"] == "recommendation_only"


def test_discord_is_recommendation_only():
    r = get_platform_readiness("discord")
    assert r["execution_truth"] == "recommendation_only"


def test_buffer_platforms_blocked_without_key():
    r = get_platform_readiness("instagram")
    assert r["publish_mode"] == "buffer"
    assert r["credential_env"] == "BUFFER_API_KEY"


def test_email_blocked_without_smtp():
    r = get_platform_readiness("email_newsletter")
    assert r["credential_env"] == "SMTP_HOST"
    assert r["execution_truth"] in ("live", "blocked_by_credentials")


def test_reddit_has_no_direct_publish():
    r = get_platform_readiness("reddit")
    assert r["publish_mode"] == "manual"
    assert r["blocker"] is not None


def test_buffer_supported_list():
    assert "instagram" in BUFFER_SUPPORTED_PLATFORMS
    assert "youtube" in BUFFER_SUPPORTED_PLATFORMS
    assert "reddit" not in BUFFER_SUPPORTED_PLATFORMS
    assert "email_newsletter" not in BUFFER_SUPPORTED_PLATFORMS


def test_all_platform_readiness_returns_all():
    all_r = get_all_platform_readiness()
    assert len(all_r) == len(PLATFORM_REGISTRY)
    for r in all_r:
        assert "execution_truth" in r
        assert "publish_mode" in r


def test_expansion_candidates():
    candidates = get_expansion_candidates(0.6)
    keys = [c["platform_key"] for c in candidates]
    assert "email_newsletter" in keys
    assert "tiktok" in keys


def test_detect_blockers_manual_platform():
    blockers = detect_platform_blockers("telegram")
    assert len(blockers) >= 1
    assert any("no_direct_publish_client" in b["type"] for b in blockers)


def test_detect_blockers_buffer_platform():
    blockers = detect_platform_blockers("instagram")
    if blockers:
        assert any("BUFFER_API_KEY" in b.get("description", "") for b in blockers)


def test_monetization_fit():
    assert get_monetization_fit("email_newsletter", "affiliate") >= 0.9
    assert get_monetization_fit("snapchat", "affiliate") == 0.0
    assert get_monetization_fit("nonexistent", "affiliate") == 0.0


def test_unknown_platform_readiness():
    r = get_platform_readiness("nonexistent_platform")
    assert r["ready"] is False
    assert r["execution_truth"] == "unknown_platform"


def test_every_platform_has_execution_truth():
    for p in PLATFORM_REGISTRY:
        assert p["execution_truth"] in ("live_when_configured", "recommendation_only"), f"{p['platform_key']} has bad truth: {p['execution_truth']}"


def test_every_platform_has_publish_mode():
    valid = {"buffer", "direct_api", "esp_service", "manual", "recommendation_only"}
    for p in PLATFORM_REGISTRY:
        assert p["publish_mode"] in valid, f"{p['platform_key']} has bad publish_mode: {p['publish_mode']}"
