"""Phase C (MXP): recovery, reputation, market timing — pure engine checks and worker registration.

Persistence tests live in tests/integration/test_mxp_phase_c_persistence.py (requires PostgreSQL).
"""
from __future__ import annotations

import pytest

from packages.scoring.market_timing_engine import evaluate_market_timing
from packages.scoring.recovery_engine import detect_recovery_incidents, recommend_recovery_actions
from packages.scoring.reputation_engine import assess_reputation
from workers.mxp_worker.tasks import (
    recompute_all_market_timing,
    recompute_all_recovery_incidents,
    recompute_all_reputation,
)


def test_email_deliverability_incident_detected():
    state = {
        "email_deliverability_issue": {"metric_value": 0.1, "scope_type": "brand"},
    }
    results = detect_recovery_incidents(state, {})
    assert any(r["incident_type"] == "email_deliverability_issue" for r in results)


def test_recovery_actions_include_force_guarded_review():
    incidents = [
        {
            "incident_type": "conversion_decline",
            "severity": "high",
            "scope_type": "brand",
        },
    ]
    actions = recommend_recovery_actions(incidents, {})
    types = {a["action_type"] for a in actions}
    assert "force_guarded_review" in types


def test_market_timing_macro_cpm_influences_score():
    ctx = {
        "niche": "tech",
        "month": 3,
        "audience_size": 10000,
        "avg_monthly_revenue": 5000,
        "active_offer_count": 2,
    }
    high_cpm_cost = evaluate_market_timing(
        ctx,
        [{"signal_type": "cpm_index", "value": 0.9, "source": "test"}],
    )
    low_cpm_cost = evaluate_market_timing(
        ctx,
        [{"signal_type": "cpm_index", "value": 0.15, "source": "test"}],
    )
    hi = next((x["timing_score"] for x in low_cpm_cost if x["market_category"] == "cpm_friendly"), None)
    lo = next((x["timing_score"] for x in high_cpm_cost if x["market_category"] == "cpm_friendly"), None)
    assert hi is not None and lo is not None
    assert hi >= lo


def test_reputation_mitigation_persist_shape():
    brand_data = {
        "niche": "finance",
        "platform_warnings": 1,
        "disclosure_policy": False,
        "sponsor_names": ["A", "A"],
        "audience_size": 5000,
        "avg_engagement_rate": 0.01,
    }
    account_signals = [
        {
            "platform": "youtube",
            "follower_delta": -10,
            "unfollow_rate": 0.05,
            "strike_count": 1,
            "engagement_rate": 0.02,
            "bot_follower_pct": 0.2,
            "comment_texts": ["scam", "unsubscribe", "guarantee cure"],
        },
    ]
    content_signals = [
        {
            "title": "Sponsored post",
            "description": "",
            "has_disclosure": False,
            "claims": ["100% results guaranteed"],
            "engagement_rate": 0.02,
            "generic_comment_pct": 0.5,
            "sponsor_name": "Acme",
        },
    ]
    result = assess_reputation(brand_data, account_signals, content_signals)
    assert result["recommended_mitigation"]
    assert any("risk_type" in m for m in result["recommended_mitigation"])


def test_mxp_phase_c_workers_registered():
    assert recompute_all_recovery_incidents.name.endswith("recompute_all_recovery_incidents")
    assert recompute_all_reputation.name.endswith("recompute_all_reputation")
    assert recompute_all_market_timing.name.endswith("recompute_all_market_timing")
