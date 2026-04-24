"""Unit tests for growth pack gatekeeper (no DB)."""

from packages.scoring.growth_commander import generate_growth_commands
from packages.scoring.growth_pack.gatekeeper import (
    apply_gatekeeper_to_commands,
    compute_gatekeeper_inputs,
    pick_primary_gate,
)


def test_compute_gatekeeper_inputs_shapes():
    gk = compute_gatekeeper_inputs(
        accounts=[{"posting_capacity_per_day": 4, "fatigue_score": 0.5}],
        offer_count=2,
        sponsor_profile_count=2,
        sponsor_open_deal_count=1,
        audience_segment_total_estimated_size=1000,
        readiness={"launch_readiness_score": 70},
        trust_avg=62.0,
        leak_count=1,
        scale_rec={"incremental_profit_new_account": 500, "incremental_profit_existing_push": 200},
    )
    assert 0 <= gk["owned_audience_readiness_score"] <= 100
    assert gk["sponsor_profile_count"] == 2
    assert "input_class" in gk


def test_pick_primary_gate_order_funnel_before_overlap():
    gk = compute_gatekeeper_inputs(
        accounts=[{"posting_capacity_per_day": 2, "fatigue_score": 0}],
        offer_count=2,
        sponsor_profile_count=3,
        sponsor_open_deal_count=2,
        audience_segment_total_estimated_size=500,
        readiness={"launch_readiness_score": 40},
        trust_avg=70.0,
        leak_count=0,
        scale_rec={"incremental_profit_new_account": 400, "incremental_profit_existing_push": 100},
    )
    key, _ = pick_primary_gate(gk, has_high_cannibalization=True)
    assert key == "funnel"


def test_apply_gatekeeper_defers_launch():
    scale_rec = {
        "recommendation_key": "monitor",
        "incremental_profit_new_account": 300,
        "incremental_profit_existing_push": 50,
        "id": None,
        "recommended_account_count": 2,
        "expansion_confidence": 0.7,
        "best_next_account": {},
    }
    cmds = generate_growth_commands(
        scale_rec,
        [
            {
                "id": "c1",
                "candidate_type": "growth",
                "primary_platform": "youtube",
                "niche": "x",
                "cannibalization_risk": 0.2,
                "audience_separation_score": 0.6,
                "confidence": 0.8,
                "urgency": 60.0,
                "supporting_reasons": [],
                "launch_blockers": [],
            }
        ],
        [],
        {"launch_readiness_score": 40, "recommended_action": "fix"},
        [],
        [{"id": "o1", "name": "a"}, {"id": "o2", "name": "b"}],
        "niche",
        60.0,
        0,
        [],
    )
    gk = compute_gatekeeper_inputs(
        accounts=[],
        offer_count=2,
        sponsor_profile_count=2,
        sponsor_open_deal_count=1,
        audience_segment_total_estimated_size=0,
        readiness={"launch_readiness_score": 40},
        trust_avg=60.0,
        leak_count=0,
        scale_rec=scale_rec,
    )
    out = apply_gatekeeper_to_commands(cmds, gk, has_high_cannibalization=False, brand_niche="niche")
    assert not any(c.get("command_type") == "launch_account" for c in out)
    assert any("DEFERRED EXPANSION" in c.get("title", "") for c in out)
