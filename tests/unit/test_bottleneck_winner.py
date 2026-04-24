"""Unit tests for bottleneck classifier and winner detection engines."""

from packages.scoring.bottleneck import BottleneckInput, classify_bottleneck
from packages.scoring.winner import ContentPerformance, detect_winners


class TestBottleneckClassifier:
    def test_no_data_defaults(self):
        result = classify_bottleneck(BottleneckInput())
        assert result.primary_bottleneck is not None
        assert result.severity in ("info", "warning", "critical")

    def test_weak_ctr_detected(self):
        result = classify_bottleneck(BottleneckInput(impressions=5000, clicks=10, ctr=0.002))
        assert result.primary_bottleneck == "weak_opportunity_selection"

    def test_weak_hook_detected(self):
        result = classify_bottleneck(BottleneckInput(views=500, avg_watch_pct=0.15, impressions=1000))
        bottleneck_cats = [b["category"] for b in result.all_bottlenecks]
        assert "weak_hook_retention" in bottleneck_cats

    def test_audience_fatigue_detected(self):
        result = classify_bottleneck(BottleneckInput(fatigue_score=0.7))
        bottleneck_cats = [b["category"] for b in result.all_bottlenecks]
        assert "audience_fatigue" in bottleneck_cats

    def test_weak_conversion_detected(self):
        result = classify_bottleneck(BottleneckInput(clicks=50, conversions=0, conversion_rate=0.0))
        bottleneck_cats = [b["category"] for b in result.all_bottlenecks]
        assert any(c in ("weak_landing_page", "weak_conversion") for c in bottleneck_cats)

    def test_scale_capacity_detected(self):
        result = classify_bottleneck(BottleneckInput(posting_capacity_used_pct=0.95))
        bottleneck_cats = [b["category"] for b in result.all_bottlenecks]
        assert "weak_scale_capacity" in bottleneck_cats

    def test_recommended_actions_present(self):
        result = classify_bottleneck(BottleneckInput(impressions=5000, ctr=0.001))
        assert len(result.recommended_actions) > 0

    def test_explanation_present(self):
        result = classify_bottleneck(BottleneckInput())
        assert len(result.explanation) > 0

    def test_severity_critical_for_bad_metrics(self):
        result = classify_bottleneck(
            BottleneckInput(
                impressions=10000,
                clicks=5,
                ctr=0.0005,
                avg_watch_pct=0.1,
                views=500,
            )
        )
        assert result.severity in ("critical", "warning")


class TestWinnerDetection:
    def test_empty_list(self):
        assert detect_winners([]) == []

    def test_winner_detected(self):
        items = [
            ContentPerformance(
                content_id="1",
                title="Winner",
                impressions=10000,
                revenue=150,
                profit=140,
                rpm=15.0,
                ctr=0.04,
                engagement_rate=0.06,
                conversion_rate=0.04,
            )
        ]
        results = detect_winners(items)
        assert results[0].is_winner
        assert results[0].win_score >= 0.5

    def test_loser_detected(self):
        items = [
            ContentPerformance(
                content_id="2",
                title="Loser",
                impressions=5000,
                revenue=5,
                profit=-3,
                rpm=1.0,
                ctr=0.002,
                engagement_rate=0.005,
            )
        ]
        results = detect_winners(items)
        assert results[0].is_loser

    def test_clone_recommended_for_winner(self):
        items = [
            ContentPerformance(
                content_id="3",
                title="Clone Me",
                impressions=20000,
                revenue=300,
                profit=280,
                rpm=15,
                ctr=0.04,
                engagement_rate=0.06,
                conversion_rate=0.05,
                platform="youtube",
            )
        ]
        results = detect_winners(items, available_platforms=["youtube", "tiktok", "instagram"])
        assert results[0].clone_recommended
        assert "tiktok" in results[0].clone_targets

    def test_neutral_content(self):
        items = [
            ContentPerformance(
                content_id="4",
                title="Meh",
                impressions=500,
                revenue=5,
                profit=2,
                rpm=10,
                ctr=0.02,
            )
        ]
        results = detect_winners(items)
        assert not results[0].is_winner
        assert not results[0].is_loser

    def test_sorted_by_win_score(self):
        items = [
            ContentPerformance(content_id="a", title="Low", rpm=5, ctr=0.01),
            ContentPerformance(
                content_id="b", title="High", rpm=20, profit=100, engagement_rate=0.08, ctr=0.04, conversion_rate=0.04
            ),
        ]
        results = detect_winners(items)
        assert results[0].content_id == "b"
