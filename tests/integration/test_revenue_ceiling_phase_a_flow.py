"""Integration tests: Revenue Ceiling Phase A APIs, persistence, and content → owned-audience chain."""

import uuid

import pytest
from sqlalchemy import select

from packages.db.enums import ContentType
from packages.db.models.content import ContentItem
from packages.db.models.revenue_ceiling_phase_a import FunnelLeakFix, OfferLadder


async def _auth_brand(api_client, sample_org_data):
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    brand = await api_client.post(
        "/api/v1/brands/",
        json={"name": "RC Phase A Brand", "slug": "rc-phase-a", "niche": "personal finance"},
        headers=headers,
    )
    bid = brand.json()["id"]
    await api_client.post(
        "/api/v1/accounts/",
        json={
            "brand_id": bid,
            "platform": "youtube",
            "platform_username": "@rc_yt",
            "niche_focus": "finance",
            "posting_capacity_per_day": 2,
            "scale_role": "flagship",
        },
        headers=headers,
    )
    await api_client.post(
        "/api/v1/offers/",
        json={
            "brand_id": bid,
            "name": "Affiliate",
            "monetization_method": "affiliate",
            "epc": 2.5,
            "conversion_rate": 0.03,
            "payout_amount": 40.0,
        },
        headers=headers,
    )
    return headers, bid


@pytest.mark.asyncio
async def test_recompute_and_read_all_endpoints(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)

    for path in [
        f"/api/v1/brands/{bid}/offer-ladders/recompute",
        f"/api/v1/brands/{bid}/owned-audience/recompute",
        f"/api/v1/brands/{bid}/message-sequences/generate",
        f"/api/v1/brands/{bid}/funnel-leaks/recompute",
    ]:
        r = await api_client.post(path, headers=headers)
        assert r.status_code == 200, f"{path}: {r.text}"

    ladders = await api_client.get(f"/api/v1/brands/{bid}/offer-ladders", headers=headers)
    assert ladders.status_code == 200
    assert len(ladders.json()) >= 1
    assert "expected_ltv_contribution" in ladders.json()[0]

    bundle = await api_client.get(f"/api/v1/brands/{bid}/owned-audience", headers=headers)
    assert bundle.status_code == 200
    b = bundle.json()
    assert "assets" in b and "events" in b
    assert len(b["assets"]) >= 1

    seqs = await api_client.get(f"/api/v1/brands/{bid}/message-sequences", headers=headers)
    assert seqs.status_code == 200
    assert len(seqs.json()) >= 1
    assert seqs.json()[0]["steps"]

    metrics = await api_client.get(f"/api/v1/brands/{bid}/funnel-stage-metrics", headers=headers)
    assert metrics.status_code == 200
    assert len(metrics.json()) >= 1

    leaks = await api_client.get(f"/api/v1/brands/{bid}/funnel-leaks", headers=headers)
    assert leaks.status_code == 200
    assert len(leaks.json()) >= 1
    assert leaks.json()[0]["recommended_fix"]


@pytest.mark.asyncio
async def test_gets_before_recompute_are_empty(api_client, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    r0 = await api_client.get(f"/api/v1/brands/{bid}/offer-ladders", headers=headers)
    assert r0.status_code == 200 and r0.json() == []
    r_oa = await api_client.get(f"/api/v1/brands/{bid}/owned-audience", headers=headers)
    assert r_oa.status_code == 200
    assert r_oa.json()["assets"] == [] and r_oa.json()["events"] == []
    for path in [
        f"/api/v1/brands/{bid}/message-sequences",
        f"/api/v1/brands/{bid}/funnel-stage-metrics",
        f"/api/v1/brands/{bid}/funnel-leaks",
    ]:
        r = await api_client.get(path, headers=headers)
        assert r.status_code == 200
        assert r.json() == []


@pytest.mark.asyncio
async def test_content_item_to_owned_audience_event(api_client, db_session, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    bid_uuid = uuid.UUID(bid)
    ci = ContentItem(
        brand_id=bid_uuid,
        title="Lead magnet hook video",
        content_type=ContentType.SHORT_VIDEO,
        tags={"family": "how_to"},
    )
    db_session.add(ci)
    await db_session.commit()

    rc = await api_client.post(f"/api/v1/brands/{bid}/owned-audience/recompute", headers=headers)
    assert rc.status_code == 200

    bundle = await api_client.get(f"/api/v1/brands/{bid}/owned-audience", headers=headers)
    assert bundle.status_code == 200
    events = bundle.json()["events"]
    assert any(e.get("content_item_id") == str(ci.id) for e in events)


@pytest.mark.asyncio
async def test_funnel_leak_fix_persisted(api_client, db_session, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    bid_uuid = uuid.UUID(bid)
    r = await api_client.post(f"/api/v1/brands/{bid}/funnel-leaks/recompute", headers=headers)
    assert r.status_code == 200

    rows = list(
        (await db_session.execute(select(FunnelLeakFix).where(FunnelLeakFix.brand_id == bid_uuid))).scalars().all()
    )
    assert len(rows) >= 1
    assert rows[0].recommended_fix


@pytest.mark.asyncio
async def test_offer_ladder_persisted_rows(api_client, db_session, sample_org_data):
    headers, bid = await _auth_brand(api_client, sample_org_data)
    bid_uuid = uuid.UUID(bid)
    await api_client.post(f"/api/v1/brands/{bid}/offer-ladders/recompute", headers=headers)

    rows = list((await db_session.execute(select(OfferLadder).where(OfferLadder.brand_id == bid_uuid))).scalars().all())
    assert len(rows) >= 1
    assert rows[0].explanation


def test_celery_tasks_registered():
    import workers.revenue_ceiling_worker.tasks  # noqa: F401 — registers tasks on the Celery app
    from workers.celery_app import app

    names = [
        "workers.revenue_ceiling_worker.tasks.recompute_all_offer_ladders",
        "workers.revenue_ceiling_worker.tasks.recompute_all_owned_audience",
        "workers.revenue_ceiling_worker.tasks.refresh_all_message_sequences",
        "workers.revenue_ceiling_worker.tasks.recompute_all_funnel_leaks",
    ]
    for n in names:
        assert n in app.tasks, f"missing task {n}"


@pytest.mark.asyncio
async def test_lead_magnet_to_sequence_chain(api_client, sample_org_data):
    """After generating sequences, nurture / conversion types exist with steps (lead-magnet → nurture path)."""
    headers, bid = await _auth_brand(api_client, sample_org_data)
    await api_client.post(f"/api/v1/brands/{bid}/message-sequences/generate", headers=headers)
    seqs = (await api_client.get(f"/api/v1/brands/{bid}/message-sequences", headers=headers)).json()
    types = {s["sequence_type"] for s in seqs}
    assert "nurture" in types
    nurture = next(s for s in seqs if s["sequence_type"] == "nurture")
    assert len(nurture["steps"]) >= 1
    assert nurture["steps"][0]["body_template"]
