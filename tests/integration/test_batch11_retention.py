"""Batch 11 — retention / renewal / reactivation layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from apps.api.services.retention_service import (
    cancel_subscription,
    compute_retention_book,
    recurring_period_for_package,
    scan_retention_state,
    trigger_reactivation,
    trigger_renewal,
    trigger_upsell,
)
from packages.db.models.clients import Client, ClientRetentionEvent
from packages.db.models.core import Brand, Organization
from packages.db.models.proposals import Proposal


async def _ensure_org_with_brand(db_session, sample_org_data):
    name = sample_org_data["organization_name"]
    slug = f"b11-{uuid.uuid4().hex[:10]}"
    org = Organization(name=name, slug=slug)
    db_session.add(org)
    await db_session.flush()
    brand = Brand(
        organization_id=org.id,
        name=f"{name} Brand",
        slug=f"{slug}-brand",
        is_active=True,
    )
    db_session.add(brand)
    await db_session.flush()
    return org.id, brand.id


async def _seed_client(
    db_session,
    org_id,
    brand_id,
    *,
    last_paid_days_ago: int = 0,
    is_recurring: bool = False,
    period_days: int | None = None,
    avenue_slug: str = "b2b_services",
    retention_state: str = "active",
):
    now = datetime.now(timezone.utc)
    c = Client(
        org_id=org_id,
        brand_id=brand_id,
        primary_email=f"client_{uuid.uuid4().hex[:8]}@test.com",
        display_name=f"Client {uuid.uuid4().hex[:6]}",
        status="active",
        activated_at=now - timedelta(days=last_paid_days_ago),
        last_paid_at=now - timedelta(days=last_paid_days_ago),
        total_paid_cents=250000,
        avenue_slug=avenue_slug,
        is_recurring=is_recurring,
        recurring_period_days=period_days,
        retention_state=retention_state,
    )
    db_session.add(c)
    await db_session.flush()
    return c


# ─────────────────────────────────────────────────────────────────────────
#  1. recurring_period_for_package mapping
# ─────────────────────────────────────────────────────────────────────────


def test_recurring_period_map_for_known_packages():
    assert recurring_period_for_package("momentum_engine") == 30
    assert recurring_period_for_package("paid_media_engine") == 30
    assert recurring_period_for_package("creative_command") == 30
    assert recurring_period_for_package("premium_access_annual") == 365
    assert recurring_period_for_package("one_off_unknown_pkg") is None
    assert recurring_period_for_package(None) is None


# ─────────────────────────────────────────────────────────────────────────
#  2. scan_retention_state — each state transition
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_scan_flags_renewal_due_for_recurring_client_within_lead_window(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    # last paid 28 days ago, period 30 → within 3-day lead window
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=28,
        is_recurring=True,
        period_days=30,
    )
    result = await scan_retention_state(db_session, c)
    assert result["state"] == "renewal_due"
    assert c.churn_risk_score > 0.1
    await db_session.commit()


@pytest.mark.asyncio
async def test_scan_flags_renewal_overdue_and_then_lapsed(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    # last paid 40 days ago, period 30 → past next_renewal + 7d cutoff
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=40,
        is_recurring=True,
        period_days=30,
    )
    r = await scan_retention_state(db_session, c)
    assert r["state"] == "renewal_overdue"

    # Now move to lapsed: 65 days ago
    c.last_paid_at = datetime.now(timezone.utc) - timedelta(days=65)
    r = await scan_retention_state(db_session, c)
    assert r["state"] == "lapsed"
    await db_session.commit()


@pytest.mark.asyncio
async def test_scan_flags_one_time_client_lapsed(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=75,
        is_recurring=False,
    )
    r = await scan_retention_state(db_session, c)
    assert r["state"] == "lapsed"
    await db_session.commit()


@pytest.mark.asyncio
async def test_scan_churned_is_terminal(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=5,
        is_recurring=True,
        period_days=30,
        retention_state="churned",
    )
    r = await scan_retention_state(db_session, c)
    assert r["state"] == "churned"
    assert r.get("terminal") is True
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  3. trigger_renewal — creates proposal + event + debounces
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_renewal_creates_new_proposal_and_event(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=35,
        is_recurring=True,
        period_days=30,
        avenue_slug="ugc_services",
    )
    result = await trigger_renewal(
        db_session,
        client=c,
        package_slug="ugc_monthly",
        line_items=[
            {
                "description": "Monthly UGC pack",
                "unit_amount_cents": 250000,
                "quantity": 1,
                "currency": "usd",
                "position": 0,
            }
        ],
        actor_id="op@test",
    )
    assert result["triggered"] is True
    assert result["proposal_id"]
    p = (await db_session.execute(select(Proposal).where(Proposal.id == uuid.UUID(result["proposal_id"])))).scalar_one()
    assert p.avenue_slug == "ugc_services"
    assert (p.extra_json or {}).get("retention_source") == "renewal"

    evt = (
        await db_session.execute(
            select(ClientRetentionEvent).where(ClientRetentionEvent.id == uuid.UUID(result["retention_event_id"]))
        )
    ).scalar_one()
    assert evt.event_type == "renewal_triggered"
    assert evt.target_proposal_id == p.id

    # Debounce: second call within 24h returns triggered=False
    again = await trigger_renewal(
        db_session,
        client=c,
        package_slug="ugc_monthly",
        line_items=[{"description": "x", "unit_amount_cents": 100000, "quantity": 1, "currency": "usd", "position": 0}],
        actor_id="op@test",
    )
    assert again["triggered"] is False
    assert again["reason"] == "debounce_24h"
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  4. trigger_reactivation — lapsed client
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_reactivation_writes_event_even_without_smtp(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=90,
        retention_state="lapsed",
    )
    result = await trigger_reactivation(
        db_session,
        client=c,
        actor_id="op@test",
    )
    assert result["triggered"] is True
    # No SMTP configured in test env → sent=False but event still lands
    assert result["sent"] is False

    evt = (
        await db_session.execute(
            select(ClientRetentionEvent).where(ClientRetentionEvent.id == uuid.UUID(result["retention_event_id"]))
        )
    ).scalar_one()
    assert evt.event_type == "reactivation_sent"
    assert (evt.details_json or {}).get("send_success") is False
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  5. trigger_upsell — expansion candidate
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_trigger_upsell_creates_proposal_with_retention_source(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=20,
        avenue_slug="high_ticket",
        retention_state="expansion_candidate",
    )
    result = await trigger_upsell(
        db_session,
        client=c,
        package_slug="high_ticket_expansion",
        line_items=[
            {
                "description": "Expansion engagement",
                "unit_amount_cents": 5000000,
                "quantity": 1,
                "currency": "usd",
                "position": 0,
            }
        ],
        actor_id="op@test",
    )
    assert result["triggered"] is True
    p = (await db_session.execute(select(Proposal).where(Proposal.id == uuid.UUID(result["proposal_id"])))).scalar_one()
    assert p.avenue_slug == "high_ticket"
    assert (p.extra_json or {}).get("retention_source") == "upsell"
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  6. cancel_subscription — terminal, idempotent
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancel_subscription_is_terminal_and_idempotent(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    c = await _seed_client(
        db_session,
        org_id,
        brand_id,
        last_paid_days_ago=5,
        is_recurring=True,
        period_days=30,
    )
    r1 = await cancel_subscription(
        db_session,
        client=c,
        reason="operator_decision",
        actor_id="op@test",
    )
    assert r1["triggered"] is True
    assert c.retention_state == "churned"
    assert c.is_recurring is False

    # Second call → no-op
    r2 = await cancel_subscription(
        db_session,
        client=c,
        reason="already_cancelled",
        actor_id="op@test",
    )
    assert r2["triggered"] is False
    assert r2["reason"] == "already_churned"

    # Scan after cancel → state stays churned
    r3 = await scan_retention_state(db_session, c)
    assert r3["state"] == "churned"
    assert r3.get("terminal") is True
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  7. compute_retention_book — per-avenue rollup
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compute_retention_book_rolls_up_by_avenue(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    await _seed_client(db_session, org_id, brand_id, avenue_slug="b2b_services", retention_state="active")
    await _seed_client(db_session, org_id, brand_id, avenue_slug="b2b_services", retention_state="lapsed")
    await _seed_client(db_session, org_id, brand_id, avenue_slug="ugc_services", retention_state="renewal_due")
    book = await compute_retention_book(db_session, org_id=org_id)
    assert book["by_avenue"]["b2b_services"]["active"] == 1
    assert book["by_avenue"]["b2b_services"]["lapsed"] == 1
    assert book["by_avenue"]["ugc_services"]["renewal_due"] == 1
    assert book["totals"]["active"] >= 1
    assert book["totals"]["lapsed"] >= 1
    assert book["totals"]["renewal_due"] >= 1


# ─────────────────────────────────────────────────────────────────────────
#  8. Endpoint-registration + auth tests
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch11_endpoints_all_registered(api_client):
    r = await api_client.get("/openapi.json")
    paths = set(r.json()["paths"].keys())
    for p in (
        "/api/v1/gm/write/clients/{client_id}/renew",
        "/api/v1/gm/write/clients/{client_id}/reactivate",
        "/api/v1/gm/write/clients/{client_id}/upsell",
        "/api/v1/gm/write/clients/{client_id}/cancel-subscription",
    ):
        assert p in paths, f"missing Batch 11 endpoint {p}"


@pytest.mark.asyncio
async def test_batch11_endpoints_require_auth(api_client):
    stub = "00000000-0000-0000-0000-000000000000"
    checks = [
        (
            "POST",
            f"/api/v1/gm/write/clients/{stub}/renew",
            {"package_slug": "x", "line_items": [{"description": "x", "unit_amount_cents": 100000}]},
        ),
        ("POST", f"/api/v1/gm/write/clients/{stub}/reactivate", {}),
        (
            "POST",
            f"/api/v1/gm/write/clients/{stub}/upsell",
            {"package_slug": "x", "line_items": [{"description": "x", "unit_amount_cents": 100000}]},
        ),
        ("POST", f"/api/v1/gm/write/clients/{stub}/cancel-subscription", {"reason": "x"}),
    ]
    for method, path, body in checks:
        r = await api_client.request(method, path, json=body)
        assert r.status_code == 401, f"{path} must 401 (got {r.status_code})"
