"""Unit tests for scale alerts, launch candidates, blockers, readiness engines."""

from packages.scoring.scale_alerts_engine import (
    ALERT_TYPES,
    compute_launch_readiness,
    dedupe_alerts_by_type,
    diagnose_scale_blockers,
    generate_launch_candidates,
    generate_scale_alerts,
)


def _scale_rec(**kw):
    base = {"recommendation_key": "add_experimental_account", "scale_readiness_score": 72,
            "incremental_profit_new_account": 180, "incremental_profit_existing_push": 22,
            "explanation": "Expansion profitable.", "best_next_account": {"rationale": "Test"}, "id": "rec1"}
    base.update(kw)
    return base


def _accounts():
    return [
        {"id": "a1", "platform": "youtube", "geography": "US", "language": "en",
         "niche_focus": "finance", "username": "@test", "follower_count": 10000,
         "fatigue_score": 0.2, "saturation_score": 0.15, "originality_drift_score": 0.1,
         "account_health": "healthy", "ctr": 0.03, "conversion_rate": 0.03,
         "posting_capacity_per_day": 2}
    ]


def test_scale_alerts_generates_primary():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 70, 2, 0.15, [0.15], [0.2], [0.1])
    assert len(alerts) >= 1
    assert alerts[0]["alert_type"] in ALERT_TYPES
    assert alerts[0]["confidence"] > 0
    assert alerts[0]["urgency"] > 0


def test_scale_alerts_cannibalization_warning():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 70, 2, 0.7, [0.15], [0.2], [0.1])
    types = {a["alert_type"] for a in alerts}
    assert "cannibalization_warning" in types


def test_scale_alerts_saturation_warning():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 70, 2, 0.1, [0.75], [0.2], [0.1])
    types = {a["alert_type"] for a in alerts}
    assert "saturation_warning" in types


def test_scale_alerts_fatigue_warning():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 70, 2, 0.1, [0.15], [0.7], [0.1])
    types = {a["alert_type"] for a in alerts}
    assert "improve_retention_before_scaling" in types


def test_scale_alerts_originality_warning():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 70, 2, 0.1, [0.15], [0.2], [0.6])
    types = {a["alert_type"] for a in alerts}
    assert "improve_originality_before_scaling" in types


def test_scale_alerts_low_trust():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 40, 2, 0.1, [0.15], [0.2], [0.1])
    types = {a["alert_type"] for a in alerts}
    assert "suppress_account" in types


def test_scale_alerts_many_leaks():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 70, 8, 0.1, [0.15], [0.2], [0.1])
    types = {a["alert_type"] for a in alerts}
    assert "improve_funnel_before_scaling" in types


def test_launch_candidate_from_scale_rec():
    candidates = generate_launch_candidates(_scale_rec(), _accounts(), "finance", 0.15, 0.85, [{"id": "o1", "name": "Offer"}])
    assert len(candidates) == 1
    c = candidates[0]
    assert c["candidate_type"] == "experimental_account"
    assert c["confidence"] > 0
    assert c["expected_monthly_revenue_min"] > 0
    assert len(c["supporting_reasons"]) >= 1


def test_launch_candidate_flagship_from_scale_winners():
    candidates = generate_launch_candidates(_scale_rec(recommendation_key="scale_current_winners_harder"), _accounts(), "finance", 0.15, 0.85, [])
    assert len(candidates) >= 1
    assert any(c["candidate_type"] == "flagship_expansion" for c in candidates)


def test_launch_candidate_suppressed_when_cannibalization_extreme():
    candidates = generate_launch_candidates(_scale_rec(), _accounts(), "finance", 0.8, 0.3, [])
    assert candidates == []


def test_launch_candidate_blockers_when_high_cannibalization():
    candidates = generate_launch_candidates(_scale_rec(), _accounts(), "finance", 0.7, 0.3, [])
    assert len(candidates) == 1
    assert len(candidates[0]["launch_blockers"]) >= 1


def test_diagnose_blockers_low_readiness():
    blockers = diagnose_scale_blockers(20, _accounts(), 70, 2, 0.15, 0.85, 3)
    types = {b["blocker_type"] for b in blockers}
    assert "low_scale_readiness" in types


def test_diagnose_blockers_weak_trust():
    blockers = diagnose_scale_blockers(72, _accounts(), 40, 2, 0.15, 0.85, 3)
    types = {b["blocker_type"] for b in blockers}
    assert "weak_trust" in types


def test_diagnose_blockers_thin_offers():
    blockers = diagnose_scale_blockers(72, _accounts(), 70, 2, 0.15, 0.85, 1)
    types = {b["blocker_type"] for b in blockers}
    assert "weak_offer_fit" in types


def test_launch_readiness_high_score():
    r = compute_launch_readiness(80, 0.8, 0.85, 0.15, 5, 0.04, 75, 6, 0.15)
    assert r["launch_readiness_score"] > 60
    assert r["recommended_action"] in ("launch_now", "prepare_but_wait")
    assert len(r["gating_factors"]) == 0


def test_launch_readiness_gated_by_trust():
    r = compute_launch_readiness(80, 0.8, 0.85, 0.15, 5, 0.04, 40, 6, 0.15)
    assert "Trust score too low" in r["gating_factors"]
    assert r["recommended_action"] == "do_not_launch_yet"


def test_launch_readiness_gated_by_cannibalization():
    r = compute_launch_readiness(80, 0.8, 0.85, 0.15, 5, 0.04, 75, 6, 0.7)
    assert "Cannibalization risk too high" in r["gating_factors"]


def test_launch_readiness_components_present():
    r = compute_launch_readiness(50, 0.5, 0.5, 0.3, 3, 0.02, 60, 4, 0.3)
    assert "scale_readiness" in r["components"]
    assert "expansion_confidence" in r["components"]
    assert "cannibalization_inverse" in r["components"]
    assert "trust_readiness" in r["components"]


def test_dedupe_alerts_by_type_keeps_higher_urgency():
    a = [{"alert_type": "scale_now", "urgency": 40.0}, {"alert_type": "scale_now", "urgency": 90.0}]
    d = dedupe_alerts_by_type(a)
    assert len(d) == 1
    assert d[0]["urgency"] == 90.0


def test_niche_shift_when_saturation_very_high():
    alerts = generate_scale_alerts(_scale_rec(), _accounts(), 70, 2, 0.1, [0.8], [0.2], [0.1])
    types = {a["alert_type"] for a in alerts}
    assert "niche_shift_recommendation" in types
