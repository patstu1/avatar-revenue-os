"""Integration tests for Batch 7A-WIDE — FULL-MACHINE GM doctrine.

Covers:
  1. Doctrine constants: 22 avenues + 38 engines + 5 status flags +
     5 hard doctrine rules + full canonical table list.
  2. classify_action precedence, plus new dormant-avenue trigger.
  3. /gm/doctrine endpoint surfaces full avenue + engine lists.
  4. /gm/floor-status combines payments + creator_revenue_events with
     per-avenue breakdown.
  5. /gm/avenue-portfolio returns all 22 avenues with live-status
     reclassification.
  6. /gm/engine-status returns all 38 engines.
  7. /gm/ask-operator returns concrete request list.
  8. /gm/unlock-plans returns LIVE_BUT_DORMANT + PRESENT_IN_CODE_ONLY.
  9. /gm/game-plan ranks across ALL avenues.
  10. /gm/startup-inspection includes avenue_portfolio, engine_status,
      ask_operator, unlock_plans + 7-line situation report.
  11. GM_OPERATOR_PROMPT carries the wide doctrine text + anti-narrowing.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from apps.api.services.gm_doctrine import (
    ACTION_CLASS_APPROVAL,
    ACTION_CLASS_ESCALATE,
    CANONICAL_DATA_TABLES,
    FLOOR_MONTH_1_CENTS,
    FLOOR_MONTH_12_CENTS,
    GM_REVENUE_DOCTRINE,
    PRIORITY_RANK,
    REVENUE_AVENUES,
    STATUS_DISABLED_BY_OPERATOR,
    STATUS_FLAGS,
    STATUS_LIVE_BUT_DORMANT,
    STATUS_PRESENT_IN_CODE_ONLY,
    STRATEGIC_ENGINES,
    classify_action,
    floor_for_month,
)

# ═══════════════════════════════════════════════════════════════════════════
#  Pure-data + pure-function tests (no DB, no HTTP)
# ═══════════════════════════════════════════════════════════════════════════


def test_doctrine_has_22_avenues_none_collapsed():
    assert len(REVENUE_AVENUES) == 22
    ns = [a["n"] for a in REVENUE_AVENUES]
    assert ns == list(range(1, 23))  # exact 1..22 ordering
    ids = {a["id"] for a in REVENUE_AVENUES}
    # Spot-check: operator list matches
    for expected_id in (
        "b2b_services", "ugc_services", "consulting", "premium_access",
        "licensing", "syndication", "data_products", "merchandise",
        "live_events", "owned_affiliate", "external_affiliate",
        "saas_subscriptions", "high_ticket", "product_launches",
        "monetization_packs", "ecommerce", "sponsor_deals",
        "recurring_revenue", "paid_promotion", "upsell_bundles",
        "referral", "reactivation",
    ):
        assert expected_id in ids, f"avenue {expected_id} missing from doctrine"


def test_doctrine_has_strategic_engines_and_every_one_carries_status():
    assert len(STRATEGIC_ENGINES) >= 38
    for e in STRATEGIC_ENGINES:
        assert e["status"] in STATUS_FLAGS, f"{e['id']} has invalid status"
        assert e["tables"], f"{e['id']} has no tables"


def test_every_avenue_has_required_fields():
    for a in REVENUE_AVENUES:
        for field in ("id", "n", "display_name", "status",
                       "revenue_tables", "activity_tables", "description"):
            assert field in a, f"avenue {a['id']} missing field {field}"
        assert a["status"] in STATUS_FLAGS, f"{a['id']} invalid status"


def test_status_flags_exactly_five():
    assert len(STATUS_FLAGS) == 5
    assert set(STATUS_FLAGS) == {
        "LIVE_AND_VERY_ACTIVE",
        "LIVE_AND_ACTIVE",
        "LIVE_BUT_DORMANT",
        "PRESENT_IN_CODE_ONLY",
        "DISABLED_BY_OPERATOR",
    }


def test_nothing_disabled_by_default():
    disabled = [a for a in REVENUE_AVENUES if a["status"] == STATUS_DISABLED_BY_OPERATOR]
    assert disabled == [], f"avenues disabled by default: {disabled}"
    engine_disabled = [e for e in STRATEGIC_ENGINES if e["status"] == STATUS_DISABLED_BY_OPERATOR]
    assert engine_disabled == [], f"engines disabled by default: {engine_disabled}"


def test_floors_are_minimums_not_maxes():
    assert FLOOR_MONTH_1_CENTS == 3_000_000
    assert FLOOR_MONTH_12_CENTS == 100_000_000
    # Interpolation monotonic
    prior = 0
    for m in range(1, 13):
        cur = floor_for_month(m)
        assert cur >= prior
        prior = cur


def test_canonical_table_list_is_wide_not_narrow():
    # Must exceed the Batch 7A narrow-27 count. After full-machine doctrine
    # it should cover every avenue + every engine + core tables.
    assert len(CANONICAL_DATA_TABLES) >= 100, (
        f"Canonical table list only has {len(CANONICAL_DATA_TABLES)} — "
        "doctrine is still narrow."
    )
    # Spot-check: major-engine tables must be present
    for critical in (
        "offer_ladders", "message_sequences", "sponsor_inventory",
        "recurring_revenue_models", "ugc_service_actions",
        "service_consulting_actions", "ol_bundles", "high_ticket_opportunities",
        "reactivation_campaigns", "referral_program_recommendations",
        "trust_conversion_reports", "paid_promotion_candidates",
        "kill_ledger_entries", "brain_decisions", "tv_signals",
        "portfolio_launch_plans", "ca_allocation_reports",
        "creator_revenue_events", "payments",
    ):
        assert critical in CANONICAL_DATA_TABLES, f"{critical} missing from CANONICAL_DATA_TABLES"


def test_classify_action_dormant_avenue_forces_approval():
    # Even with high confidence + reversible, activating dormant → approval
    assert classify_action(
        confidence=0.99, standard_reversible=True, activates_dormant_avenue=True
    ) == ACTION_CLASS_APPROVAL


def test_classify_action_escalation_overrides_dormant():
    # Escalation still wins over dormant
    assert classify_action(
        confidence=0.5, activates_dormant_avenue=True
    ) == ACTION_CLASS_ESCALATE


def test_doctrine_text_has_all_three_hard_rules_verbatim():
    for marker in (
        "ANTI-NARROWING RULE",
        "NO-MONEY-CAPPING RULE",
        "FLOORS-NOT-CEILINGS RULE",
        "ALWAYS-PLAN-AND-ASK RULE",
        "DORMANT-AVENUE RULE",
    ):
        assert marker in GM_REVENUE_DOCTRINE, f"missing rule: {marker}"


def test_doctrine_text_surfaces_all_22_avenues():
    for a in REVENUE_AVENUES:
        assert a["display_name"] in GM_REVENUE_DOCTRINE


def test_doctrine_text_states_floors_are_minimums():
    assert "MINIMUMS" in GM_REVENUE_DOCTRINE
    assert "US$30,000" in GM_REVENUE_DOCTRINE
    assert "US$1,000,000" in GM_REVENUE_DOCTRINE


def test_doctrine_text_forbids_narrowing():
    assert "narrow" in GM_REVENUE_DOCTRINE.lower()
    assert "PRESENT_IN_CODE_ONLY" in GM_REVENUE_DOCTRINE
    assert "DISABLED_BY_OPERATOR" in GM_REVENUE_DOCTRINE


def test_operator_prompt_carries_wide_doctrine():
    from apps.api.services.gm_system_prompt import GM_OPERATOR_PROMPT
    assert "GM OPERATING DIRECTIVE" in GM_OPERATOR_PROMPT
    assert "ANTI-NARROWING RULE" in GM_OPERATOR_PROMPT
    assert "B2B services" in GM_OPERATOR_PROMPT
    assert "Sponsor / brand deals" in GM_OPERATOR_PROMPT


def test_priority_rank_includes_dormant_avenue_activation():
    labels = [r["label"] for r in PRIORITY_RANK]
    assert "dormant_avenue_activation" in labels
    assert "revenue_at_immediate_risk" in labels
    assert "floor_gap_math" in labels


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
async def test_doctrine_endpoint_exposes_22_avenues_and_all_engines(
    api_client, sample_org_data,
):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/doctrine", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_avenues"] == 22
    assert body["total_engines"] == len(STRATEGIC_ENGINES)
    assert body["total_canonical_tables"] == len(CANONICAL_DATA_TABLES)
    assert len(body["status_flags"]) == 5
    assert len(body["revenue_avenues"]) == 22
    assert len(body["doctrine_rules"]) == 5


@pytest.mark.asyncio
async def test_floor_status_combines_payments_and_creator_revenue(
    api_client, db_session, sample_org_data,
):
    from packages.db.models.proposals import Payment

    headers, org_id = await _auth(api_client, sample_org_data)
    # Seed $5,000 B2B payment
    db_session.add(Payment(
        org_id=org_id, provider="stripe",
        provider_event_id=f"evt_{uuid.uuid4().hex[:10]}",
        amount_cents=500_000, currency="usd", status="succeeded",
        completed_at=datetime.now(timezone.utc) - timedelta(days=5),
        customer_email="test@example.com",
    ))
    await db_session.commit()

    r = await api_client.get("/api/v1/gm/floor-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["trailing_30d_cents"] >= 500_000
    assert "avenue_breakdown" in body
    # Must have a b2b_services entry
    b2b = next((b for b in body["avenue_breakdown"] if b["avenue_id"] == "b2b_services"), None)
    assert b2b is not None
    assert b2b["revenue_cents_30d"] == 500_000


@pytest.mark.asyncio
async def test_avenue_portfolio_returns_all_22_with_live_status(
    api_client, sample_org_data,
):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/avenue-portfolio", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_avenues"] == 22
    assert len(body["avenues"]) == 22
    # Every avenue must carry both doctrine_status and live_status
    for a in body["avenues"]:
        assert a["doctrine_status"] in STATUS_FLAGS
        assert a["live_status"] in STATUS_FLAGS
        assert "n" in a and 1 <= a["n"] <= 22
    # Status histogram
    assert "status_histogram" in body


@pytest.mark.asyncio
async def test_engine_status_returns_all_engines_classified(
    api_client, sample_org_data,
):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/engine-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_engines"] == len(STRATEGIC_ENGINES)
    assert "status_histogram" in body
    assert "family_histogram" in body
    # Every engine has live_status
    for e in body["engines"]:
        assert e["live_status"] in STATUS_FLAGS
        assert e["doctrine_status"] in STATUS_FLAGS


@pytest.mark.asyncio
async def test_ask_operator_returns_structured_asks(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/ask-operator", headers=headers)
    assert r.status_code == 200
    body = r.json()
    for field in ("total_asks", "by_category", "asks"):
        assert field in body
    # Each ask must have priority + request + category
    for a in body["asks"]:
        assert "priority" in a
        assert "request" in a
        assert "category" in a


@pytest.mark.asyncio
async def test_unlock_plans_returns_dormant_avenues_with_plans(
    api_client, sample_org_data,
):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/unlock-plans", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "total_unlock_candidates" in body
    assert "plans" in body
    # Each plan must have avenue_id + live_status + action_class
    for p in body["plans"]:
        assert p["live_status"] in (STATUS_LIVE_BUT_DORMANT, STATUS_PRESENT_IN_CODE_ONLY)
        assert p["action_class"] == "approval_required"


@pytest.mark.asyncio
async def test_game_plan_ranks_across_all_avenues(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/game-plan", headers=headers)
    assert r.status_code == 200
    body = r.json()
    labels = {a["label"] for a in body["actions"]}
    assert "floor_gap_math" in labels
    # Dormant-avenue activation should appear when floor unmet
    assert "dormant_avenue_activation" in labels


@pytest.mark.asyncio
async def test_startup_inspection_includes_all_wide_fields(
    api_client, sample_org_data,
):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/startup-inspection", headers=headers)
    assert r.status_code == 200
    body = r.json()
    for field in (
        "floor_status", "avenue_portfolio", "engine_status", "pipeline_state",
        "bottlenecks", "closest_revenue", "blocking_floors", "game_plan",
        "ask_operator", "unlock_plans",
        "situation_report_lines",
        "priority_rank_reference", "forbidden_behaviors",
        "total_avenues", "total_engines",
    ):
        assert field in body, f"missing field {field}"
    # 7-line situation report (Batch 7A-WIDE format)
    assert len(body["situation_report_lines"]) == 7
    assert body["total_avenues"] == 22


@pytest.mark.asyncio
async def test_floor_status_does_not_double_count_stripe_origin_events(
    api_client, db_session, sample_org_data,
):
    """The canonical bug: a Stripe payment writes to BOTH ``payments``
    and ``creator_revenue_events`` (event_type='stripe_charge_sync').
    Recognized revenue must count it ONCE, not twice.
    """
    from packages.db.models.core import Brand
    from packages.db.models.creator_revenue import CreatorRevenueEvent
    from packages.db.models.proposals import Payment

    headers, org_id = await _auth(api_client, sample_org_data)

    # Seed a $1,000 payment
    event_id = f"evt_dedup_{uuid.uuid4().hex[:10]}"
    db_session.add(Payment(
        org_id=org_id, provider="stripe",
        provider_event_id=event_id,
        amount_cents=100_000, currency="usd", status="succeeded",
        completed_at=datetime.now(timezone.utc) - timedelta(days=1),
        customer_email="dedup@example.com",
    ))

    # Seed a matching creator_revenue_event that represents the SAME
    # Stripe transaction. Per the rule this must NOT add to the total.
    brand = (
        await db_session.execute(
            select(Brand).where(Brand.organization_id == org_id).limit(1)
        )
    ).scalar_one_or_none()
    if brand is not None:
        db_session.add(CreatorRevenueEvent(
            brand_id=brand.id,
            avenue_type="ugc_services",
            event_type="stripe_charge_sync",
            revenue=1000.00,  # $1,000 stored in dollars (creator_revenue_events schema)
            cost=0.0,
            profit=1000.00,
            description="Should be excluded — duplicates the $1,000 Payment above",
            metadata_json={"stripe_event_id": event_id},
        ))
    await db_session.commit()

    r = await api_client.get("/api/v1/gm/floor-status", headers=headers)
    assert r.status_code == 200
    body = r.json()
    breakdown = body["recognized_revenue_breakdown"]

    # Total must be $1,000 (payments only), not $2,000 (double-counted)
    assert body["trailing_30d_cents"] == 100_000, (
        f"Expected 100_000 ($1,000), got {body['trailing_30d_cents']}. "
        f"Double-count detected. Breakdown: {breakdown}"
    )
    # Payments ledger contributes the full $1,000
    assert breakdown["from_payments_cents"] == 100_000
    # Creator events contribute zero because the row was stripe_charge_sync
    assert breakdown["from_creator_events_cents"] == 0
    # The excluded row is counted separately for audit
    if brand is not None:
        assert breakdown["excluded_stripe_origin_events_count"] >= 1


@pytest.mark.asyncio
async def test_floor_status_includes_non_stripe_creator_revenue(
    api_client, db_session, sample_org_data,
):
    """A manual creator_revenue_event (not from Stripe) MUST be counted
    in recognized revenue — it represents real money that does not
    flow through the payments table.
    """
    from packages.db.models.core import Brand
    from packages.db.models.creator_revenue import CreatorRevenueEvent

    headers, org_id = await _auth(api_client, sample_org_data)

    brand = (
        await db_session.execute(
            select(Brand).where(Brand.organization_id == org_id).limit(1)
        )
    ).scalar_one_or_none()
    if brand is None:
        pytest.skip("No brand for this org to attach creator_revenue_events to")

    # Seed a manual (non-Stripe) revenue event for $500
    db_session.add(CreatorRevenueEvent(
        brand_id=brand.id,
        avenue_type="licensing",
        event_type="manual_log",           # NOT stripe_/shopify_
        revenue=500.00,
        cost=0.0,
        profit=500.00,
        description="Manual licensing payment — wire transfer",
    ))
    await db_session.commit()

    r = await api_client.get("/api/v1/gm/floor-status", headers=headers)
    assert r.status_code == 200
    body = r.json()

    assert body["trailing_30d_cents"] >= 50_000, (
        f"Non-Stripe creator_revenue_event should have been counted. "
        f"Got {body['trailing_30d_cents']}; "
        f"breakdown: {body['recognized_revenue_breakdown']}"
    )
    # Licensing avenue must appear in breakdown with $500
    licensing = next(
        (a for a in body["avenue_breakdown"] if a["avenue_id"] == "licensing"),
        None,
    )
    assert licensing is not None, f"licensing missing from avenue_breakdown: {body['avenue_breakdown']}"
    assert licensing["from_creator_events_cents"] == 50_000


@pytest.mark.asyncio
async def test_floor_status_plan_data_ledgers_do_not_add_to_total(
    api_client, db_session, sample_org_data,
):
    """Plan-data ledgers (high_ticket_deals, sponsor_opportunities,
    subscription_events, credit_transactions, pack_purchases, af_*)
    are surfaced in ``plan_data_ledgers`` but MUST NOT add to
    trailing_30d_cents.
    """
    from packages.db.models.proposals import Payment

    headers, org_id = await _auth(api_client, sample_org_data)

    # Exactly $200 of recognized revenue from payments
    db_session.add(Payment(
        org_id=org_id, provider="stripe",
        provider_event_id=f"evt_plan_{uuid.uuid4().hex[:10]}",
        amount_cents=20_000, currency="usd", status="succeeded",
        completed_at=datetime.now(timezone.utc) - timedelta(days=2),
        customer_email="plan@example.com",
    ))
    await db_session.commit()

    r = await api_client.get("/api/v1/gm/floor-status", headers=headers)
    body = r.json()
    # Total is exactly payments, regardless of whatever plan-data rows
    # exist elsewhere.
    assert body["trailing_30d_cents"] == 20_000, (
        f"trailing_30d must equal payments total alone; got "
        f"{body['trailing_30d_cents']}. Plan-data bled through."
    )
    # plan_data_ledgers field must exist and be a list
    assert isinstance(body["plan_data_ledgers"], list)


@pytest.mark.asyncio
async def test_floor_status_carries_canonical_rule_text(
    api_client, sample_org_data,
):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.get("/api/v1/gm/floor-status", headers=headers)
    body = r.json()
    rule = body.get("recognized_revenue_rule", "")
    for marker in ("payments", "creator_revenue_events", "stripe_", "PLAN DATA"):
        assert marker in rule, f"rule missing marker {marker!r}: {rule}"


@pytest.mark.asyncio
async def test_doctrine_text_has_recognized_revenue_rule(api_client, sample_org_data):
    from apps.api.services.gm_doctrine import GM_REVENUE_DOCTRINE, RECOGNIZED_REVENUE_RULE
    assert "RECOGNIZED-REVENUE RULE" in RECOGNIZED_REVENUE_RULE
    assert "RECOGNIZED-REVENUE RULE" in GM_REVENUE_DOCTRINE
    assert "payments" in GM_REVENUE_DOCTRINE
    assert "stripe_charge_sync" in GM_REVENUE_DOCTRINE


@pytest.mark.asyncio
async def test_all_gm_endpoints_require_operator_auth(api_client):
    for path in (
        "/api/v1/gm/doctrine",
        "/api/v1/gm/floor-status",
        "/api/v1/gm/avenue-portfolio",
        "/api/v1/gm/engine-status",
        "/api/v1/gm/pipeline-state",
        "/api/v1/gm/bottlenecks",
        "/api/v1/gm/closest-revenue",
        "/api/v1/gm/blocking-floors",
        "/api/v1/gm/game-plan",
        "/api/v1/gm/ask-operator",
        "/api/v1/gm/unlock-plans",
        "/api/v1/gm/startup-inspection",
    ):
        r = await api_client.get(path)
        assert r.status_code in (401, 403), f"{path} returned {r.status_code}"
