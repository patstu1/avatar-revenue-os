"""Unit tests for revenue leak engine."""
from packages.scoring.revenue_leak_engine import (
    LEAK_TYPES,
    cluster_leaks,
    detect_leaks,
    estimate_total_loss,
    generate_corrections,
    prioritize_leaks,
)


class TestLeakTypes:
    def test_14_types(self):
        assert len(LEAK_TYPES) == 14


class TestDetection:
    def test_high_impressions_low_ctr(self):
        data = {"content_items": [{"id": "c1", "impressions": 10000, "clicks": 50, "engagement_rate": 0.01, "revenue": 0, "conversion_rate": 0.005}]}
        leaks = detect_leaks(data)
        assert any(l["leak_type"] == "high_impressions_low_ctr" for l in leaks)

    def test_high_clicks_low_conversion(self):
        data = {"content_items": [{"id": "c1", "impressions": 5000, "clicks": 200, "engagement_rate": 0.04, "revenue": 0, "conversion_rate": 0.001}]}
        leaks = detect_leaks(data)
        assert any(l["leak_type"] == "high_clicks_low_conversion" for l in leaks)

    def test_high_engagement_low_monetization(self):
        data = {"content_items": [{"id": "c1", "impressions": 5000, "clicks": 100, "engagement_rate": 0.08, "revenue": 2, "conversion_rate": 0.02}]}
        leaks = detect_leaks(data)
        assert any(l["leak_type"] == "high_engagement_low_monetization" for l in leaks)

    def test_underused_winner(self):
        data = {"offers": [{"id": "o1", "rank_score": 0.8, "usage_count": 1}]}
        leaks = detect_leaks(data)
        assert any(l["leak_type"] == "underused_winner" for l in leaks)

    def test_blocked_provider(self):
        data = {"provider_blockers": [{"id": "b1", "name": "stripe"}]}
        leaks = detect_leaks(data)
        assert any(l["leak_type"] == "blocked_provider" for l in leaks)

    def test_under_monetized_account(self):
        data = {"accounts": [{"id": "a1", "state": "scaling", "revenue": 3}]}
        leaks = detect_leaks(data)
        assert any(l["leak_type"] == "under_monetized_account" for l in leaks)

    def test_clean_system(self):
        data = {"content_items": [{"id": "c1", "impressions": 100, "clicks": 10, "engagement_rate": 0.02, "revenue": 50, "conversion_rate": 0.1}]}
        leaks = detect_leaks(data)
        assert len(leaks) == 0


class TestClustering:
    def test_clusters_by_type(self):
        leaks = [
            {"leak_type": "high_clicks_low_conversion", "estimated_revenue_loss": 50, "confidence": 0.8},
            {"leak_type": "high_clicks_low_conversion", "estimated_revenue_loss": 30, "confidence": 0.7},
            {"leak_type": "blocked_provider", "estimated_revenue_loss": 100, "confidence": 0.9},
        ]
        clusters = cluster_leaks(leaks)
        assert len(clusters) == 2
        assert clusters[0]["total_loss"] >= clusters[1]["total_loss"]


class TestEstimation:
    def test_total_loss(self):
        leaks = [{"leak_type": "a", "affected_scope": "content", "estimated_revenue_loss": 50}, {"leak_type": "b", "affected_scope": "offer", "estimated_revenue_loss": 30}]
        est = estimate_total_loss(leaks)
        assert est["total_estimated_loss"] == 80
        assert "a" in est["by_leak_type"]


class TestCorrections:
    def test_generates_corrections(self):
        leaks = [{"leak_type": "high_clicks_low_conversion", "severity": "critical"}, {"leak_type": "underused_winner", "severity": "high"}]
        corrections = generate_corrections(leaks)
        assert len(corrections) == 2
        assert corrections[0]["priority"] == "critical"


class TestPrioritization:
    def test_prioritizes_by_score(self):
        leaks = [
            {"leak_type": "a", "estimated_revenue_loss": 100, "severity": "critical", "confidence": 0.9},
            {"leak_type": "b", "estimated_revenue_loss": 10, "severity": "low", "confidence": 0.3},
        ]
        prioritized = prioritize_leaks(leaks)
        assert prioritized[0]["priority_score"] > prioritized[1]["priority_score"]
