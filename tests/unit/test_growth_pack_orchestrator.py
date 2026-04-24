"""Unit tests for growth pack orchestrator (deterministic)."""

from packages.scoring.growth_pack.orchestrator import (
    build_cannibalization_pairs,
    build_capital_plan,
    build_platform_allocation_rows,
    build_portfolio_output,
    canonical_fields_from_command,
)
from packages.scoring.growth_pack.platform_os import normalize_platform, platform_spec


def test_canonical_fields_populates_financials():
    cmd = {
        "command_type": "launch_account",
        "priority": 80,
        "title": "T",
        "exact_instruction": "Do X",
        "expected_upside": 400,
        "expected_cost": 100,
        "execution_spec": {"platform": "youtube", "content_role": "experimental_satellite"},
        "platform_fit": {"platform": "youtube", "fit_score": 0.9},
        "niche_fit": {"niche": "finance", "sub_niche": "credit"},
        "monetization_path": {"primary_method": "affiliate"},
        "cannibalization_analysis": {"risk": 0.3},
        "success_threshold": {"metric": "m"},
        "failure_threshold": {"metric": "f"},
        "blocking_factors": ["a"],
        "first_week_plan": [],
    }
    cf = canonical_fields_from_command(cmd)
    assert cf["command_priority"] == 80
    assert cf["platform"] == "youtube"
    assert cf["niche"] == "finance"
    assert cf["expected_revenue_max"] >= cf["expected_revenue_min"]
    assert cf["risk_score"] == 0.3


def test_platform_allocation_seven_platforms():
    rows = build_platform_allocation_rows(
        {"youtube": 1},
        {"recommended_account_count": 3, "incremental_profit_new_account": 50, "expansion_confidence": 0.6},
        "finance",
    )
    assert len(rows) == 7
    plats = {r["platform"] for r in rows}
    assert "tiktok" in plats and "instagram" in plats and "reddit" in plats


def test_cannibalization_pair_same_platform():
    accs = [
        {"id": "u1", "platform": "youtube", "niche_focus": "personal finance tips"},
        {"id": "u2", "platform": "youtube", "niche_focus": "finance tips personal"},
    ]
    pairs = build_cannibalization_pairs(accs)
    assert len(pairs) >= 1


def test_capital_holdback_higher_when_constrained():
    loose = build_capital_plan(10000, {"youtube": 5000}, False)
    tight = build_capital_plan(10000, {"youtube": 5000}, True)
    assert tight["holdback_budget"] >= loose["holdback_budget"]


def test_portfolio_output_has_platform_keys():
    out = build_portfolio_output(
        [{"id": "x", "platform": "youtube", "posting_capacity_per_day": 2, "fatigue_score": 0.1}],
        {"youtube": 1},
    )
    assert "youtube" in out["per_platform_output_json"]


def test_normalize_platform_x_to_twitter():
    assert normalize_platform("X") == "twitter"


def test_normalize_platform_tiktok():
    assert normalize_platform("tiktok") == "tiktok"
    assert normalize_platform("TikTok") == "tiktok"


def test_platform_spec_has_cadence():
    spec = platform_spec("instagram")
    assert "posting_cadence_posts_per_week" in spec


def test_tiktok_platform_spec_complete():
    spec = platform_spec("tiktok")
    assert "posting_cadence_posts_per_week" in spec
    assert spec["posting_cadence_posts_per_week"]["min"] == 7
    assert "recommended_roles" in spec
    assert "trend_capture" in spec["recommended_roles"]
    assert "monetization_styles" in spec
    assert "warmup_cadence" in spec
    assert "ramp_behavior" in spec
    assert "scale_ready_conditions" in spec
    assert "max_safe_output_per_day" in spec
    assert spec["max_safe_output_per_day"] == 4
    assert "spam_fatigue_signals" in spec
    assert "account_health_signals" in spec
    assert "derivative_style_guidance" in spec


def test_tiktok_in_platform_allocation():
    rows = build_platform_allocation_rows(
        {"tiktok": 2, "youtube": 1},
        {"recommended_account_count": 5, "incremental_profit_new_account": 100, "expansion_confidence": 0.7},
        "personal finance",
    )
    plats = {r["platform"] for r in rows}
    assert "tiktok" in plats
    tiktok_row = next(r for r in rows if r["platform"] == "tiktok")
    assert tiktok_row["current_account_count"] == 2
    assert tiktok_row["rationale_json"]["platform_os"]["recommended_roles"] is not None


def test_all_seven_platforms_have_specs():
    from packages.scoring.growth_pack.platform_os import PLATFORM_SPECS
    expected = {"tiktok", "instagram", "youtube", "twitter", "reddit", "linkedin", "facebook"}
    assert set(PLATFORM_SPECS.keys()) == expected


def test_all_platforms_have_warmup_cadence():
    from packages.scoring.growth_pack.platform_os import PLATFORM_SPECS
    for plat, spec in PLATFORM_SPECS.items():
        assert "warmup_cadence" in spec, f"{plat} missing warmup_cadence"
        assert "week_1" in spec["warmup_cadence"], f"{plat} warmup_cadence missing week_1"


def test_all_platforms_have_scale_ready_conditions():
    from packages.scoring.growth_pack.platform_os import PLATFORM_SPECS
    for plat, spec in PLATFORM_SPECS.items():
        assert "scale_ready_conditions" in spec, f"{plat} missing scale_ready_conditions"
        assert len(spec["scale_ready_conditions"]) >= 2, f"{plat} has too few scale_ready_conditions"


def test_all_platforms_have_max_safe_output():
    from packages.scoring.growth_pack.platform_os import PLATFORM_SPECS
    for plat, spec in PLATFORM_SPECS.items():
        assert "max_safe_output_per_day" in spec, f"{plat} missing max_safe_output_per_day"
        assert spec["max_safe_output_per_day"] >= 1
