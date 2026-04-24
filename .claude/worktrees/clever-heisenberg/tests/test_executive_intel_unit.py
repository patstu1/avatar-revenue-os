"""Unit tests for executive intelligence engine."""
import pytest
from packages.scoring.executive_intel_engine import (
    rollup_kpis, forecast_metric, compute_usage_cost, compute_uptime,
    evaluate_oversight, generate_executive_alerts,
)


class TestKPIRollup:
    def test_rollup(self):
        r = rollup_kpis({"total_revenue": 5000, "total_profit": 2000, "total_spend": 500}, {"produced": 100, "published": 80}, {"total_impressions": 500000, "avg_engagement_rate": 0.06, "avg_conversion_rate": 0.03}, {"active_count": 10}, {"active_count": 5})
        assert r["total_revenue"] == 5000
        assert r["content_produced"] == 100
        assert r["active_campaigns"] == 5


class TestForecast:
    def test_growth_trend(self):
        r = forecast_metric([100, 120, 150, 180])
        assert r["predicted_value"] > 180
        assert r["confidence"] > 0.3
        assert any("Growth" in o for o in r.get("opportunity_factors", []))

    def test_decline_trend(self):
        r = forecast_metric([200, 180, 150, 100])
        assert r["predicted_value"] < 100
        assert any("Declining" in rf for rf in r.get("risk_factors", []))

    def test_single_value(self):
        r = forecast_metric([100])
        assert r["predicted_value"] == 100
        assert r["confidence"] == 0.2

    def test_empty(self):
        r = forecast_metric([])
        assert r["predicted_value"] == 0


class TestUsageCost:
    def test_compute(self):
        r = compute_usage_cost({"claude": {"tasks": 100, "cost": 50, "hero_cost": 30, "bulk_cost": 20}})
        assert len(r) == 1
        assert r[0]["cost_incurred"] == 50


class TestUptime:
    def test_perfect(self):
        r = compute_uptime("claude", 1000, 0, 200)
        assert r["uptime_pct"] == 100.0
        assert r["reliability_grade"] == "A"

    def test_degraded(self):
        r = compute_uptime("claude", 1000, 100, 500)
        assert r["uptime_pct"] == 90.0
        assert r["reliability_grade"] == "C"

    def test_failed(self):
        r = compute_uptime("claude", 100, 30, 1000)
        assert r["reliability_grade"] in ("D", "F")

    def test_no_requests(self):
        r = compute_uptime("claude", 0, 0, 0)
        assert r["uptime_pct"] == 100.0


class TestOversight:
    def test_full_auto(self):
        r = evaluate_oversight(95, 5, 2)
        assert r["mode"] == "full_auto"

    def test_hybrid(self):
        r = evaluate_oversight(60, 40, 8)
        assert r["mode"] == "hybrid"

    def test_human_only(self):
        r = evaluate_oversight(50, 50, 40)
        assert r["mode"] == "human_only"

    def test_no_actions(self):
        r = evaluate_oversight(0, 0, 0)
        assert r["ai_accuracy_estimate"] == 0


class TestAlerts:
    def test_zero_revenue(self):
        alerts = generate_executive_alerts({"total_revenue": 0}, [], [], {})
        assert any(a["alert_type"] == "zero_revenue" for a in alerts)

    def test_declining_forecast(self):
        alerts = generate_executive_alerts({}, [{"forecast_type": "revenue", "trend": -0.2, "confidence": 0.7}], [], {})
        assert any(a["alert_type"] == "declining_forecast" for a in alerts)

    def test_provider_reliability(self):
        alerts = generate_executive_alerts({}, [], [{"provider_key": "claude", "reliability_grade": "F", "uptime_pct": 70, "failed_requests": 30}], {})
        assert any(a["alert_type"] == "provider_reliability" for a in alerts)

    def test_low_ai_accuracy(self):
        alerts = generate_executive_alerts({}, [], [], {"ai_accuracy_estimate": 0.6, "recommendation": "Switch to human"})
        assert any(a["alert_type"] == "ai_accuracy_low" for a in alerts)

    def test_no_alerts_when_healthy(self):
        alerts = generate_executive_alerts({"total_revenue": 5000}, [], [], {"ai_accuracy_estimate": 0.95})
        assert len(alerts) == 0
