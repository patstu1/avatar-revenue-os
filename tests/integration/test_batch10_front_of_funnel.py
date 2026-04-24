"""Batch 10 — front-of-funnel GM control layer tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from apps.api.services.gm_front_of_funnel_service import (
    bulk_import_leads_with_avenue,
    launch_outreach_for_segment,
    pause_outreach_for_avenue,
    qualify_lead,
    rewrite_draft,
    route_lead_to_proposal,
)
from packages.db.models.core import Brand, Organization
from packages.db.models.email_pipeline import (
    EmailMessage,
    EmailReplyDraft,
    EmailThread,
    InboxConnection,
)
from packages.db.models.expansion_pack2_phase_c import (
    SponsorOutreachSequence,
    SponsorTarget,
)


async def _ensure_org_with_brand(db_session, sample_org_data) -> tuple[uuid.UUID, uuid.UUID]:
    name = sample_org_data["organization_name"]
    slug = f"b10-{uuid.uuid4().hex[:10]}"
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


# ─────────────────────────────────────────────────────────────────────────
#  1. bulk_import_leads_with_avenue — propagates avenue_slug
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bulk_import_tags_every_row_with_avenue_slug(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    result = await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="b2b_services",
        rows=[
            {"company_name": "Alpha Co", "email": "a@alpha.test"},
            {"company_name": "Beta Co", "email": "b@beta.test"},
        ],
    )
    assert result["imported"] == 2
    rows = (await db_session.execute(select(SponsorTarget).where(SponsorTarget.brand_id == brand_id))).scalars().all()
    assert len(rows) == 2
    assert all(r.avenue_slug == "b2b_services" for r in rows)
    await db_session.commit()


@pytest.mark.asyncio
async def test_bulk_import_refuses_missing_company_name(db_session, sample_org_data):
    org_id, _ = await _ensure_org_with_brand(db_session, sample_org_data)
    result = await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="b2b_services",
        rows=[{"company_name": "", "email": "x@y.test"}],
    )
    assert result["imported"] == 0
    assert result["skipped"] == 1
    assert any("missing company_name" in e for e in result["errors"])
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  2. qualify_lead — tier + intent + avenue override
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_qualify_lead_sets_tier_fit_score_and_avenue_override(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    # Seed lead
    imp = await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="ugc_services",
        rows=[{"company_name": "Qual Co", "email": "q@qual.test"}],
    )
    lead_id = uuid.UUID(imp["first_lead_id"])

    result = await qualify_lead(
        db_session,
        org_id=org_id,
        lead_id=lead_id,
        intent="offer_request",
        tier="hot",
        reason_codes=["asked_for_pricing", "budget_confirmed"],
        avenue_slug_override="high_ticket",
        notes="Live proof",
        actor_id="tester@example.com",
    )
    assert result["tier"] == "hot"
    assert result["avenue_slug"] == "high_ticket"
    assert result["fit_score"] >= 0.85

    await db_session.refresh(
        (await db_session.execute(select(SponsorTarget).where(SponsorTarget.id == lead_id))).scalar_one()
    )
    await db_session.commit()


@pytest.mark.asyncio
async def test_qualify_rejects_bad_tier(db_session, sample_org_data):
    org_id, _ = await _ensure_org_with_brand(db_session, sample_org_data)
    imp = await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="b2b_services",
        rows=[{"company_name": "Bad Tier Co", "email": "bt@example.com"}],
    )
    lid = uuid.UUID(imp["first_lead_id"])
    with pytest.raises(ValueError):
        await qualify_lead(
            db_session,
            org_id=org_id,
            lead_id=lid,
            intent="offer_request",
            tier="super_hot",  # invalid
        )


# ─────────────────────────────────────────────────────────────────────────
#  3. launch + pause outreach
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_outreach_launch_creates_sequences_with_avenue_slug(db_session, sample_org_data):
    org_id, brand_id = await _ensure_org_with_brand(db_session, sample_org_data)
    await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="sponsor_deals",
        rows=[{"company_name": "Out1", "email": "o1@x.test"}, {"company_name": "Out2", "email": "o2@x.test"}],
    )
    result = await launch_outreach_for_segment(
        db_session,
        org_id=org_id,
        avenue_slug="sponsor_deals",
        sequence_template_slug="sponsor_intro_v1",
    )
    assert result["scheduled"] == 2

    rows = (
        (
            await db_session.execute(
                select(SponsorOutreachSequence).where(SponsorOutreachSequence.avenue_slug == "sponsor_deals")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert all(r.sequence_name == "sponsor_intro_v1" for r in rows)
    assert all(r.avenue_slug == "sponsor_deals" for r in rows)
    await db_session.commit()


@pytest.mark.asyncio
async def test_outreach_pause_deactivates_sequences(db_session, sample_org_data):
    org_id, _ = await _ensure_org_with_brand(db_session, sample_org_data)
    await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="b2b_services",
        rows=[{"company_name": "Pause Co", "email": "p@pause.test"}],
    )
    await launch_outreach_for_segment(
        db_session,
        org_id=org_id,
        avenue_slug="b2b_services",
    )
    pause_result = await pause_outreach_for_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="b2b_services",
    )
    assert pause_result["paused"] >= 1
    active = (
        (
            await db_session.execute(
                select(SponsorOutreachSequence).where(
                    SponsorOutreachSequence.avenue_slug == "b2b_services",
                    SponsorOutreachSequence.is_active.is_(True),
                )
            )
        )
        .scalars()
        .all()
    )
    assert active == []
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  4. rewrite_draft — versioning + avenue passthrough
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rewrite_draft_appends_version_and_flips_to_pending(db_session, sample_org_data):
    org_id, _ = await _ensure_org_with_brand(db_session, sample_org_data)
    ic = InboxConnection(
        org_id=org_id,
        email_address="rw@test.com",
        display_name="Rw",
        provider="imap",
        host="imap.test",
        port=993,
        auth_method="oauth",
        credential_provider_key="gmail_oauth",
        status="active",
        consecutive_failures=0,
        messages_synced_total=0,
        is_active=True,
    )
    db_session.add(ic)
    await db_session.flush()
    now = datetime.now(timezone.utc)
    t = EmailThread(
        inbox_connection_id=ic.id,
        org_id=org_id,
        provider_thread_id=f"rw_{uuid.uuid4().hex[:8]}",
        subject="rw thread",
        direction="inbound",
        sales_stage="discovery",
        reply_status="pending",
        message_count=1,
        from_email="prospect@test.com",
        from_name="P",
        first_message_at=now,
        last_message_at=now,
        last_inbound_at=now,
        is_active=True,
        avenue_slug="b2b_services",
    )
    db_session.add(t)
    await db_session.flush()
    m = EmailMessage(
        thread_id=t.id,
        inbox_connection_id=ic.id,
        org_id=org_id,
        provider_message_id=f"m_{uuid.uuid4().hex[:8]}",
        direction="inbound",
        from_email="prospect@test.com",
        subject="pricing?",
        snippet="pricing",
        message_date=now,
        size_bytes=10,
        is_active=True,
        avenue_slug="b2b_services",
    )
    db_session.add(m)
    await db_session.flush()
    d = EmailReplyDraft(
        thread_id=t.id,
        message_id=m.id,
        org_id=org_id,
        to_email="prospect@test.com",
        subject="Original subject",
        body_text="Original body",
        reply_mode="draft",
        status="approved",
        confidence=0.8,
        is_active=True,
        avenue_slug="b2b_services",
    )
    db_session.add(d)
    await db_session.flush()

    updated = await rewrite_draft(
        db_session,
        draft=d,
        new_subject="New subject",
        new_body_text="New body",
        reason="tighter copy",
        actor_id="rewriter@test.com",
    )
    assert updated.subject == "New subject"
    assert updated.body_text == "New body"
    assert updated.status == "pending"  # approved → pending on rewrite
    history = updated.rewrite_history_json or {}
    versions = history.get("versions", [])
    assert len(versions) == 1
    assert versions[0]["previous_subject"] == "Original subject"
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  5. route_lead_to_proposal — avenue_slug carried into Proposal
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_route_lead_to_proposal_carries_avenue_forward(db_session, sample_org_data):
    org_id, _ = await _ensure_org_with_brand(db_session, sample_org_data)
    imp = await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="high_ticket",
        rows=[{"company_name": "Big Co", "email": "buyer@big.test", "contact_name": "Big CEO"}],
    )
    lid = uuid.UUID(imp["first_lead_id"])

    proposal = await route_lead_to_proposal(
        db_session,
        org_id=org_id,
        lead_id=lid,
        package_slug="high_ticket_starter",
        line_items=[
            {
                "description": "Starter engagement",
                "unit_amount_cents": 2500000,
                "quantity": 1,
                "currency": "usd",
                "position": 0,
            }
        ],
        title="High-ticket proposal",
        actor_id="router@test.com",
    )
    assert proposal.avenue_slug == "high_ticket"
    assert proposal.total_amount_cents == 2500000
    assert proposal.package_slug == "high_ticket_starter"
    extra = proposal.extra_json or {}
    assert extra.get("source_lead_id") == str(lid)
    await db_session.commit()


@pytest.mark.asyncio
async def test_route_lead_rejects_missing_email(db_session, sample_org_data):
    org_id, _ = await _ensure_org_with_brand(db_session, sample_org_data)
    imp = await bulk_import_leads_with_avenue(
        db_session,
        org_id=org_id,
        avenue_slug="b2b_services",
        rows=[{"company_name": "NoEmail"}],  # no email
    )
    lid = uuid.UUID(imp["first_lead_id"])
    with pytest.raises(ValueError):
        await route_lead_to_proposal(
            db_session,
            org_id=org_id,
            lead_id=lid,
            package_slug="pkg",
            line_items=[
                {"description": "x", "unit_amount_cents": 100000, "quantity": 1, "currency": "usd", "position": 0}
            ],
        )


# ─────────────────────────────────────────────────────────────────────────
#  6. Endpoint-registration + auth tests
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch10_endpoints_all_registered(api_client):
    r = await api_client.get("/openapi.json")
    paths = set(r.json()["paths"].keys())
    for p in (
        "/api/v1/gm/write/leads/import",
        "/api/v1/gm/write/leads/{lead_id}/qualify",
        "/api/v1/gm/write/leads/{lead_id}/route-to-proposal",
        "/api/v1/gm/write/outreach/launch",
        "/api/v1/gm/write/outreach/pause",
        "/api/v1/gm/write/replies/drafts/{draft_id}/rewrite",
        "/api/v1/gm/write/replies/drafts/{draft_id}/send-now",
    ):
        assert p in paths, f"missing Batch 10 endpoint {p}"


@pytest.mark.asyncio
async def test_batch10_endpoints_require_auth(api_client):
    checks = [
        ("POST", "/api/v1/gm/write/leads/import", {"avenue_slug": "x", "rows": [{"company_name": "x"}]}),
        (
            "POST",
            "/api/v1/gm/write/leads/00000000-0000-0000-0000-000000000000/qualify",
            {"intent": "offer_request", "tier": "warm"},
        ),
        (
            "POST",
            "/api/v1/gm/write/leads/00000000-0000-0000-0000-000000000000/route-to-proposal",
            {"line_items": [{"description": "x", "unit_amount_cents": 100000}]},
        ),
        ("POST", "/api/v1/gm/write/outreach/launch", {"avenue_slug": "x"}),
        ("POST", "/api/v1/gm/write/outreach/pause", {"avenue_slug": "x"}),
        ("POST", "/api/v1/gm/write/replies/drafts/00000000-0000-0000-0000-000000000000/rewrite", {"subject": "x"}),
        ("POST", "/api/v1/gm/write/replies/drafts/00000000-0000-0000-0000-000000000000/send-now", {}),
    ]
    for method, path, body in checks:
        r = await api_client.request(method, path, json=body)
        assert r.status_code == 401, f"{path} must 401 without JWT (got {r.status_code})"
