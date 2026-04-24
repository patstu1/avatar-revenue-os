"""Unit tests: autonomous execution gate engine."""
from __future__ import annotations

import pytest

from packages.scoring.autonomous_execution_engine import evaluate_execution_gate


def test_kill_switch_blocks():
    r = evaluate_execution_gate(
        operating_mode="fully_autonomous",
        kill_switch_engaged=True,
        loop_step="publish_queue",
        confidence=0.99,
        estimated_cost_usd=1.0,
        min_confidence_auto_execute=0.5,
        min_confidence_publish=0.5,
        max_auto_cost_usd_per_action=500.0,
        require_approval_above_cost_usd=50.0,
    )
    assert r["decision"] == "blocked"
    assert "kill_switch" in str(r["reasons"]).lower() or "kill_switch" in r["reasons"][0]


def test_escalation_only_is_manual_only():
    r = evaluate_execution_gate(
        operating_mode="escalation_only",
        kill_switch_engaged=False,
        loop_step="scan_opportunities",
        confidence=0.99,
        estimated_cost_usd=None,
        min_confidence_auto_execute=0.1,
        min_confidence_publish=0.1,
        max_auto_cost_usd_per_action=None,
        require_approval_above_cost_usd=None,
    )
    assert r["decision"] == "manual_only"


def test_low_confidence_requires_approval():
    r = evaluate_execution_gate(
        operating_mode="fully_autonomous",
        kill_switch_engaged=False,
        loop_step="publish_queue",
        confidence=0.10,
        estimated_cost_usd=1.0,
        min_confidence_auto_execute=0.72,
        min_confidence_publish=0.78,
        max_auto_cost_usd_per_action=500.0,
        require_approval_above_cost_usd=50.0,
    )
    assert r["decision"] == "require_approval"


def test_cost_exceeds_hard_cap_blocked():
    r = evaluate_execution_gate(
        operating_mode="fully_autonomous",
        kill_switch_engaged=False,
        loop_step="generate_content",
        confidence=0.99,
        estimated_cost_usd=9999.0,
        min_confidence_auto_execute=0.5,
        min_confidence_publish=0.5,
        max_auto_cost_usd_per_action=100.0,
        require_approval_above_cost_usd=50.0,
    )
    assert r["decision"] == "blocked"


def test_guarded_cost_triggers_approval_not_block():
    r = evaluate_execution_gate(
        operating_mode="guarded_autonomous",
        kill_switch_engaged=False,
        loop_step="generate_content",
        confidence=0.95,
        estimated_cost_usd=120.0,
        min_confidence_auto_execute=0.5,
        min_confidence_publish=0.5,
        max_auto_cost_usd_per_action=500.0,
        require_approval_above_cost_usd=50.0,
    )
    assert r["decision"] == "require_approval"


def test_allow_when_healthy():
    r = evaluate_execution_gate(
        operating_mode="fully_autonomous",
        kill_switch_engaged=False,
        loop_step="monitor_performance",
        confidence=0.90,
        estimated_cost_usd=5.0,
        min_confidence_auto_execute=0.72,
        min_confidence_publish=0.78,
        max_auto_cost_usd_per_action=250.0,
        require_approval_above_cost_usd=75.0,
    )
    assert r["decision"] == "allow"
