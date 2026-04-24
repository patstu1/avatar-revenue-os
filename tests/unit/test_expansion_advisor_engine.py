"""Unit tests for Account Expansion Advisor engine."""
from packages.scoring.expansion_advisor_engine import (
    EXPAND_REC_KEYS,
    HOLD_REC_KEYS,
    compute_expansion_advisory,
)


def _scale_result(rec_key="add_experimental", inc_new=200, inc_exist=100, readiness=65, exp_conf=0.6, cann=0.2, seg_sep=0.7):
    return {
        "recommendation_key": rec_key,
        "best_next_account": {"platform_suggestion": "tiktok", "niche_suggestion": "fitness sub-niche"},
        "incremental_profit_new_account": inc_new,
        "incremental_profit_more_volume": inc_exist,
        "scale_readiness_score": readiness,
        "expansion_confidence": exp_conf,
        "cannibalization_risk": cann,
        "audience_segment_separation": seg_sep,
        "explanation": "Expansion beats exploitation.",
    }


def _accounts(n=2):
    return [{"id": f"a{i}", "platform": "youtube", "username": f"@u{i}"} for i in range(n)]


def test_expand_when_scale_says_add():
    r = compute_expansion_advisory(_scale_result("add_experimental"), _accounts(), "fitness", None, 2, 10)
    assert r["should_add_account_now"] is True
    assert r["platform"] is not None
    assert r["content_role"] is not None
    assert r["monetization_path"] is not None
    assert r["expected_upside"] > 0
    assert r["confidence"] > 0
    assert "EXPAND NOW" in r["explanation"]


def test_hold_when_scale_says_monitor():
    r = compute_expansion_advisory(_scale_result("monitor"), _accounts(), "fitness", None, 2, 10)
    assert r["should_add_account_now"] is False
    assert r["hold_reason"] is not None
    assert r["platform"] is None
    assert "HOLD" in r["explanation"]


def test_hold_when_winners_harder():
    r = compute_expansion_advisory(_scale_result("scale_winners_harder", inc_new=50, inc_exist=200), _accounts(), "tech", None, 3, 15)
    assert r["should_add_account_now"] is False
    assert "winners" in r["hold_reason"].lower() or "existing" in r["hold_reason"].lower()


def test_hold_when_do_not_scale():
    r = compute_expansion_advisory(_scale_result("do_not_scale_yet", readiness=20), _accounts(), "tech", None, 2, 10)
    assert r["should_add_account_now"] is False
    assert "readiness" in r["hold_reason"].lower()


def test_hold_when_improve_funnel():
    r = compute_expansion_advisory(_scale_result("improve_funnel"), _accounts(), "tech", None, 2, 10)
    assert r["should_add_account_now"] is False
    assert "funnel" in r["hold_reason"].lower()


def test_blocker_no_offers():
    r = compute_expansion_advisory(_scale_result("add_experimental"), _accounts(), "tech", None, offer_count=0, content_count=10)
    assert r["should_add_account_now"] is False
    assert any(b["type"] == "no_offers" for b in r["blockers"])


def test_blocker_critical_health():
    r = compute_expansion_advisory(_scale_result("add_experimental"), _accounts(), "tech", None, 2, 10, avg_account_health="critical")
    assert r["should_add_account_now"] is False
    assert any(b["type"] == "unhealthy_accounts" for b in r["blockers"])


def test_blocker_low_content():
    r = compute_expansion_advisory(_scale_result("add_experimental"), _accounts(), "tech", None, 2, content_count=3)
    assert any(b["type"] == "low_content" for b in r["blockers"])


def test_blocker_high_fatigue():
    r = compute_expansion_advisory(_scale_result("add_experimental"), _accounts(), "tech", None, 2, 10, avg_fatigue=0.85)
    assert any(b["type"] == "high_fatigue" for b in r["blockers"])


def test_evidence_populated():
    r = compute_expansion_advisory(_scale_result(), _accounts(), "tech", "sub", 3, 20)
    ev = r["evidence"]
    assert ev["recommendation_key"] == "add_experimental"
    assert ev["offer_count"] == 3
    assert ev["content_count"] == 20
    assert "scale_readiness" in ev
    assert "cannibalization_risk" in ev


def test_all_expand_keys_produce_expand():
    for key in EXPAND_REC_KEYS:
        r = compute_expansion_advisory(_scale_result(key), _accounts(), "x", None, 2, 10)
        assert r["should_add_account_now"] is True, f"{key} should expand"


def test_all_hold_keys_produce_hold():
    for key in HOLD_REC_KEYS:
        r = compute_expansion_advisory(_scale_result(key), _accounts(), "x", None, 2, 10)
        assert r["should_add_account_now"] is False, f"{key} should hold"


def test_confidence_in_range():
    r = compute_expansion_advisory(_scale_result(), _accounts(), "x", None, 2, 10)
    assert 0 <= r["confidence"] <= 1


def test_urgency_positive():
    r = compute_expansion_advisory(_scale_result(), _accounts(), "x", None, 2, 10)
    assert r["urgency"] > 0


def test_time_to_signal_present_when_expand():
    r = compute_expansion_advisory(_scale_result("add_trend_capture"), _accounts(), "x", None, 2, 10)
    assert r["expected_time_to_signal_days"] > 0


def test_time_to_signal_zero_when_hold():
    r = compute_expansion_advisory(_scale_result("monitor"), _accounts(), "x", None, 2, 10)
    assert r["expected_time_to_signal_days"] == 0
