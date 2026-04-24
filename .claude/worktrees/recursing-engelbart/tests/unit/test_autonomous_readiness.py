"""Unit tests for Autonomous Readiness Standard + Activation Checklist."""
from packages.scoring.autonomous_readiness_engine import (
    ACTIVATION_CHECKLIST,
    evaluate_autonomous_readiness,
    get_activation_checklist,
    get_configured_count_by_priority,
)


def test_readiness_has_10_conditions():
    r = evaluate_autonomous_readiness()
    assert r["conditions_total"] == 10


def test_readiness_not_autonomous_without_credentials():
    r = evaluate_autonomous_readiness()
    assert r["fully_autonomous"] is False
    assert r["conditions_passing"] < 10


def test_readiness_verdict_contains_failing_count():
    r = evaluate_autonomous_readiness()
    if not r["fully_autonomous"]:
        assert "NOT YET AUTONOMOUS" in r["verdict"]


def test_readiness_blocking_conditions_listed():
    r = evaluate_autonomous_readiness()
    assert len(r["blocking_conditions"]) >= 1


def test_checklist_has_all_providers():
    assert len(ACTIVATION_CHECKLIST) >= 15


def test_checklist_has_required_fields():
    for item in ACTIVATION_CHECKLIST:
        for field in ("provider", "env_vars", "priority", "unlocks", "code_path_live"):
            assert field in item, f"Missing {field} in {item['provider']}"


def test_checklist_priorities_are_0_to_3():
    priorities = {item["priority"] for item in ACTIVATION_CHECKLIST}
    assert priorities == {0, 1, 2, 3}


def test_checklist_p0_has_claude_google_deepseek():
    p0 = [item for item in ACTIVATION_CHECKLIST if item["priority"] == 0]
    providers = {item["provider"] for item in p0}
    assert any("Claude" in p for p in providers)
    assert any("Gemini" in p for p in providers)
    assert any("DeepSeek" in p for p in providers)


def test_checklist_all_code_paths_live():
    for item in ACTIVATION_CHECKLIST:
        assert item["code_path_live"] is True


def test_get_activation_checklist_adds_configured_status():
    checklist = get_activation_checklist()
    for item in checklist:
        assert "configured" in item
        assert "missing_vars" in item


def test_configured_count_by_priority():
    counts = get_configured_count_by_priority()
    assert 0 in counts
    assert counts[0]["total"] >= 3


def test_readiness_condition_2_dead_ends_pass():
    r = evaluate_autonomous_readiness()
    cond2 = next(c for c in r["conditions"] if c["id"] == 2)
    assert cond2["passed"] is True


def test_readiness_condition_5_offer_learning_pass():
    r = evaluate_autonomous_readiness()
    cond5 = next(c for c in r["conditions"] if c["id"] == 5)
    assert cond5["passed"] is True


def test_readiness_condition_6_expansion_pass():
    r = evaluate_autonomous_readiness()
    cond6 = next(c for c in r["conditions"] if c["id"] == 6)
    assert cond6["passed"] is True


def test_readiness_condition_7_kill_scale_pass():
    r = evaluate_autonomous_readiness()
    cond7 = next(c for c in r["conditions"] if c["id"] == 7)
    assert cond7["passed"] is True
