"""Unit tests for Growth Commander engine."""

from packages.scoring.growth_commander import (
    generate_growth_commands, assess_portfolio_balance, compute_portfolio_directive,
    find_whitespace, map_content_role, rank_commands, COMMAND_TYPES,
)
from packages.scoring.scale import RK_ADD_NICHE_SPINOFF, RK_ADD_PLATFORM_SPECIFIC


def _scale_rec(**kw):
    base = {"recommendation_key": "add_experimental_account", "scale_readiness_score": 72,
            "incremental_profit_new_account": 180, "incremental_profit_existing_push": 22,
            "explanation": "Expansion profitable.", "best_next_account": {}, "id": "rec1"}
    base.update(kw)
    return base


def _candidate(**kw):
    base = {"id": "cand1", "candidate_type": "experimental_account",
            "primary_platform": "tiktok", "niche": "finance", "sub_niche": "budget",
            "language": "en", "geography": "US", "monetization_path": "affiliate",
            "posting_strategy": "2/day", "expected_monthly_revenue_min": 100,
            "expected_monthly_revenue_max": 300, "expected_launch_cost": 150,
            "expected_time_to_signal_days": 21, "expected_time_to_profit_days": 60,
            "cannibalization_risk": 0.15, "audience_separation_score": 0.85,
            "confidence": 0.7, "urgency": 65, "supporting_reasons": ["Scale engine says expand"],
            "launch_blockers": []}
    base.update(kw)
    return base


def _accounts():
    return [{"id": "a1", "platform": "youtube", "geography": "US", "language": "en",
             "niche_focus": "finance", "username": "@flagship", "follower_count": 10000,
             "fatigue_score": 0.2, "saturation_score": 0.15, "originality_drift_score": 0.1,
             "account_health": "healthy", "profit_per_post": 20, "revenue_per_mille": 10,
             "posting_capacity_per_day": 2}]


def test_launch_command_generated_from_candidate():
    cmds = generate_growth_commands(
        _scale_rec(), [_candidate()], [], {"launch_readiness_score": 75, "recommended_action": "launch_now"},
        _accounts(), [{"id": "o1", "name": "Offer"}], "finance", 70, 2, [],
    )
    launch_cmds = [c for c in cmds if c["command_type"] == "launch_account"]
    assert len(launch_cmds) == 1
    lc = launch_cmds[0]
    assert lc["comparison"]["incremental_new"] > 0
    assert lc["comparison"]["winner"] == "new_account"
    assert lc["cannibalization_analysis"]["risk"] == 0.15
    assert lc["success_threshold"]["metric"] == "weekly_profit"
    assert lc["failure_threshold"]["action_on_failure"] == "pause_account"
    assert len(lc["first_week_plan"]) == 7
    assert lc["confidence"] > 0
    assert lc["platform_fit"]["platform"] == "tiktok"


def test_funnel_fix_before_launch():
    cmds = generate_growth_commands(
        _scale_rec(), [_candidate()],
        [{"blocker_type": "weak_funnel", "severity": "high", "title": "Leaking funnel"}],
        {"launch_readiness_score": 75, "recommended_action": "launch_now"},
        _accounts(), [{"id": "o1", "name": "Offer"}], "finance", 70, 8, [],
    )
    assert cmds[0]["command_type"] == "fix_funnel_first"
    assert cmds[0]["priority"] > 80


def test_increase_output_when_exploitation_wins():
    cmds = generate_growth_commands(
        _scale_rec(incremental_profit_new_account=10, incremental_profit_existing_push=50),
        [], [], None, _accounts(), [{"id": "o1", "name": "Offer"}], "finance", 70, 0, [],
    )
    types = {c["command_type"] for c in cmds}
    assert "increase_output" in types
    inc = next(c for c in cmds if c["command_type"] == "increase_output")
    assert inc["comparison"]["winner"] == "more_output"


def test_suppress_unhealthy_account():
    accts = _accounts()
    accts[0]["account_health"] = "critical"
    cmds = generate_growth_commands(
        _scale_rec(), [], [], None, accts, [], "finance", 70, 0, [],
    )
    types = {c["command_type"] for c in cmds}
    assert "suppress_account" in types


def test_do_nothing_when_no_candidates_or_issues():
    cmds = generate_growth_commands(
        _scale_rec(recommendation_key="monitor", incremental_profit_new_account=0, incremental_profit_existing_push=0),
        [], [], {"launch_readiness_score": 60, "recommended_action": "monitor"},
        [], [{"id": "o1"}, {"id": "o2"}], "finance", 70, 0, [],
    )
    assert any(c["command_type"] == "do_nothing" for c in cmds)


def test_add_offer_first():
    cmds = generate_growth_commands(
        _scale_rec(recommendation_key="add_new_offer_before_adding_account"),
        [], [], None, _accounts(), [{"id": "o1", "name": "Single"}], "finance", 70, 0, [],
    )
    types = {c["command_type"] for c in cmds}
    assert "add_offer_first" in types


def test_comparison_mandatory_on_launch():
    cmds = generate_growth_commands(
        _scale_rec(), [_candidate()], [], {"launch_readiness_score": 75},
        _accounts(), [{"id": "o1"}], "finance", 70, 2, [],
    )
    for c in cmds:
        if c["command_type"] == "launch_account":
            assert "incremental_new" in c["comparison"]
            assert "incremental_existing" in c["comparison"]
            assert "winner" in c["comparison"]


def test_cannibalization_analysis_on_launch():
    cmds = generate_growth_commands(
        _scale_rec(), [_candidate(cannibalization_risk=0.7)], [],
        {"launch_readiness_score": 75}, _accounts(), [], "finance", 70, 0, [],
    )
    lc = next(c for c in cmds if c["command_type"] == "launch_account")
    assert lc["cannibalization_analysis"]["risk"] == 0.7
    assert "overlap" in lc["cannibalization_analysis"]["mitigation"].lower() or "niche" in lc["cannibalization_analysis"]["mitigation"].lower()


def test_rank_commands_fixes_before_launches():
    cmds = [
        {"command_type": "launch_account", "priority": 85},
        {"command_type": "fix_funnel_first", "priority": 95},
        {"command_type": "increase_output", "priority": 75},
    ]
    ranked = rank_commands(cmds)
    assert ranked[0]["command_type"] == "fix_funnel_first"
    assert ranked[1]["command_type"] == "launch_account"
    assert ranked[2]["command_type"] == "increase_output"


def test_portfolio_balance_detects_absent():
    balance = assess_portfolio_balance([{"platform": "youtube"}])
    assert "tiktok" in balance["absent_platforms"]
    assert "instagram" in balance["absent_platforms"]


def test_portfolio_balance_detects_overbuilt():
    accts = [{"platform": "youtube"}] * 4 + [{"platform": "tiktok"}]
    balance = assess_portfolio_balance(accts)
    assert len(balance["overbuilt"]) >= 1
    assert balance["overbuilt"][0]["platform"] == "youtube"


def test_whitespace_finds_platform_gaps():
    ws = find_whitespace([{"platform": "youtube", "niche_focus": "finance", "geography": "US"}], "finance", [])
    platforms = {w["platform"] for w in ws}
    assert "tiktok" in platforms
    assert "youtube" not in platforms


def test_whitespace_includes_geo_expansion():
    ws = find_whitespace(
        [{"platform": "youtube", "niche_focus": "finance", "geography": "US"}],
        "finance",
        [{"target_geography": "EU-5", "target_language": "en", "estimated_revenue_potential": 4800}],
    )
    geo_ws = [w for w in ws if w.get("geography") == "EU-5"]
    assert len(geo_ws) >= 1


def _acct_row(**kw):
    base = {"id": "a1", "platform": "youtube", "geography": "US", "language": "en",
            "niche_focus": "finance", "username": "@flagship", "follower_count": 10000,
            "fatigue_score": 0.2, "saturation_score": 0.15, "originality_drift_score": 0.1,
            "account_health": "healthy", "profit_per_post": 20, "revenue_per_mille": 10,
            "posting_capacity_per_day": 2}
    base.update(kw)
    return base


def test_shift_platform_from_scale_key():
    cmds = generate_growth_commands(
        _scale_rec(
            recommendation_key=RK_ADD_PLATFORM_SPECIFIC,
            incremental_profit_new_account=100,
            incremental_profit_existing_push=40,
            best_next_account={"platform_suggestion": "tiktok", "rationale": "Diversify platforms."},
        ),
        [], [], None, [_acct_row()], [{"id": "o1"}, {"id": "o2"}], "finance", 70, 0, [],
    )
    assert any(c["command_type"] == "shift_platform" for c in cmds)


def test_shift_niche_when_no_launch_candidates():
    cmds = generate_growth_commands(
        _scale_rec(
            recommendation_key=RK_ADD_NICHE_SPINOFF,
            incremental_profit_new_account=120,
            incremental_profit_existing_push=40,
            best_next_account={
                "niche_suggestion": "Budget hacks spinoff",
                "platform_suggestion": "youtube",
                "rationale": "Split sub-audience.",
            },
        ),
        [], [], None, [_acct_row()], [{"id": "o1"}, {"id": "o2"}], "finance", 70, 0, [],
    )
    assert any(c["command_type"] == "shift_niche" for c in cmds)


def test_compute_portfolio_directive_expand():
    cmds = [{"command_type": "launch_account", "priority": 80, "urgency": 70, "comparison": {"winner": "new_account"}}]
    bal = {"overbuilt": [], "underbuilt": [], "absent_platforms": ["tiktok"]}
    d = compute_portfolio_directive(
        2,
        {
            "recommended_account_count": 4,
            "recommendation_key": "add_experimental_account",
            "expansion_confidence": 0.72,
            "incremental_profit_new_account": 100,
            "incremental_profit_existing_push": 40,
        },
        bal,
        cmds,
        1,
    )
    assert d["current_account_count"] == 2
    assert d["recommended_account_count"] == 4
    assert d["hold_vs_expand"] == "expand"
    assert "explanation" in d and d["evidence"]["open_leak_count"] == 1


def test_map_content_role_experimental():
    assert "experimental" in map_content_role("experimental_account", None)


def test_merge_accounts_when_high_niche_overlap():
    accts = [
        _acct_row(id="a1", username="@one", niche_focus="personal finance tips"),
        _acct_row(id="a2", username="@two", niche_focus="finance tips personal"),
    ]
    cmds = generate_growth_commands(
        _scale_rec(), [], [], None, accts, [{"id": "o1"}, {"id": "o2"}], "finance", 70, 0, [],
    )
    assert any(c["command_type"] == "merge_accounts" for c in cmds)
