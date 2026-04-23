"""Unit tests for objection mining engine — pure functions, no DB."""
import pytest
from packages.scoring.objection_mining_engine import (
    OBJECTION_TYPES, extract_objections, cluster_objections,
    generate_responses, build_priority_report,
)


class TestObjectionTypes:
    def test_all_9_types(self):
        assert len(OBJECTION_TYPES) == 9
        for t in ("price", "trust", "complexity", "timing", "competitor", "relevance", "proof", "identity", "skepticism"):
            assert t in OBJECTION_TYPES


class TestExtraction:
    def test_price_objection(self):
        texts = [{"text": "This is way too expensive for what you get", "source_type": "comment"}]
        signals = extract_objections(texts)
        assert len(signals) == 1
        assert signals[0]["objection_type"] == "price"
        assert signals[0]["severity"] > 0

    def test_trust_objection(self):
        signals = extract_objections([{"text": "Is this even legit or just another scam?", "source_type": "comment"}])
        assert len(signals) == 1
        assert signals[0]["objection_type"] == "trust"

    def test_complexity_objection(self):
        signals = extract_objections([{"text": "This looks way too complicated for beginners", "source_type": "comment"}])
        assert signals[0]["objection_type"] == "complexity"

    def test_competitor_objection(self):
        signals = extract_objections([{"text": "There's a better option out there vs this", "source_type": "comment"}])
        assert signals[0]["objection_type"] == "competitor"

    def test_proof_objection(self):
        signals = extract_objections([{"text": "Show me the proof and results before I buy", "source_type": "comment"}])
        assert signals[0]["objection_type"] == "proof"

    def test_skepticism_objection(self):
        signals = extract_objections([{"text": "This sounds too good to be true, I doubt it works", "source_type": "comment"}])
        assert signals[0]["objection_type"] == "skepticism"

    def test_no_objection_in_positive_text(self):
        signals = extract_objections([{"text": "Great video, love your content!", "source_type": "comment"}])
        assert len(signals) == 0

    def test_short_text_skipped(self):
        signals = extract_objections([{"text": "ok", "source_type": "comment"}])
        assert len(signals) == 0

    def test_monetization_impact_scored(self):
        signals = extract_objections([{"text": "Way too expensive, can't afford it", "source_type": "comment", "offer_id": "abc"}])
        assert signals[0]["monetization_impact"] > 0.8

    def test_multiple_texts(self):
        texts = [
            {"text": "Too expensive for me", "source_type": "comment"},
            {"text": "Is this a scam? Not sure I trust this", "source_type": "comment"},
            {"text": "Love this product!", "source_type": "comment"},
        ]
        signals = extract_objections(texts)
        assert len(signals) == 2
        types = {s["objection_type"] for s in signals}
        assert "price" in types
        assert "trust" in types


class TestClustering:
    def test_clusters_by_type(self):
        signals = [
            {"objection_type": "price", "severity": 0.7, "monetization_impact": 0.9, "extracted_objection": "too expensive"},
            {"objection_type": "price", "severity": 0.6, "monetization_impact": 0.9, "extracted_objection": "can't afford"},
            {"objection_type": "trust", "severity": 0.8, "monetization_impact": 0.85, "extracted_objection": "looks like scam"},
        ]
        clusters = cluster_objections(signals)
        assert len(clusters) == 2
        price_cluster = [c for c in clusters if c["objection_type"] == "price"]
        assert price_cluster[0]["signal_count"] == 2

    def test_empty_signals(self):
        assert cluster_objections([]) == []

    def test_sorted_by_impact(self):
        signals = [
            {"objection_type": "timing", "severity": 0.3, "monetization_impact": 0.3, "extracted_objection": "not now"},
            {"objection_type": "price", "severity": 0.8, "monetization_impact": 0.9, "extracted_objection": "expensive"},
        ]
        clusters = cluster_objections(signals)
        assert clusters[0]["objection_type"] == "price"


class TestResponses:
    def test_generates_responses(self):
        clusters = [{"objection_type": "price", "avg_monetization_impact": 0.9, "signal_count": 5, "id": "c1"}]
        responses = generate_responses(clusters)
        assert len(responses) >= 1
        assert any(r["target_channel"] == "content_brief" for r in responses)

    def test_priority_based_on_impact(self):
        clusters = [{"objection_type": "price", "avg_monetization_impact": 0.9, "signal_count": 5, "id": "c1"}]
        responses = generate_responses(clusters)
        assert responses[0]["priority"] == "critical"


class TestPriorityReport:
    def test_builds_report(self):
        clusters = [
            {"objection_type": "price", "signal_count": 10, "avg_monetization_impact": 0.9, "recommended_response_angle": "value demo"},
            {"objection_type": "trust", "signal_count": 5, "avg_monetization_impact": 0.85, "recommended_response_angle": "social proof"},
        ]
        report = build_priority_report(clusters, 15)
        assert report["total_signals"] == 15
        assert report["total_clusters"] == 2
        assert report["highest_impact_type"] == "price"
        assert len(report["top_objections"]) == 2
