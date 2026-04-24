"""Unit tests: experiment outcome loop and cross-module signal helpers."""

from __future__ import annotations

import uuid

from apps.api.services.experiment_decision_service import apply_market_timing_to_experiment_candidates
from packages.scoring.experiment_decision_engine import (
    EXP_DEC,
    apply_prior_scope_signals,
    evaluate_experiment_outcome,
    prioritize_experiment_candidates,
)


def test_apply_prior_scope_signals_promote_boosts_expected_upside():
    exps = [
        {
            "experiment_type": "offer_variant",
            "target_scope_type": "offer",
            "target_scope_id": str(uuid.uuid4()),
            "expected_upside": 0.15,
            "confidence_gap": 0.4,
            "age_days": 0,
        }
    ]
    oid = exps[0]["target_scope_id"]
    prior = [{"target_scope_type": "offer", "target_scope_id": oid, "outcome_type": "promote", "observed_uplift": 0.08}]
    out, inf = apply_prior_scope_signals([dict(e) for e in exps], prior)
    assert inf["signals_applied"] == 1
    assert out[0]["expected_upside"] > 0.15


def test_evaluate_experiment_outcome_persistable_shape():
    exp = {"experiment_type": "offer_variant", "target_scope_id": str(uuid.uuid4())}
    obs = {
        "variants": [
            {"variant_id": "a", "conversion_rate": 0.06, "sample_size": 600},
            {"variant_id": "b", "conversion_rate": 0.04, "sample_size": 580},
        ],
        "baseline_conversion_rate": 0.045,
        "days_running": 25,
    }
    r = evaluate_experiment_outcome(exp, obs)
    body = {k: v for k, v in r.items() if k != EXP_DEC}
    assert "outcome_type" in body
    assert "confidence" in body
    assert "observed_uplift" in body
    assert "recommended_next_action" in body


def test_market_timing_changes_prioritization_scores():
    experiments = [
        {
            "experiment_type": "offer_variant",
            "target_scope_type": "offer",
            "target_scope_id": str(uuid.uuid4()),
            "hypothesis": "a",
            "expected_upside": 0.14,
            "confidence_gap": 0.4,
            "age_days": 0,
        },
        {
            "experiment_type": "offer_variant",
            "target_scope_type": "offer",
            "target_scope_id": str(uuid.uuid4()),
            "hypothesis": "b",
            "expected_upside": 0.14,
            "confidence_gap": 0.4,
            "age_days": 0,
        },
    ]
    ctx = {"brand_id": "b", "total_traffic": 8000, "risk_tolerance": 0.5}
    s0 = prioritize_experiment_candidates([dict(e) for e in experiments], ctx)
    adjusted, _ = apply_market_timing_to_experiment_candidates([dict(e) for e in experiments], 0.85)
    s1 = prioritize_experiment_candidates(adjusted, ctx)
    assert s0[0]["priority_score"] != s1[0]["priority_score"]


def test_market_timing_increases_expected_upside_when_timing_high():
    exps = [
        {
            "experiment_type": "offer_variant",
            "target_scope_type": "offer",
            "target_scope_id": str(uuid.uuid4()),
            "expected_upside": 0.10,
            "confidence_gap": 0.4,
            "age_days": 0,
        }
    ]
    base = float(exps[0]["expected_upside"])
    adjusted, inf = apply_market_timing_to_experiment_candidates([dict(e) for e in exps], 1.0)
    assert inf["applied"] is True
    assert adjusted[0]["expected_upside"] > base


def test_prior_signals_influence_prioritization_order():
    sid = str(uuid.uuid4())
    experiments = [
        {
            "experiment_type": "offer_variant",
            "target_scope_type": "offer",
            "target_scope_id": sid,
            "hypothesis": "h1",
            "expected_upside": 0.12,
            "confidence_gap": 0.5,
            "age_days": 0,
        },
        {
            "experiment_type": "offer_variant",
            "target_scope_type": "offer",
            "target_scope_id": str(uuid.uuid4()),
            "hypothesis": "h2",
            "expected_upside": 0.12,
            "confidence_gap": 0.5,
            "age_days": 0,
        },
    ]
    prior = [{"target_scope_type": "offer", "target_scope_id": sid, "outcome_type": "promote", "observed_uplift": 0.1}]
    adjusted, _ = apply_prior_scope_signals([dict(e) for e in experiments], prior)
    scored = prioritize_experiment_candidates(adjusted, {"brand_id": "b", "total_traffic": 5000, "risk_tolerance": 0.5})
    assert scored[0]["priority_score"] >= scored[1]["priority_score"]
