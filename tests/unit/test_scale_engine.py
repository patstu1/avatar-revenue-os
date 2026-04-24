"""Unit tests for Phase 5 scale scoring engine."""

import pytest

from packages.scoring.scale import (
    EXPANSION_BEATS_EXISTING_RATIO,
    NEW_ACCOUNT_OVERHEAD_USD,
    RK_ADD_EXPERIMENTAL,
    RK_ADD_OFFER_FIRST,
    VOLUME_LIFT_FACTOR,
    AccountScaleSnapshot,
    compute_audience_segment_separation,
    compute_cannibalization_risk,
    compute_incremental_profit_more_volume,
    compute_incremental_profit_new_account,
    compute_offer_performance_score,
    compute_scale_readiness_score,
    niche_jaccard,
    run_scale_engine,
)


def _snap(**kw) -> AccountScaleSnapshot:
    base = dict(
        account_id="x",
        platform="youtube",
        username="@u",
        niche_focus="personal finance",
        sub_niche_focus="budget",
        revenue=1000.0,
        profit=400.0,
        profit_per_post=20.0,
        revenue_per_mille=10.0,
        ctr=0.03,
        conversion_rate=0.03,
        follower_growth_rate=0.02,
        fatigue_score=0.2,
        saturation_score=0.2,
        originality_drift_score=0.1,
        diminishing_returns_score=0.2,
        posting_capacity_per_day=2,
        account_health="healthy",
        offer_performance_score=0.7,
        scale_role=None,
        impressions_rollup=1000,
    )
    base.update(kw)
    return AccountScaleSnapshot(**base)


def test_niche_jaccard():
    assert niche_jaccard("personal finance tips", "finance personal") > 0.5
    assert niche_jaccard("crypto", "cooking") == 0.0


def test_offer_performance_score():
    s = compute_offer_performance_score([{"epc": 3.0, "conversion_rate": 0.05}])
    assert 0 < s <= 1.0


def test_cannibalization_risk_overlapping_niches():
    a = _snap(account_id="1", platform="tiktok", niche_focus="budget apps")
    b = _snap(account_id="2", platform="tiktok", niche_focus="budget planning apps")
    r = compute_cannibalization_risk([a, b])
    assert r > 0.15


def test_audience_segment_separation_inverse():
    a = _snap(account_id="1")
    b = _snap(account_id="2", platform="instagram")
    sep = compute_audience_segment_separation([a, b])
    assert 0 <= sep <= 1


def test_incremental_profit_volume_positive():
    a = _snap(profit_per_post=10.0, posting_capacity_per_day=2, diminishing_returns_score=0.0)
    v = compute_incremental_profit_more_volume([a])
    assert v > 0
    assert v == pytest.approx(2 * VOLUME_LIFT_FACTOR * 10.0, rel=0.01)


def test_incremental_new_account_net_of_overhead():
    a = _snap(profit_per_post=50.0, posting_capacity_per_day=3)
    inc = compute_incremental_profit_new_account([a], expansion_confidence=0.8, cannibalization_risk=0.1)
    assert inc > 0
    baseline_week = 50.0 * min(3, 3) * 7
    raw = baseline_week * 0.8 * 0.9
    assert inc == pytest.approx(max(0.0, raw - NEW_ACCOUNT_OVERHEAD_USD), rel=0.01)


def test_scale_readiness_in_range():
    score, parts = compute_scale_readiness_score([_snap()], 0.8)
    assert 0 <= score <= 100
    assert "per_account_readiness_avg" in parts


def test_run_scale_engine_prefers_offer_fix_when_thin_catalog():
    res = run_scale_engine([], [], 0, "finance", funnel_weak=False, weak_offer_diversity=True)
    assert res.recommendation_key == RK_ADD_OFFER_FIRST


def test_run_scale_engine_single_account_experimental():
    res = run_scale_engine(
        [_snap(account_id="a1")],
        [{"epc": 2.0, "conversion_rate": 0.04}, {"epc": 1.5, "conversion_rate": 0.03}],
        50_000,
        "finance",
        funnel_weak=False,
        weak_offer_diversity=False,
    )
    assert res.recommendation_key == RK_ADD_EXPERIMENTAL


def test_expansion_vs_exploitation_ratio_constant():
    assert EXPANSION_BEATS_EXISTING_RATIO == pytest.approx(1.15)
