"""Unit tests for Buffer Distribution Layer engine logic."""
import pytest

from packages.scoring.buffer_engine import (
    build_publish_payload,
    determine_publish_mode,
    detect_buffer_blockers,
    map_buffer_status,
    compute_publish_job_summary,
    evaluate_profile_readiness,
    JOB_STATUSES,
)


class TestBuildPublishPayload:
    def test_basic_text_post(self):
        r = build_publish_payload(
            {"caption": "Hello world", "title": "Test"},
            {"platform": "tiktok", "buffer_profile_id": "bp_123"},
        )
        assert r["_profile_ids"] == ["bp_123"]
        assert "Hello world" in r["text"]
        assert r["schedulingType"] == "automatic"

    def test_text_truncated_for_twitter(self):
        long_text = "A" * 300
        r = build_publish_payload(
            {"caption": long_text},
            {"platform": "twitter", "buffer_profile_id": "bp_x"},
        )
        assert len(r["text"]) <= 280

    def test_text_not_truncated_for_instagram(self):
        text = "B" * 500
        r = build_publish_payload(
            {"caption": text},
            {"platform": "instagram", "buffer_profile_id": "bp_ig"},
        )
        assert len(r["text"]) == 500

    def test_media_photo_attachment(self):
        r = build_publish_payload(
            {"caption": "Look", "media_url": "https://example.com/photo.jpg"},
            {"platform": "tiktok", "buffer_profile_id": "bp_1"},
        )
        assert "images" in r.get("assets", {})

    def test_media_video_attachment(self):
        r = build_publish_payload(
            {"caption": "Watch", "media_url": "https://example.com/clip.mp4"},
            {"platform": "tiktok", "buffer_profile_id": "bp_1"},
        )
        assert "videos" in r.get("assets", {})

    def test_link_url_appended(self):
        r = build_publish_payload(
            {"caption": "Check", "link_url": "https://example.com"},
            {"platform": "linkedin", "buffer_profile_id": "bp_li"},
        )
        assert "https://example.com" in r["text"]

    def test_scheduled_at_included(self):
        r = build_publish_payload(
            {"caption": "Later", "scheduled_at": "2026-04-01T10:00:00Z"},
            {"platform": "youtube", "buffer_profile_id": "bp_yt"},
        )
        assert r["dueAt"] == "2026-04-01T10:00:00Z"
        assert r["schedulingType"] == "customScheduled"


class TestDeterminePublishMode:
    def test_default_is_queue(self):
        assert determine_publish_mode({}, {}) == "queue"

    def test_publish_now(self):
        assert determine_publish_mode({"publish_now": True}, {}) == "publish_now"

    def test_scheduled(self):
        assert determine_publish_mode({"scheduled_at": "2026-04-01"}, {}) == "schedule"


class TestDetectBufferBlockers:
    def test_no_api_key(self):
        blockers = detect_buffer_blockers([], {"has_buffer_api_key": False})
        types = [b["blocker_type"] for b in blockers]
        assert "missing_buffer_api_key" in types

    def test_no_profiles(self):
        blockers = detect_buffer_blockers([], {"has_buffer_api_key": True})
        types = [b["blocker_type"] for b in blockers]
        assert "profile_not_linked" in types

    def test_not_connected_profile(self):
        profiles = [{"id": "p1", "platform": "tiktok", "display_name": "TK", "credential_status": "not_connected"}]
        blockers = detect_buffer_blockers(profiles, {"has_buffer_api_key": True})
        types = [b["blocker_type"] for b in blockers]
        assert "missing_buffer_credentials" in types

    def test_expired_token(self):
        profiles = [{"id": "p1", "platform": "instagram", "display_name": "IG", "credential_status": "expired"}]
        blockers = detect_buffer_blockers(profiles, {"has_buffer_api_key": True})
        types = [b["blocker_type"] for b in blockers]
        assert "expired_buffer_token" in types

    def test_no_blockers_when_connected(self):
        profiles = [{"id": "p1", "platform": "tiktok", "display_name": "TK", "credential_status": "connected"}]
        blockers = detect_buffer_blockers(profiles, {"has_buffer_api_key": True})
        assert len(blockers) == 0

    def test_blocker_structure(self):
        blockers = detect_buffer_blockers([], {"has_buffer_api_key": False})
        for b in blockers:
            assert "blocker_type" in b
            assert "severity" in b
            assert "description" in b
            assert "operator_action_needed" in b


class TestMapBufferStatus:
    def test_buffer_to_queued(self):
        assert map_buffer_status("buffer") == "queued"

    def test_sent_to_published(self):
        assert map_buffer_status("sent") == "published"

    def test_error_to_failed(self):
        assert map_buffer_status("error") == "failed"

    def test_service_to_scheduled(self):
        assert map_buffer_status("service") == "scheduled"

    def test_unknown_status(self):
        assert map_buffer_status("something_else") == "unknown"

    def test_none_status(self):
        assert map_buffer_status(None) == "unknown"


class TestComputePublishJobSummary:
    def test_empty_list(self):
        r = compute_publish_job_summary([])
        assert r["total"] == 0

    def test_mixed_statuses(self):
        jobs = [{"status": "pending"}, {"status": "published"}, {"status": "failed"}, {"status": "pending"}]
        r = compute_publish_job_summary(jobs)
        assert r["total"] == 4
        assert r["pending"] == 2
        assert r["published"] == 1
        assert r["failed"] == 1


class TestEvaluateProfileReadiness:
    def test_ready_profile(self):
        r = evaluate_profile_readiness({
            "credential_status": "connected",
            "buffer_profile_id": "bp_123",
            "is_active": True,
            "platform": "tiktok",
        })
        assert r["ready"] is True
        assert len(r["issues"]) == 0

    def test_not_connected(self):
        r = evaluate_profile_readiness({
            "credential_status": "not_connected",
            "buffer_profile_id": "bp_123",
            "is_active": True,
        })
        assert r["ready"] is False

    def test_no_buffer_profile_id(self):
        r = evaluate_profile_readiness({
            "credential_status": "connected",
            "buffer_profile_id": None,
            "is_active": True,
        })
        assert r["ready"] is False

    def test_inactive_profile(self):
        r = evaluate_profile_readiness({
            "credential_status": "connected",
            "buffer_profile_id": "bp_123",
            "is_active": False,
        })
        assert r["ready"] is False
