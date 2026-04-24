"""Unit tests for integrations + listening engine."""

from packages.scoring.integrations_listening_engine import (
    CONNECTOR_TYPES,
    SIGNAL_TYPES,
    cluster_listening_signals,
    evaluate_connector_sync,
    extract_competitor_signals,
    generate_response_recommendations,
    route_business_signal,
)


class TestConnectorEval:
    def test_healthy(self):
        r = evaluate_connector_sync(
            {"status": "active", "credential_env_key": "KEY", "endpoint_url": "https://api.example.com"}
        )
        assert r["healthy"] is True

    def test_no_endpoint(self):
        r = evaluate_connector_sync({"status": "active", "credential_env_key": "KEY", "endpoint_url": None})
        assert r["healthy"] is False
        assert r["blocker"] == "no_endpoint"

    def test_no_credentials(self):
        r = evaluate_connector_sync({"status": "active", "credential_env_key": None, "endpoint_url": "https://x.com"})
        assert r["healthy"] is False
        assert r["blocker"] == "no_credentials"

    def test_failed_sync(self):
        r = evaluate_connector_sync(
            {"status": "active", "credential_env_key": "KEY", "endpoint_url": "https://x.com"},
            {"sync_status": "failed", "detail": "timeout"},
        )
        assert r["healthy"] is False


class TestClustering:
    def test_clusters_by_type(self):
        signals = [
            {"signal_type": "brand_mention", "raw_text": "Love this brand", "sentiment": 0.8, "relevance_score": 0.7},
            {"signal_type": "brand_mention", "raw_text": "Great product", "sentiment": 0.6, "relevance_score": 0.6},
            {"signal_type": "demand_signal", "raw_text": "Need this feature", "sentiment": 0.3, "relevance_score": 0.9},
        ]
        clusters = cluster_listening_signals(signals)
        assert len(clusters) == 2
        brand = [c for c in clusters if c["cluster_type"] == "brand_mention"]
        assert brand[0]["signal_count"] == 2

    def test_empty_signals(self):
        assert cluster_listening_signals([]) == []


class TestCompetitorExtraction:
    def test_high_opportunity(self):
        signals = [
            {
                "competitor_name": "Rival",
                "signal_type": "competitor_mention",
                "raw_text": "Disappointed with Rival, looking for alternative",
                "sentiment": -0.5,
            }
        ]
        scored = extract_competitor_signals(signals)
        assert scored[0]["opportunity_score"] > 0.5

    def test_neutral_signal(self):
        signals = [
            {
                "competitor_name": "Rival",
                "signal_type": "competitor_mention",
                "raw_text": "Rival is okay",
                "sentiment": 0.1,
            }
        ]
        scored = extract_competitor_signals(signals)
        assert scored[0]["opportunity_score"] < 0.5


class TestRouting:
    def test_demand_routes(self):
        routes = route_business_signal({"signal_type": "demand_signal", "priority": "high"})
        targets = {r["target_system"] for r in routes}
        assert "content_generation" in targets
        assert "campaign_constructor" in targets

    def test_support_pain_routes(self):
        routes = route_business_signal({"signal_type": "support_pain"})
        targets = {r["target_system"] for r in routes}
        assert "objection_mining" in targets

    def test_unknown_defaults_to_copilot(self):
        routes = route_business_signal({"signal_type": "unknown_type"})
        assert routes[0]["target_system"] == "copilot"


class TestResponseRecs:
    def test_generates_from_clusters(self):
        clusters = [{"cluster_type": "demand_signal", "signal_count": 10, "id": "c1"}]
        recs = generate_response_recommendations(clusters)
        assert len(recs) >= 2
        assert any(r["target_system"] == "content_generation" for r in recs)


class TestTypes:
    def test_signal_types(self):
        assert len(SIGNAL_TYPES) == 7

    def test_connector_types(self):
        assert len(CONNECTOR_TYPES) == 8
