"""Unit tests for Live Execution Closure Phase 1 engine logic."""

from packages.scoring.live_execution_engine import (
    classify_analytics_source,
    compute_import_summary,
    derive_experiment_truth,
    detect_messaging_blockers,
    reconcile_truth,
    validate_email_send,
    validate_sms_send,
)

# ── classify_analytics_source ──────────────────────────────────────────

class TestClassifyAnalyticsSource:
    def test_buffer_is_social(self):
        assert classify_analytics_source("buffer_analytics") == "social"

    def test_tiktok_is_social(self):
        assert classify_analytics_source("tiktok_insights") == "social"

    def test_instagram_is_social(self):
        assert classify_analytics_source("instagram_api") == "social"

    def test_youtube_is_social(self):
        assert classify_analytics_source("youtube_analytics") == "social"

    def test_twitter_is_social(self):
        assert classify_analytics_source("twitter_api") == "social"

    def test_facebook_is_social(self):
        assert classify_analytics_source("facebook_insights") == "social"

    def test_linkedin_is_social(self):
        assert classify_analytics_source("linkedin_api") == "social"

    def test_reddit_is_social(self):
        assert classify_analytics_source("reddit_api") == "social"

    def test_stripe_is_checkout(self):
        assert classify_analytics_source("stripe_payments") == "checkout"

    def test_shopify_is_checkout(self):
        assert classify_analytics_source("shopify_orders") == "checkout"

    def test_affiliate_source(self):
        assert classify_analytics_source("clickbank_affiliate") == "affiliate"

    def test_email_source(self):
        assert classify_analytics_source("mailchimp_stats") == "email"

    def test_sms_source(self):
        assert classify_analytics_source("twilio_sms") == "sms"

    def test_ads_source(self):
        assert classify_analytics_source("google_ads_report") == "ads"

    def test_crm_source(self):
        assert classify_analytics_source("hubspot_crm") == "crm"

    def test_unknown_is_manual(self):
        assert classify_analytics_source("random_thing") == "manual"


# ── reconcile_truth ────────────────────────────────────────────────────

class TestReconcileTruth:
    def test_live_import_beats_proxy(self):
        assert reconcile_truth("synthetic_proxy", "live_import") == "live_import"

    def test_live_verified_beats_import(self):
        assert reconcile_truth("live_import", "live_verified") == "live_verified"

    def test_proxy_does_not_beat_live(self):
        assert reconcile_truth("live_import", "synthetic_proxy") == "live_import"

    def test_same_level_keeps_new(self):
        assert reconcile_truth("live_import", "live_import") == "live_import"

    def test_operator_override_beats_proxy(self):
        assert reconcile_truth("synthetic_proxy", "operator_override") == "operator_override"

    def test_unknown_loses_to_everything(self):
        assert reconcile_truth("unknown", "synthetic_proxy") == "synthetic_proxy"


# ── compute_import_summary ─────────────────────────────────────────────

class TestComputeImportSummary:
    def test_all_new(self):
        events = [{"external_post_id": "a"}, {"external_post_id": "b"}]
        result = compute_import_summary(events, set())
        assert result["events_imported"] == 2
        assert result["events_new"] == 2
        assert result["events_matched"] == 0

    def test_some_matched(self):
        events = [{"external_post_id": "a"}, {"external_post_id": "b"}]
        result = compute_import_summary(events, {"a"})
        assert result["events_matched"] == 1
        assert result["events_new"] == 1

    def test_empty(self):
        result = compute_import_summary([], set())
        assert result["events_imported"] == 0


# ── derive_experiment_truth ────────────────────────────────────────────

class TestDeriveExperimentTruth:
    def test_live_with_large_sample(self):
        result = derive_experiment_truth(0.5, 0.8, 100)
        assert result["truth_level"] == "live_import"
        assert result["value"] == 0.8
        assert result["source"] == "live"

    def test_blended_with_small_sample(self):
        result = derive_experiment_truth(0.5, 0.8, 20)
        assert result["truth_level"] == "live_import"
        assert result["source"] == "blended"
        assert 0.5 < result["value"] < 0.8

    def test_proxy_fallback(self):
        result = derive_experiment_truth(0.5, None, 0)
        assert result["truth_level"] == "synthetic_proxy"
        assert result["value"] == 0.5
        assert result["source"] == "proxy"

    def test_proxy_tiny_sample(self):
        result = derive_experiment_truth(0.5, 0.9, 5)
        assert result["truth_level"] == "synthetic_proxy"


# ── detect_messaging_blockers ──────────────────────────────────────────

class TestDetectMessagingBlockers:
    def test_all_missing(self):
        blockers = detect_messaging_blockers({})
        types = {b["blocker_type"] for b in blockers}
        assert "missing_smtp_config" in types
        assert "missing_sms_api_key" in types
        assert "missing_esp_api_key" in types
        assert "missing_crm_credentials" in types
        assert "no_contacts" in types

    def test_all_present(self):
        ctx = {
            "has_smtp_config": True,
            "has_sms_api_key": True,
            "has_esp_api_key": True,
            "has_crm_credentials": True,
            "contacts_count": 50,
        }
        blockers = detect_messaging_blockers(ctx)
        assert len(blockers) == 0

    def test_only_smtp_missing(self):
        ctx = {
            "has_smtp_config": False,
            "has_sms_api_key": True,
            "has_esp_api_key": True,
            "has_crm_credentials": True,
            "contacts_count": 50,
        }
        blockers = detect_messaging_blockers(ctx)
        assert len(blockers) == 1
        assert blockers[0]["blocker_type"] == "missing_smtp_config"

    def test_severity_levels(self):
        blockers = detect_messaging_blockers({})
        severity_map = {b["blocker_type"]: b["severity"] for b in blockers}
        assert severity_map["missing_smtp_config"] == "critical"
        assert severity_map["missing_sms_api_key"] == "critical"
        assert severity_map["missing_esp_api_key"] == "high"
        assert severity_map["no_contacts"] == "medium"


# ── validate_email_send ────────────────────────────────────────────────

class TestValidateEmailSend:
    def test_valid_smtp(self):
        result = validate_email_send(
            {"to_email": "a@b.com", "subject": "Hi", "body_text": "Hello"},
            {"has_smtp_config": True}
        )
        assert result["valid"] is True

    def test_valid_esp(self):
        result = validate_email_send(
            {"to_email": "a@b.com", "subject": "Hi", "template_id": "tmpl_1"},
            {"has_esp_api_key": True}
        )
        assert result["valid"] is True

    def test_no_provider(self):
        result = validate_email_send(
            {"to_email": "a@b.com", "subject": "Hi", "body_text": "Hello"},
            {}
        )
        assert result["valid"] is False

    def test_missing_email(self):
        result = validate_email_send(
            {"to_email": "", "subject": "Hi", "body_text": "Hello"},
            {"has_smtp_config": True}
        )
        assert result["valid"] is False

    def test_missing_subject(self):
        result = validate_email_send(
            {"to_email": "a@b.com", "subject": "", "body_text": "Hello"},
            {"has_smtp_config": True}
        )
        assert result["valid"] is False

    def test_missing_body_and_template(self):
        result = validate_email_send(
            {"to_email": "a@b.com", "subject": "Hi"},
            {"has_smtp_config": True}
        )
        assert result["valid"] is False


# ── validate_sms_send ──────────────────────────────────────────────────

class TestValidateSmsSend:
    def test_valid(self):
        result = validate_sms_send(
            {"to_phone": "+1234567890", "message_body": "Hello"},
            {"has_sms_api_key": True}
        )
        assert result["valid"] is True

    def test_no_api_key(self):
        result = validate_sms_send(
            {"to_phone": "+1234567890", "message_body": "Hello"},
            {}
        )
        assert result["valid"] is False

    def test_missing_phone(self):
        result = validate_sms_send(
            {"to_phone": "", "message_body": "Hello"},
            {"has_sms_api_key": True}
        )
        assert result["valid"] is False

    def test_missing_body(self):
        result = validate_sms_send(
            {"to_phone": "+1234567890", "message_body": ""},
            {"has_sms_api_key": True}
        )
        assert result["valid"] is False

    def test_body_too_long(self):
        result = validate_sms_send(
            {"to_phone": "+1234567890", "message_body": "X" * 1601},
            {"has_sms_api_key": True}
        )
        assert result["valid"] is False
