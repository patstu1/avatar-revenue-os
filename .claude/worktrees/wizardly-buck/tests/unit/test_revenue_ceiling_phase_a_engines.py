"""Unit tests for Revenue Ceiling Phase A scoring engines."""

import pytest

from packages.scoring.revenue_ceiling_phase_a_engines import (
    SEQUENCE_TYPES,
    build_offer_ladder_for_opportunity,
    build_sequence,
    detect_funnel_leaks,
    generate_all_message_sequences,
    generate_offer_ladders,
    generate_owned_audience_assets,
    owned_audience_objective_for_family,
    synthesize_owned_audience_events,
    compute_funnel_stage_metrics,
)


def test_offer_ladder_includes_paths_and_economics():
    row = build_offer_ladder_for_opportunity(
        "offer:x|content:y",
        "Test Offer",
        "My video title",
        epc=2.0,
        cvr=0.02,
        aov=50.0,
    )
    assert row["opportunity_key"] == "offer:x|content:y"
    assert "upsell_path" in row and "steps" in row["upsell_path"]
    assert "retention_path" in row
    assert "fallback_path" in row
    assert row["expected_first_conversion_value"] > 0
    assert row["expected_downstream_value"] >= row["expected_first_conversion_value"]
    assert 0 < row["confidence"] <= 0.95
    assert row["friction_level"] in ("low", "medium", "high")


def test_generate_offer_ladders_no_content_uses_offer_fallback():
    offers = [{"id": "o1", "name": "A", "epc": 1.5, "conversion_rate": 0.02, "average_order_value": 40}]
    rows = generate_offer_ladders("niche", offers, [])
    assert len(rows) == 1
    assert "no_content" in rows[0]["opportunity_key"]


def test_owned_audience_objective_routing():
    assert owned_audience_objective_for_family("how_to", 0.7) == "direct_sale"
    assert owned_audience_objective_for_family("how_to", 0.2) == "owned_capture"
    assert owned_audience_objective_for_family("how_to", 0.5) == "hybrid"


def test_generate_owned_audience_assets_covers_types():
    assets = generate_owned_audience_assets("finance", ["how_to", "review"])
    types = {a["asset_type"] for a in assets}
    assert "newsletter" in types and "lead_magnet" in types
    assert all("cta_variants" in a for a in assets)


def test_synthesize_events_links_content_to_assets():
    content = [{"id": "c1", "title": "T1"}, {"id": "c2", "title": "T2"}]
    ev = synthesize_owned_audience_events(content, ["a1", "a2"])
    assert len(ev) == 2
    assert ev[0]["content_item_id"] == "c1"
    assert ev[0]["asset_id"] in ("a1", "a2")


def test_synthesize_events_empty_assets_still_emits():
    ev = synthesize_owned_audience_events([{"id": "c1", "title": "x"}], [])
    assert len(ev) == 1
    assert ev[0]["asset_id"] is None


def test_generate_all_message_sequences_covers_types_and_channels():
    seqs = generate_all_message_sequences("voice")
    assert len(seqs) == len(SEQUENCE_TYPES)
    channels = {m["channel"] for m, _ in seqs}
    assert channels <= {"email", "sms", "hybrid"}
    for meta, steps in seqs:
        assert meta["sequence_type"] in SEQUENCE_TYPES
        assert len(steps) >= 1
        hybrid_ok = all(s["channel"] in ("email", "sms") for s in steps)
        assert hybrid_ok


def test_build_sequence_hybrid_alternates_channels():
    meta, steps = build_sequence("welcome", "hybrid", "brand", sponsor_safe=False)
    assert meta["channel"] == "hybrid"
    chans = [s["channel"] for s in steps]
    assert set(chans) <= {"email", "sms"}


def test_funnel_metrics_and_leak_detection():
    metrics = compute_funnel_stage_metrics("general")
    assert len(metrics) >= 5
    leaks = detect_funnel_leaks(metrics, "general")
    assert len(leaks) >= 1
    L = leaks[0]
    for k in ("leak_type", "severity", "affected_funnel_stage", "recommended_fix", "confidence", "urgency"):
        assert k in L
