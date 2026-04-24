"""Unit tests for hyper-scale execution engine."""
import pytest
from packages.scoring.hyperscale_engine import (
    partition_workload, evaluate_capacity, detect_burst, plan_degradation,
    enforce_ceiling, schedule_priority, balance_market_workload, build_scale_health,
)


class TestPartitioning:
    def test_partitions_by_brand(self):
        tasks = [{"brand_id": "a", "task_type": "gen"}, {"brand_id": "b", "task_type": "gen"}, {"brand_id": "a", "task_type": "gen"}]
        segs = partition_workload(tasks)
        assert len(segs) >= 2

    def test_empty_tasks(self):
        assert partition_workload([]) == {}


class TestCapacity:
    def test_healthy(self):
        segs = {"a": [{}] * 5}
        r = evaluate_capacity(segs, 50)
        assert r["health_status"] == "healthy"

    def test_degraded(self):
        segs = {"a": [{}] * 60}
        r = evaluate_capacity(segs, 50)
        assert r["health_status"] in ("degraded", "busy")

    def test_critical(self):
        segs = {"a": [{}] * 200}
        r = evaluate_capacity(segs, 50)
        assert r["health_status"] == "critical"


class TestBurst:
    def test_burst_detected(self):
        r = detect_burst(10.0, 600)
        assert r["burst_detected"] is True
        assert r["severity"] in ("high", "critical")

    def test_no_burst(self):
        r = detect_burst(1.0, 10)
        assert r["burst_detected"] is False


class TestDegradation:
    def test_critical_degrades(self):
        cap = {"health_status": "critical"}
        burst = {"burst_detected": True, "peak_qps": 10}
        r = plan_degradation(cap, burst)
        assert r["degradation_needed"] is True
        assert len(r["actions"]) >= 2

    def test_healthy_no_degradation(self):
        r = plan_degradation({"health_status": "healthy"}, {"burst_detected": False})
        assert r["degradation_needed"] is False


class TestCeiling:
    def test_exceeded(self):
        r = enforce_ceiling("cost", 100.0, 110.0)
        assert r["exceeded"] is True
        assert r["action"] == "block"

    def test_warning(self):
        r = enforce_ceiling("cost", 100.0, 85.0)
        assert r["warning"] is True
        assert r["action"] == "warn"

    def test_allowed(self):
        r = enforce_ceiling("cost", 100.0, 50.0)
        assert r["action"] == "allow"


class TestPriority:
    def test_sorted_by_priority(self):
        tasks = [{"priority": 10, "created_at": "a"}, {"priority": 90, "created_at": "b"}, {"priority": 50, "created_at": "c"}]
        result = schedule_priority(tasks)
        assert result[0]["priority"] == 90
        assert result[-1]["priority"] == 10


class TestMarketBalance:
    def test_identifies_overloaded(self):
        allocs = [{"market": "us", "allocated_capacity": 10, "used_capacity": 15}, {"market": "eu", "allocated_capacity": 10, "used_capacity": 3}]
        result = balance_market_workload(allocs)
        assert result[0]["status"] == "overloaded"
        assert result[1]["status"] == "healthy"


class TestScaleHealth:
    def test_builds_report(self):
        cap = {"health_status": "healthy", "total_queued": 20}
        ceilings = [{"utilization_pct": 45}]
        r = build_scale_health(cap, ceilings, 1, 0)
        assert r["health_status"] == "healthy"

    def test_critical_from_degradations(self):
        r = build_scale_health({"health_status": "degraded", "total_queued": 100}, [], 2, 5)
        assert r["health_status"] == "critical"
