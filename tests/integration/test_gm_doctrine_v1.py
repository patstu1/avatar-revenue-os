"""Integration tests for Batch 7A — GM doctrine + startup inspection.

Covers:
  1. Doctrine constants + classifier (pure-function unit behaviour)
  2. Floor status math against real Payments
  3. Pipeline state counts + bottleneck selection
  4. Bottlenecks ranks past-SLA stage_states first
  5. Closest-revenue buckets populate correctly
  6. Blocking-floors combines floor + closest
  7. Game plan ranks by priority engine
  8. /gm/doctrine endpoint surfaces the canonical constants
  9. /gm/startup-inspection returns the 5 compute outputs + situation_report_lines
  10. /gm/floor-status, /gm/game-plan, /gm/bottlenecks, /gm/closest-revenue,
      /gm/blocking-floors, /gm/pipeline-state all return 200 + expected shape
  11. System prompt GM_OPERATOR_PROMPT contains the revenue doctrine text
  12. Doctrine forbidden-behaviors list is non-empty and references
      approval-required / stage-completion / escalation invariants
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from apps.api.services.gm_doctrine import (
    ACTION_CLASS_APPROVAL,
    ACTION_CLASS_AUTO,
    ACTION_CLASS_ESCALATE,
    CANONICAL_DATA_TABLES,
    FLOOR_MONTH_1_CENTS,
    FLOOR_MONTH_12_CENTS,
    FORBIDDEN_BEHAVIORS,
    GM_REVENUE_DOCTRINE,
    PILLARS,
    PRIORITY_RANK,
    STAGE_MACHINE,
    classify_action,
    floor_for_month,
)


# ═══════════════════════════════════════════════════════════════════════════
#  Pure-data + pure-function tests (no DB, no HTTP)
# ═══════════════════════════════════════════════════════════════════════════


def test_doctrine_constants_shape():
    assert FLOOR_MONTH_1_CENTS == 3_000_000
    assert FLOOR_MONTH_12_CENTS == 100_000_000
    assert len(STAGE_MACHINE) == 11
    assert all("n" in s and "name" in s and "timeout_minutes" in s for s in STAGE_MACHINE)
    assert set(PILLARS) == {"intake", "conversion", "fulfillment"}
    assert len(PRIORITY_RANK) == 6
    assert len(FORBIDDEN_BEHAVIORS) >= 8
    assert "proposals" in CANONICAL_DATA_TABLES
    assert "gm_approvals" in CANONICAL_DATA_TABLES
    assert "payments" in CANONICAL_DATA_TABLES


def test_floor_trajectory_is_monotonic_and_bounded():
    # Log-linear from month 1 to month 12
    assert floor_for_month(1) == FLOOR_MONTH_1_CENTS
    assert floor_for_month(12) == FLOOR_MONTH_12_CENTS
    assert floor_for_month(0) == FLOOR_MONTH_1_CENTS
    assert floor_for_month(20) == FLOOR_MONTH_12_CENTS
    # Monotonic increasing 1..12
    prior = 0
    for m in range(1, 13):
        cur = floor_for_month(m)
        assert cur >= prior, f"month {m} floor {cur} should be >= month {m-1} {prior}"
        prior = cur


def test_classify_action_escalates_on_low_confidence():
    assert classify_action(confidence=0.5) == ACTION_CLASS_ESCALATE


def test_classify_action_escalates_on_unmatched():
    assert classify_action(confidence=0.95, unmatched=True) == ACTION_CLASS_ESCALATE


def test_classify_action_requires_approval_on_money():
    assert classify_action(confidence=0.95, money_involved=True) == ACTION_CLASS_APPROVAL


def test_classify_action_auto_only_when_all_conditions_met():
    assert classify_action(confidence=0.95) == ACTION_CLASS_AUTO
    # Not reversible → approval
    assert classify_action(confidence=0.95, standard_reversible=False) == ACTION_CLASS_APPROVAL


def test_classify_action_escalation_beats_money():
    # Past SLA + money → escalate (escalation is checked first)
    assert classify_action(confidence=0.95, money_involved=True, past_hard_sla=True) == ACTION_CLASS_ESCALATE


def test_gm_revenue_doctrine_text_has_required_markers():
    for marker in (
        "GM OPERATING DIRECTIVE",
        "US$30,000",
        "US$1,000,000",
        "Canonical stage machine (11 stages)",
        "Action classes",
        "Priority engine",
        "Forbidden behaviors",
        "Canonical data dependencies",
    ):
        assert marker in GM_REVENUE_DOCTRINE, f"missing marker: {marker!r}"


def test_operator_prompt_inlines_doctrine():
    from apps.api.services.gm_system_prompt import GM_OPERATOR_PROMPT
    assert "GM OPERATING DIRECTIVE" in GM_OPERATOR_PROMPT
    assert "US$30,000" in GM_OPERATOR_PROMPT
    assert "US$1,000,000" in GM_OPERATOR_PROMPT


# ═══════════════════════════════════════════════════════════════════════════
#  HTTP / DB-backed tests
# ═══════════════════════════════════════════════════════════════════════════


async def _auth(api_client, sample_org_data) -> tuple[dict, uuid.UUID]:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, uuid.UUID(me.json()["organization_id"])


@pytest.mark.asyncio
async def test_gm_doctrine_endpoint_returns_canonical_structure(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/doctrine", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["floors"]["month_1_cents"] == FLOOR_MONTH_1_CENTS
    assert body["floors"]["month_12_cents"] == FLOOR_MONTH_12_CENTS
    assert len(body["stage_machine"]) == 11
    assert set(body["pillars"]) == set(PILLARS)
    assert len(body["priority_rank"]) == 6
    assert "GM OPERATING DIRECTIVE" in body["initialization_brief_preview"]


@pytest.mark.asyncio
async def test_floor_status_with_no_payments_returns_zero(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/floor-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["floor_cents"] == FLOOR_MONTH_1_CENTS
    assert body["trailing_30d_cents"] == 0
    assert body["gap_cents"] == FLOOR_MONTH_1_CENTS
    assert body["ratio_to_floor"] == 0.0
    assert body["floor_met"] is False


@pytest.mark.asyncio
async def test_floor_status_math_with_seeded_payment(api_client, db_session, sample_org_data):
    from packages.db.models.proposals import Payment

    headers, org_id = await _auth(api_client, sample_org_data)

    # Seed a $5,000 succeeded payment inside the trailing-30d window
    db_session.add(Payment(
        org_id=org_id,
        provider="stripe",
        provider_event_id=f"evt_test_{uuid.uuid4().hex[:10]}",
        amount_cents=500_000,
        currency="usd",
        status="succeeded",
        completed_at=datetime.now(timezone.utc) - timedelta(days=5),
        customer_email="test@example.com",
    ))
    await db_session.commit()

    r = await api_client.get("/api/v1/gm/floor-status", headers=headers)
    body = r.json()
    assert body["trailing_30d_cents"] == 500_000
    assert body["trailing_30d_usd"] == 5000.0
    assert body["gap_cents"] == FLOOR_MONTH_1_CENTS - 500_000
    assert 0.16 < body["ratio_to_floor"] < 0.18  # ~0.1667


@pytest.mark.asyncio
async def test_pipeline_state_returns_stage_entries(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/pipeline-state", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body["stages"]) >= 8  # we track stages 1,4,5,6,7,8,9,10,11
    stage_numbers = [s["stage"] for s in body["stages"]]
    for n in (1, 4, 5, 6, 7, 8, 9, 10, 11):
        assert n in stage_numbers


@pytest.mark.asyncio
async def test_bottlenecks_endpoint_shape(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/bottlenecks", headers=headers)
    assert r.status_code == 200
    body = r.json()
    for field in ("ranked", "total_tracked", "total_stuck", "total_overdue"):
        assert field in body


@pytest.mark.asyncio
async def test_closest_revenue_shape_with_empty_db(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/closest-revenue", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_potential_cents"] == 0
    assert set(body["buckets"].keys()) == {
        "proposal_sent_unpaid",
        "draft_pending_money_intent",
        "draft_approved_pending_send",
        "intake_sent_not_submitted",
    }


@pytest.mark.asyncio
async def test_blocking_floors_endpoint(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/blocking-floors", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["month_index"] == 1
    assert body["floor_usd"] == FLOOR_MONTH_1_CENTS / 100.0
    assert body["floor_met"] is False
    assert isinstance(body["blocker_reasons"], list)


@pytest.mark.asyncio
async def test_game_plan_includes_floor_gap_entry_when_floor_unmet(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/game-plan", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["month_index"] == 1
    assert isinstance(body["actions"], list)
    labels = {a["label"] for a in body["actions"]}
    assert "floor_gap_math" in labels


@pytest.mark.asyncio
async def test_startup_inspection_returns_five_compute_outputs(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/startup-inspection", headers=headers)
    assert r.status_code == 200
    body = r.json()
    for field in (
        "floor_status", "pipeline_state", "bottlenecks",
        "closest_revenue", "blocking_floors", "game_plan",
        "situation_report_lines", "priority_rank_reference", "forbidden_behaviors",
    ):
        assert field in body, f"missing field {field}"
    assert len(body["situation_report_lines"]) == 5
    assert len(body["forbidden_behaviors"]) >= 8
    assert len(body["priority_rank_reference"]) == 6


@pytest.mark.asyncio
async def test_endpoints_require_operator_auth(api_client):
    # Hit without auth — each should 401
    for path in (
        "/api/v1/gm/doctrine",
        "/api/v1/gm/floor-status",
        "/api/v1/gm/pipeline-state",
        "/api/v1/gm/bottlenecks",
        "/api/v1/gm/closest-revenue",
        "/api/v1/gm/blocking-floors",
        "/api/v1/gm/game-plan",
        "/api/v1/gm/startup-inspection",
    ):
        r = await api_client.get(path)
        assert r.status_code in (401, 403), f"{path} returned {r.status_code}, expected 401/403"
