"""Unit tests for Brain Architecture Phase A scoring engines."""
import pytest

from packages.scoring.brain_phase_a_engine import (
    ACCOUNT_STATES,
    AUDIENCE_STATES_V2,
    EXECUTION_STATES,
    MEMORY_ENTRY_TYPES,
    OPPORTUNITY_STATES,
    compute_account_state,
    compute_audience_state_v2,
    compute_execution_state,
    compute_opportunity_state,
    consolidate_brain_memory,
)


# ── Account State Engine ──────────────────────────────────────────────

class TestComputeAccountState:
    def test_newborn_account(self):
        result = compute_account_state({"age_days": 5, "follower_count": 50})
        assert result["current_state"] == "newborn"
        assert result["current_state"] in ACCOUNT_STATES

    def test_warming_account(self):
        result = compute_account_state({"age_days": 20, "follower_count": 200})
        assert result["current_state"] == "warming"

    def test_stable_account(self):
        result = compute_account_state({
            "age_days": 90, "follower_count": 500,
            "avg_engagement": 0.02, "profit_per_post": 5,
        })
        assert result["current_state"] == "stable"

    def test_scaling_account(self):
        result = compute_account_state({
            "age_days": 120, "follower_count": 2000,
            "avg_engagement": 0.03, "profit_per_post": 10,
        })
        assert result["current_state"] == "scaling"

    def test_max_output_account(self):
        result = compute_account_state({
            "age_days": 200, "follower_count": 10000,
            "avg_engagement": 0.04, "profit_per_post": 20,
            "posting_capacity_per_day": 2, "output_per_week": 12,
        })
        assert result["current_state"] == "max_output"

    def test_saturated_account(self):
        result = compute_account_state({
            "age_days": 200, "saturation_score": 0.8,
        })
        assert result["current_state"] == "saturated"

    def test_cooling_account(self):
        result = compute_account_state({
            "age_days": 200, "fatigue_score": 0.7, "saturation_score": 0.3,
        })
        assert result["current_state"] == "cooling"

    def test_at_risk_account(self):
        result = compute_account_state({"account_health": "critical"})
        assert result["current_state"] == "at_risk"

    def test_output_has_all_fields(self):
        result = compute_account_state({"age_days": 30})
        for key in ["current_state", "state_score", "transition_reason", "next_expected_state", "confidence", "explanation"]:
            assert key in result

    def test_confidence_bounded(self):
        result = compute_account_state({"age_days": 500})
        assert 0 <= result["confidence"] <= 1.0


# ── Opportunity State Engine ──────────────────────────────────────────

class TestComputeOpportunityState:
    def test_blocked_opportunity(self):
        result = compute_opportunity_state({"has_blocker": True})
        assert result["current_state"] == "blocked"

    def test_suppress_high_risk(self):
        result = compute_opportunity_state({"suppression_risk": 0.8})
        assert result["current_state"] == "suppress"

    def test_scale_winner(self):
        result = compute_opportunity_state({
            "opportunity_score": 0.7, "tests_run": 3, "win_rate": 0.6,
        })
        assert result["current_state"] == "scale"

    def test_test_phase(self):
        result = compute_opportunity_state({
            "opportunity_score": 0.5, "readiness": 0.6,
        })
        assert result["current_state"] == "test"

    def test_monitor_phase(self):
        result = compute_opportunity_state({"opportunity_score": 0.3})
        assert result["current_state"] == "monitor"

    def test_backlog(self):
        result = compute_opportunity_state({"opportunity_score": 0.1})
        assert result["current_state"] == "evergreen_backlog"

    def test_all_states_valid(self):
        for state in OPPORTUNITY_STATES:
            assert state in OPPORTUNITY_STATES


# ── Execution State Engine ────────────────────────────────────────────

class TestComputeExecutionState:
    def test_completed(self):
        result = compute_execution_state({"run_status": "completed"})
        assert result["current_state"] == "completed"

    def test_failed_after_retries(self):
        result = compute_execution_state({"failure_count": 3})
        assert result["current_state"] == "failed"
        assert result["rollback_eligible"] is True
        assert result["escalation_required"] is True

    def test_recovering(self):
        result = compute_execution_state({"failure_count": 1})
        assert result["current_state"] == "recovering"

    def test_blocked(self):
        result = compute_execution_state({"has_blocker": True})
        assert result["current_state"] == "blocked"

    def test_autonomous_execution(self):
        result = compute_execution_state({
            "execution_mode": "autonomous", "confidence": 0.85, "estimated_cost": 20,
        })
        assert result["current_state"] == "autonomous"

    def test_guarded_low_confidence(self):
        result = compute_execution_state({
            "execution_mode": "autonomous", "confidence": 0.5, "estimated_cost": 20,
        })
        assert result["current_state"] == "guarded"

    def test_guarded_high_cost(self):
        result = compute_execution_state({
            "execution_mode": "autonomous", "confidence": 0.85, "estimated_cost": 100,
        })
        assert result["current_state"] == "guarded"

    def test_manual(self):
        result = compute_execution_state({"execution_mode": "manual"})
        assert result["current_state"] == "manual"

    def test_queued_default(self):
        result = compute_execution_state({})
        assert result["current_state"] == "manual"


# ── Audience State V2 Engine ──────────────────────────────────────────

class TestComputeAudienceStateV2:
    def test_unaware(self):
        result = compute_audience_state_v2({})
        assert result["current_state"] == "unaware"

    def test_curious(self):
        result = compute_audience_state_v2({"content_views_30d": 5})
        assert result["current_state"] == "curious"

    def test_evaluating(self):
        result = compute_audience_state_v2({"content_views_30d": 15, "cta_clicks_30d": 2})
        assert result["current_state"] == "evaluating"

    def test_objection_heavy(self):
        result = compute_audience_state_v2({"content_views_30d": 15, "cta_clicks_30d": 2, "objection_signals": 3})
        assert result["current_state"] == "objection_heavy"

    def test_ready_to_buy(self):
        result = compute_audience_state_v2({"cta_clicks_30d": 5})
        assert result["current_state"] == "ready_to_buy"

    def test_bought_once(self):
        result = compute_audience_state_v2({"purchase_count": 1})
        assert result["current_state"] == "bought_once"

    def test_churn_risk(self):
        result = compute_audience_state_v2({"purchase_count": 1, "churn_risk": 0.6})
        assert result["current_state"] == "churn_risk"

    def test_repeat_buyer(self):
        result = compute_audience_state_v2({"purchase_count": 2})
        assert result["current_state"] == "repeat_buyer"

    def test_high_ltv(self):
        result = compute_audience_state_v2({"purchase_count": 3, "ltv": 300})
        assert result["current_state"] == "high_ltv"

    def test_advocate(self):
        result = compute_audience_state_v2({"purchase_count": 5, "ltv": 600, "referral_activity": 2})
        assert result["current_state"] == "advocate"

    def test_sponsor_friendly(self):
        result = compute_audience_state_v2({"purchase_count": 3, "sponsor_fit_score": 0.8})
        assert result["current_state"] == "sponsor_friendly"

    def test_transition_likelihoods(self):
        result = compute_audience_state_v2({"purchase_count": 1})
        assert "transition_likelihoods" in result
        assert isinstance(result["transition_likelihoods"], dict)

    def test_next_best_action(self):
        result = compute_audience_state_v2({"purchase_count": 1})
        assert result["next_best_action"] is not None


# ── Brain Memory Consolidation ────────────────────────────────────────

class TestConsolidateBrainMemory:
    def test_empty_context_returns_confidence_adjustment(self):
        result = consolidate_brain_memory({})
        assert len(result) >= 1
        assert result[0]["entry_type"] == "confidence_adjustment"

    def test_winner_account_creates_entry(self):
        ctx = {
            "accounts": [{"id": "abc123", "platform": "tiktok", "niche": "finance", "profit_per_post": 15, "avg_engagement": 0.04, "age_days": 90}],
            "offers": [],
            "suppression_history": [],
            "recovery_incidents": [],
            "top_content": [],
        }
        result = consolidate_brain_memory(ctx)
        assert any(e["entry_type"] == "winner" for e in result)

    def test_loser_account_creates_entry(self):
        ctx = {
            "accounts": [{"id": "xyz789", "platform": "instagram", "niche": "health", "profit_per_post": 0.5, "avg_engagement": 0.005, "age_days": 90}],
            "offers": [],
            "suppression_history": [],
            "recovery_incidents": [],
            "top_content": [],
        }
        result = consolidate_brain_memory(ctx)
        assert any(e["entry_type"] == "loser" for e in result)

    def test_strong_offer_creates_entry(self):
        ctx = {
            "accounts": [],
            "offers": [{"id": "offer1", "niche": "tech", "epc": 3.0, "conversion_rate": 0.05}],
            "suppression_history": [],
            "recovery_incidents": [],
            "top_content": [],
        }
        result = consolidate_brain_memory(ctx)
        assert any(e["entry_type"] == "best_monetization_route" for e in result)

    def test_suppression_creates_saturated_pattern(self):
        ctx = {
            "accounts": [],
            "offers": [],
            "suppression_history": [{"scope_type": "content", "scope_id": "s1", "reason": "audience fatigue", "confidence": 0.7, "detail": {}}],
            "recovery_incidents": [],
            "top_content": [],
        }
        result = consolidate_brain_memory(ctx)
        assert any(e["entry_type"] == "saturated_pattern" for e in result)

    def test_recovery_creates_common_blocker(self):
        ctx = {
            "accounts": [],
            "offers": [],
            "suppression_history": [],
            "recovery_incidents": [{"scope_type": "system", "scope_id": "r1", "incident_type": "provider_failure", "confidence": 0.55, "detail": {}, "explanation": "API down", "fix": "switch provider"}],
            "top_content": [],
        }
        result = consolidate_brain_memory(ctx)
        assert any(e["entry_type"] == "common_blocker" for e in result)

    def test_entry_types_are_valid(self):
        ctx = {
            "accounts": [{"id": "a1", "platform": "youtube", "niche": "gaming", "profit_per_post": 20, "avg_engagement": 0.05, "age_days": 100}],
            "offers": [{"id": "o1", "niche": "gaming", "epc": 4.0, "conversion_rate": 0.06}],
            "suppression_history": [],
            "recovery_incidents": [],
            "top_content": [],
        }
        result = consolidate_brain_memory(ctx)
        for e in result:
            assert e["entry_type"] in MEMORY_ENTRY_TYPES
