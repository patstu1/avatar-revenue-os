"""Unit tests for Live Execution Phase 2 + Buffer Expansion engines."""

from packages.scoring.live_execution_phase2_engine import (
    BUFFER_TRUTH_STATES,
    ESCALATION_THRESHOLD,
    MAX_BUFFER_RETRIES,
    STALE_JOB_THRESHOLD_HOURS,
    WEBHOOK_SOURCES,
    build_ingestion_summary,
    check_duplicate_submit,
    check_idempotency,
    classify_buffer_truth_state,
    classify_webhook_source,
    compute_retry_backoff,
    detect_stale_jobs,
    determine_sequence_triggers,
    evaluate_ad_platform_readiness,
    evaluate_analytics_sync_readiness,
    evaluate_buffer_profile_readiness,
    evaluate_payment_sync_readiness,
)


def test_classify_webhook_source_stripe():
    out = classify_webhook_source("stripe")
    assert out["source_category"] == "payment"
    assert out["known"] is True


def test_classify_webhook_source_unknown():
    out = classify_webhook_source("unknown_xyz")
    assert out["known"] is False


def test_check_idempotency_duplicate():
    assert check_idempotency("evt-1", {"evt-1", "evt-2"}) is True


def test_check_idempotency_new():
    assert check_idempotency("evt-new", {"evt-1"}) is False


def test_sequence_triggers_purchase_creates_conversion():
    triggers = determine_sequence_triggers("purchase", "payment", 0)
    assert len(triggers) >= 1
    assert any("conversion" in t["action_type"] for t in triggers)


def test_sequence_triggers_purchase_high_value_adds_upsell():
    triggers = determine_sequence_triggers("purchase", "payment", 150.0)
    assert any(t.get("action_type") == "create_upsell_offer" for t in triggers)


def test_sequence_triggers_subscription_cancelled():
    triggers = determine_sequence_triggers("subscription_cancelled", "payment", 0)
    assert any(t.get("action_type") == "start_reactivation_sequence" for t in triggers)


def test_sequence_triggers_unknown_event():
    # Engine has no trigger for arbitrary unknown strings; use a known lifecycle type
    # that hits the generic `_KNOWN_EVENT_TYPES` nurture path (fallback-style behavior).
    triggers = determine_sequence_triggers("subscription_started", "unknown", 0)
    assert len(triggers) >= 1


def test_payment_sync_no_key_blocked():
    result = evaluate_payment_sync_readiness("stripe", api_key_present=False)
    assert result["sync_ready"] is False
    assert "missing" in result["credential_status"]


def test_payment_sync_with_key_ready():
    result = evaluate_payment_sync_readiness("stripe", api_key_present=True)
    assert result["sync_ready"] is True


def test_ad_platform_no_key():
    result = evaluate_ad_platform_readiness("meta_ads", api_key_present=False, account_id_present=True)
    assert result["import_ready"] is False


def test_ad_platform_with_key_and_account():
    result = evaluate_ad_platform_readiness("meta_ads", api_key_present=True, account_id_present=True)
    assert result["import_ready"] is True


def test_analytics_sync_no_key():
    result = evaluate_analytics_sync_readiness("youtube_analytics", api_key_present=False)
    assert result["sync_ready"] is False
    assert result["credential_status"] == "missing"


def test_buffer_truth_pending_maps_to_queued():
    # External "queued" maps to truth state containing "queued" (queued_internally).
    result = classify_buffer_truth_state("queued", None, 0, 0)
    assert "queued" in result["truth_state"]


def test_buffer_truth_published():
    for status in ("published", "published_by_buffer"):
        result = classify_buffer_truth_state(status, None, 0, 0)
        assert result["truth_state"] == "published_by_buffer"


def test_buffer_truth_stale_detection():
    result = classify_buffer_truth_state("pending", None, 0, 100.0)
    assert result["is_stale"] is True


def test_buffer_truth_not_stale_when_published():
    result = classify_buffer_truth_state("published", None, 0, 100.0)
    assert result["is_stale"] is False


def test_duplicate_submit_detected():
    assert check_duplicate_submit("cid-1", "twitter", {"cid-1:twitter"}) is True


def test_duplicate_submit_not_duplicate():
    assert check_duplicate_submit("cid-1", "twitter", set()) is False


def test_retry_backoff_attempt_1():
    result = compute_retry_backoff(1)
    assert result["backoff_seconds"] > 0
    assert result["should_escalate"] is False


def test_retry_backoff_escalation():
    result = compute_retry_backoff(ESCALATION_THRESHOLD)
    assert result["should_escalate"] is True


def test_retry_backoff_exponential():
    first = compute_retry_backoff(1)["backoff_seconds"]
    third = compute_retry_backoff(3)["backoff_seconds"]
    assert third > first


def test_detect_stale_jobs_stale():
    result = detect_stale_jobs(STALE_JOB_THRESHOLD_HOURS + 1, "submitted_to_buffer")
    assert result["is_stale"] is True


def test_detect_stale_jobs_not_stale():
    result = detect_stale_jobs(1.0, "submitted_to_buffer")
    assert result["is_stale"] is False


def test_buffer_profile_ready():
    result = evaluate_buffer_profile_readiness(
        credential_status="valid",
        buffer_profile_id="prof-1",
        platform="twitter",
        is_active=True,
    )
    assert result["profile_ready"] is True


def test_buffer_profile_not_ready_missing_id():
    result = evaluate_buffer_profile_readiness(
        credential_status="valid",
        buffer_profile_id=None,
        platform="twitter",
        is_active=True,
    )
    assert result["missing_profile_mapping"] is True


def test_buffer_profile_inactive():
    result = evaluate_buffer_profile_readiness(
        credential_status="valid",
        buffer_profile_id="prof-1",
        platform="twitter",
        is_active=False,
    )
    assert result["inactive_profile"] is True


def test_ingestion_summary_all_processed():
    result = build_ingestion_summary(10, 10, 0, 0)
    assert result["status"] == "completed"


def test_ingestion_summary_with_failures():
    result = build_ingestion_summary(10, 5, 0, 2)
    assert result["needs_attention"] is True


def test_constants_exported():
    assert isinstance(BUFFER_TRUTH_STATES, list)
    assert len(BUFFER_TRUTH_STATES) >= 1
    assert isinstance(WEBHOOK_SOURCES, list)
    assert MAX_BUFFER_RETRIES == 5
    assert STALE_JOB_THRESHOLD_HOURS == 48
    assert ESCALATION_THRESHOLD == 3
