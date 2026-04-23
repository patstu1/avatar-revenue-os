"""Unit tests: Deal Desk and Kill Ledger engines (Phase D)."""
from __future__ import annotations

import uuid

from packages.scoring.deal_desk_engine import DEAL_DESK, recommend_deal_strategy
from packages.scoring.kill_ledger_engine import (
    KILL_LEDGER,
    evaluate_kill_candidates,
    review_kill_hindsight,
)


class TestDealDeskEngine:
    def test_recommend_deal_strategy_outputs_required_fields(self):
        ctx = {
            "scope_type": "offer",
            "scope_id": str(uuid.uuid4()),
            "deal_value": 120000.0,
            "lead_quality": 0.85,
            "urgency": 0.6,
            "competition_intensity": 0.4,
            "niche": "saas",
        }
        brand_metrics = {
            "brand_authority_score": 0.75,
            "avg_margin": 0.4,
            "avg_close_rate": 0.3,
            "niche": "saas",
        }
        out = recommend_deal_strategy(ctx, brand_metrics)
        assert out.get(DEAL_DESK) is True
        stripped = {k: v for k, v in out.items() if k != DEAL_DESK}
        assert "deal_strategy" in stripped
        assert "pricing_stance" in stripped
        assert "packaging_recommendation" in stripped
        assert "expected_margin" in stripped
        assert "expected_close_probability" in stripped
        assert "confidence" in stripped
        assert "explanation" in stripped
        assert isinstance(stripped["expected_margin"], float)
        assert 0.0 <= stripped["expected_close_probability"] <= 1.0

    def test_sponsor_scope_produces_recommendation(self):
        ctx = {
            "scope_type": "sponsor",
            "scope_id": str(uuid.uuid4()),
            "deal_value": 25000.0,
            "lead_quality": 0.55,
            "urgency": 0.5,
            "competition_intensity": 0.65,
            "niche": "finance",
        }
        brand_metrics = {
            "brand_authority_score": 0.5,
            "avg_margin": 0.35,
            "avg_close_rate": 0.2,
            "niche": "finance",
        }
        out = recommend_deal_strategy(ctx, brand_metrics)
        stripped = {k: v for k, v in out.items() if k != DEAL_DESK}
        assert stripped["deal_strategy"] in (
            "custom_quote",
            "package_standard",
            "bundle_discount",
            "hold_price",
            "strategic_discount",
            "push_upsell",
            "nurture_sequence",
            "require_human_approval",
        )
        assert stripped["pricing_stance"] in ("premium", "competitive", "penetration", "hold")


class TestKillLedgerEngine:
    def test_evaluate_kill_candidates_underperforming_offer(self):
        candidates = [
            {
                "scope_type": "offer",
                "scope_id": str(uuid.uuid4()),
                "name": "Dead Offer",
                "conversion_rate": 0.0001,
                "revenue": 1.0,
                "aov": 5.0,
            }
        ]
        kills = evaluate_kill_candidates(candidates, {})
        assert len(kills) >= 1
        k = {x: y for x, y in kills[0].items() if x != KILL_LEDGER}
        assert k["scope_type"] == "offer"
        assert "kill_reason" in k
        assert "replacement_recommendation" in k
        assert "performance_snapshot" in k
        assert "name" in k["performance_snapshot"]

    def test_review_kill_hindsight_persistence_shape(self):
        kill_entry = {
            "scope_type": "offer",
            "scope_id": str(uuid.uuid4()),
            "kill_reason": "test",
            "performance_snapshot": {"revenue": 100.0, "engagement_rate": 0.02},
            "killed_at": "2025-01-01T00:00:00Z",
        }
        post = {
            "revenue": 40.0,
            "engagement_rate": 0.015,
            "overall_brand_revenue_delta": 500.0,
            "time_since_kill_days": 14,
            "replacement_performance": {},
        }
        r = review_kill_hindsight(kill_entry, post)
        body = {k: v for k, v in r.items() if k != KILL_LEDGER}
        assert "hindsight_outcome" in body
        assert "was_correct_kill" in body
        assert "explanation" in body
