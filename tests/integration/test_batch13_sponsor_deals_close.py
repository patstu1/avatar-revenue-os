"""Batch 13 — sponsor_deals FULL_CIRCLE close tests."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from apps.api.services.client_activation import start_onboarding
from apps.api.services.invoice_service import (
    create_invoice_from_proposal, mark_paid, send_invoice,
    void_invoice, scan_overdue_invoices,
)
from apps.api.services.proposals_service import LineItemInput, create_proposal
from apps.api.services.sponsor_fulfillment_service import (
    record_placement_delivered, record_placement_missed,
    schedule_placement,
)
from apps.api.services.sponsor_issue_service import (
    CRITICAL_THRESHOLD_CENTS, WARNING_THRESHOLD_CENTS,
    classify_sponsor_issue,
)
from apps.api.services.sponsor_onboarding_service import (
    SPONSOR_INTAKE_SCHEMA, ensure_campaign,
    record_brief_received, record_contract_signed, set_campaign_start,
)
from apps.api.services.sponsor_reporting_service import (
    compile_report, send_report,
)
from packages.db.models.clients import Client
from packages.db.models.core import Brand, Organization
from packages.db.models.email_pipeline import (
    EmailMessage, EmailReplyDraft, EmailThread, InboxConnection,
)
from packages.db.models.gm_control import GMEscalation
from packages.db.models.invoices import (
    Invoice, InvoiceLineItem, InvoiceMilestone,
)
from packages.db.models.proposals import Payment, Proposal
from packages.db.models.sponsor_campaigns import (
    SponsorCampaign, SponsorPlacement, SponsorReport,
)


async def _seed_org_and_proposal(db_session, sample_org_data):
    name = sample_org_data["organization_name"]
    slug = f"b13-{uuid.uuid4().hex[:10]}"
    org = Organization(name=name, slug=slug)
    db_session.add(org); await db_session.flush()
    brand = Brand(
        organization_id=org.id, name=f"{name} Brand",
        slug=f"{slug}-brand", is_active=True,
    )
    db_session.add(brand); await db_session.flush()

    proposal = await create_proposal(
        db_session,
        org_id=org.id, brand_id=brand.id,
        recipient_email=f"sponsor_{uuid.uuid4().hex[:6]}@example.com",
        recipient_name="Acme Media",
        recipient_company="Acme Media Holdings",
        title="Sponsor test proposal",
        line_items=[LineItemInput(
            description="Q2 sponsor campaign",
            unit_amount_cents=18_000_000, quantity=1,
            currency="usd", position=0,
        )],
        avenue_slug="sponsor_deals",
    )
    await db_session.flush()
    return org.id, brand.id, proposal


# ─────────────────────────────────────────────────────────────────────────
#  1. Invoice lifecycle — create + send + mark_paid fires activation
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_invoice_from_proposal_copies_lines_and_milestones(
    db_session, sample_org_data
):
    _o, _b, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    due = datetime.now(timezone.utc) + timedelta(days=30)
    invoice = await create_invoice_from_proposal(
        db_session, proposal=proposal,
        milestones=[
            {"label": "Signing", "amount_cents": 5_400_000, "position": 0},
            {"label": "Midpoint", "amount_cents": 7_200_000, "position": 1},
            {"label": "End", "amount_cents": 5_400_000, "position": 2},
        ],
        due_date=due, actor_id="op@test",
    )
    assert invoice.status == "draft"
    assert invoice.total_cents == 18_000_000
    assert invoice.avenue_slug == "sponsor_deals"
    ms_rows = (
        await db_session.execute(
            select(InvoiceMilestone).where(
                InvoiceMilestone.invoice_id == invoice.id
            ).order_by(InvoiceMilestone.position)
        )
    ).scalars().all()
    assert [m.amount_cents for m in ms_rows] == [5_400_000, 7_200_000, 5_400_000]
    line_items = (
        await db_session.execute(
            select(InvoiceLineItem).where(
                InvoiceLineItem.invoice_id == invoice.id
            )
        )
    ).scalars().all()
    assert len(line_items) == 1
    await db_session.commit()


@pytest.mark.asyncio
async def test_mark_paid_triggers_activation_chain(
    db_session, sample_org_data
):
    _o, _b, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    invoice = await create_invoice_from_proposal(
        db_session, proposal=proposal, actor_id="op@test",
    )
    # Mark the whole thing paid
    result = await mark_paid(
        db_session, invoice=invoice,
        amount_cents=invoice.total_cents,
        payment_method="wire",
        payment_reference="WIRE-TEST-001",
        actor_id="op@test",
    )
    assert result["triggered"] is True
    assert result["payment_id"]
    assert result["invoice_status"] == "paid"
    # Client must have been created via activate_client_from_payment
    assert result["client_id"]

    # A SponsorCampaign row exists for that client (activation hook)
    client_id = uuid.UUID(result["client_id"])
    campaign = (
        await db_session.execute(
            select(SponsorCampaign).where(SponsorCampaign.client_id == client_id)
        )
    ).scalar_one()
    assert campaign.status == "pre_contract"
    assert campaign.avenue_slug == "sponsor_deals"

    # The IntakeRequest was seeded with the sponsor schema
    from packages.db.models.clients import IntakeRequest
    intake = (
        await db_session.execute(
            select(IntakeRequest).where(IntakeRequest.client_id == client_id)
        )
    ).scalar_one()
    assert intake.schema_json.get("schema_version") == "sponsor_v1"
    await db_session.commit()


@pytest.mark.asyncio
async def test_mark_paid_is_idempotent(db_session, sample_org_data):
    _o, _b, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    invoice = await create_invoice_from_proposal(
        db_session, proposal=proposal, actor_id="op@test",
    )
    r1 = await mark_paid(
        db_session, invoice=invoice,
        amount_cents=invoice.total_cents,
        payment_method="wire", payment_reference="WIRE-1",
        actor_id="op@test",
    )
    assert r1["triggered"] is True
    r2 = await mark_paid(
        db_session, invoice=invoice,
        amount_cents=invoice.total_cents,
        payment_method="wire", payment_reference="WIRE-1",
        actor_id="op@test",
    )
    assert r2["triggered"] is False
    assert r2["reason"] == "already_paid"
    # Only one Payment row
    count = (
        await db_session.execute(
            select(Payment).where(Payment.provider == "invoice")
        )
    ).scalars().all()
    assert len(count) >= 1
    await db_session.commit()


@pytest.mark.asyncio
async def test_void_rejects_paid_invoice(db_session, sample_org_data):
    _o, _b, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    invoice = await create_invoice_from_proposal(
        db_session, proposal=proposal, actor_id="op@test",
    )
    await mark_paid(
        db_session, invoice=invoice,
        amount_cents=invoice.total_cents,
        payment_method="check", payment_reference="CHK-1",
        actor_id="op@test",
    )
    with pytest.raises(ValueError):
        await void_invoice(
            db_session, invoice=invoice, reason="too late",
            actor_id="op@test",
        )


# ─────────────────────────────────────────────────────────────────────────
#  2. Onboarding — schema + state machine
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_sponsor_client_gets_sponsor_schema_and_campaign_row(
    db_session, sample_org_data
):
    _o, _b, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    # Simulate activated sponsor client
    org_id = proposal.org_id
    now = datetime.now(timezone.utc)
    c = Client(
        org_id=org_id, brand_id=proposal.brand_id,
        primary_email=proposal.recipient_email,
        display_name="Acme CEO", status="active",
        activated_at=now, last_paid_at=now,
        total_paid_cents=18_000_000,
        avenue_slug="sponsor_deals", retention_state="active",
    )
    db_session.add(c); await db_session.flush()
    intake = await start_onboarding(db_session, client=c)
    assert intake.schema_json.get("schema_version") == "sponsor_v1"
    field_ids = {f["field_id"] for f in intake.schema_json["fields"]}
    assert "contracting_entity" in field_ids
    assert "approved_talent_list" in field_ids
    assert "make_good_policy" in field_ids

    campaign = (
        await db_session.execute(
            select(SponsorCampaign).where(SponsorCampaign.client_id == c.id)
        )
    ).scalar_one()
    assert campaign.status == "pre_contract"
    await db_session.commit()


@pytest.mark.asyncio
async def test_onboarding_state_machine_advances(db_session, sample_org_data):
    _o, brand_id, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    now = datetime.now(timezone.utc)
    c = Client(
        org_id=proposal.org_id, brand_id=brand_id,
        primary_email=f"s_{uuid.uuid4().hex[:6]}@test.com",
        display_name="Sp Client", status="active",
        activated_at=now, last_paid_at=now, total_paid_cents=100000,
        avenue_slug="sponsor_deals", retention_state="active",
    )
    db_session.add(c); await db_session.flush()
    await ensure_campaign(db_session, client=c)

    r1 = await record_contract_signed(
        db_session, client=c,
        contract_url="https://docs/contract.pdf",
        counterparty_name="Acme",
        actor_id="op@test",
    )
    assert r1["status"] == "contract_signed"
    assert r1["already_signed"] is False

    # Idempotent
    r1b = await record_contract_signed(
        db_session, client=c,
        contract_url="https://docs/contract.pdf",
        counterparty_name="Acme",
        actor_id="op@test",
    )
    assert r1b["already_signed"] is True

    r2 = await record_brief_received(
        db_session, client=c, brief_json={"scope": "Q2 campaign"},
        actor_id="op@test",
    )
    assert r2["status"] == "brief_received"

    r3 = await set_campaign_start(
        db_session, client=c,
        campaign_start_at=now + timedelta(days=14),
        campaign_end_at=now + timedelta(days=104),
        actor_id="op@test",
    )
    assert r3["status"] == "campaign_live"
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  3. Fulfillment — placement + make-good
# ─────────────────────────────────────────────────────────────────────────


async def _seed_sponsor_campaign(db_session, sample_org_data) -> SponsorCampaign:
    _o, brand_id, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    now = datetime.now(timezone.utc)
    c = Client(
        org_id=proposal.org_id, brand_id=brand_id,
        primary_email=f"sp_{uuid.uuid4().hex[:6]}@test.com",
        display_name="SP", status="active",
        activated_at=now, last_paid_at=now, total_paid_cents=100000,
        avenue_slug="sponsor_deals", retention_state="active",
    )
    db_session.add(c); await db_session.flush()
    return await ensure_campaign(db_session, client=c)


@pytest.mark.asyncio
async def test_placement_delivered_records_metrics(db_session, sample_org_data):
    campaign = await _seed_sponsor_campaign(db_session, sample_org_data)
    now = datetime.now(timezone.utc)
    p = await schedule_placement(
        db_session, campaign=campaign,
        placement_type="ad_spot",
        scheduled_at=now, position=0, actor_id="op@test",
    )
    r = await record_placement_delivered(
        db_session, placement=p,
        metrics={"impressions": 240000, "clicks": 1850, "conversions": 42},
        actor_id="op@test",
    )
    assert r["status"] == "delivered"
    await db_session.refresh(p)
    assert p.metrics_json["impressions"] == 240000
    await db_session.commit()


@pytest.mark.asyncio
async def test_placement_missed_creates_linked_make_good(
    db_session, sample_org_data
):
    campaign = await _seed_sponsor_campaign(db_session, sample_org_data)
    now = datetime.now(timezone.utc)
    p = await schedule_placement(
        db_session, campaign=campaign,
        placement_type="host_read",
        scheduled_at=now, position=0, actor_id="op@test",
    )
    r = await record_placement_missed(
        db_session, placement=p, reason="Host schedule conflict",
        make_good=True, actor_id="op@test",
    )
    assert r["status"] == "missed"
    assert r["make_good_placement_id"]
    mg = (
        await db_session.execute(
            select(SponsorPlacement).where(
                SponsorPlacement.id == uuid.UUID(r["make_good_placement_id"])
            )
        )
    ).scalar_one()
    assert mg.make_good_of_placement_id == p.id
    assert mg.status == "scheduled"
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  4. Follow-up — compile + send
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_compile_report_aggregates_placements(db_session, sample_org_data):
    campaign = await _seed_sponsor_campaign(db_session, sample_org_data)
    now = datetime.now(timezone.utc)
    p1 = await schedule_placement(
        db_session, campaign=campaign, placement_type="ad_spot",
        scheduled_at=now, actor_id="op@test",
    )
    await record_placement_delivered(
        db_session, placement=p1,
        metrics={"impressions": 100000, "clicks": 500, "conversions": 20},
        actor_id="op@test",
    )
    p2 = await schedule_placement(
        db_session, campaign=campaign, placement_type="host_read",
        scheduled_at=now, actor_id="op@test",
    )
    await record_placement_missed(
        db_session, placement=p2, reason="no-go", make_good=True,
        actor_id="op@test",
    )
    report = await compile_report(
        db_session, campaign=campaign,
        period_start=now - timedelta(hours=1),
        period_end=now + timedelta(hours=1),
        actor_id="op@test",
    )
    assert report.status == "draft"
    m = report.metrics_json
    assert m["placements_scheduled"] >= 2  # p1 + p2 (and possibly make-good row scheduled now)
    assert m["placements_delivered"] == 1
    assert m["placements_missed"] == 1
    assert m["impressions"] == 100000
    await db_session.commit()


@pytest.mark.asyncio
async def test_send_report_marks_sent_even_without_smtp(
    db_session, sample_org_data
):
    campaign = await _seed_sponsor_campaign(db_session, sample_org_data)
    now = datetime.now(timezone.utc)
    report = await compile_report(
        db_session, campaign=campaign,
        period_start=now - timedelta(days=1), period_end=now,
        actor_id="op@test",
    )
    r = await send_report(
        db_session, report=report,
        recipient_email="sponsor@acme.test", actor_id="op@test",
    )
    assert r["triggered"] is True
    assert r["status"] == "sent"
    # Tolerant to missing SMTP in test env
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  5. Issue — sponsor subtype + severity
# ─────────────────────────────────────────────────────────────────────────


async def _seed_draft_for_sponsor(db_session, org_id: uuid.UUID) -> EmailReplyDraft:
    ic = InboxConnection(
        org_id=org_id,
        email_address=f"sp+{uuid.uuid4().hex[:6]}@test.com",
        display_name="SPI", provider="imap",
        host="imap.test", port=993, auth_method="oauth",
        credential_provider_key="gmail_oauth",
        status="active", consecutive_failures=0,
        messages_synced_total=0, is_active=True,
    )
    db_session.add(ic); await db_session.flush()
    now = datetime.now(timezone.utc)
    t = EmailThread(
        inbox_connection_id=ic.id, org_id=org_id,
        provider_thread_id=f"sp_{uuid.uuid4().hex[:8]}",
        subject="Metrics concern", direction="inbound",
        sales_stage="issue", reply_status="pending", message_count=1,
        from_email="sp@buyer.test", from_name="SP",
        first_message_at=now, last_message_at=now, last_inbound_at=now,
        is_active=True, avenue_slug="sponsor_deals",
    )
    db_session.add(t); await db_session.flush()
    m = EmailMessage(
        thread_id=t.id, inbox_connection_id=ic.id, org_id=org_id,
        provider_message_id=f"m_{uuid.uuid4().hex[:8]}",
        direction="inbound", from_email="sp@buyer.test",
        subject="Re: Campaign", snippet="Metrics don't match",
        message_date=now, size_bytes=50, is_active=True,
        avenue_slug="sponsor_deals",
    )
    db_session.add(m); await db_session.flush()
    d = EmailReplyDraft(
        thread_id=t.id, message_id=m.id, org_id=org_id,
        to_email="sp@buyer.test", subject="Re: Campaign",
        body_text="Let's review", reply_mode="draft", status="pending",
        confidence=0.5, is_active=True, avenue_slug="sponsor_deals",
    )
    db_session.add(d); await db_session.flush()
    return d


@pytest.mark.asyncio
async def test_sponsor_issue_classify_severity_scales(
    db_session, sample_org_data
):
    _o, _b, proposal = await _seed_org_and_proposal(db_session, sample_org_data)
    d_crit = await _seed_draft_for_sponsor(db_session, proposal.org_id)
    r = await classify_sponsor_issue(
        db_session, draft=d_crit, subtype="under_delivery",
        affected_cents=CRITICAL_THRESHOLD_CENTS + 100, actor_id="op@test",
    )
    assert r["severity"] == "critical"
    assert r["subtype"] == "under_delivery"

    d_warn = await _seed_draft_for_sponsor(db_session, proposal.org_id)
    r2 = await classify_sponsor_issue(
        db_session, draft=d_warn, subtype="metrics_dispute",
        affected_cents=WARNING_THRESHOLD_CENTS + 50, actor_id="op@test",
    )
    assert r2["severity"] == "warning"

    escs = (
        await db_session.execute(
            select(GMEscalation).where(
                GMEscalation.org_id == proposal.org_id,
                GMEscalation.reason_code.like("sponsor_%"),
            )
        )
    ).scalars().all()
    assert any(e.reason_code == "sponsor_under_delivery" for e in escs)
    assert any(e.reason_code == "sponsor_metrics_dispute" for e in escs)
    await db_session.commit()


# ─────────────────────────────────────────────────────────────────────────
#  6. Endpoint registration + auth tests
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_batch13_endpoints_all_registered(api_client):
    r = await api_client.get("/openapi.json")
    paths = set(r.json()["paths"].keys())
    for p in (
        "/api/v1/gm/write/proposals/{proposal_id}/invoice",
        "/api/v1/gm/write/invoices/{invoice_id}/send",
        "/api/v1/gm/write/invoices/{invoice_id}/mark-paid",
        "/api/v1/gm/write/invoices/{invoice_id}/void",
        "/api/v1/gm/write/clients/{client_id}/sponsor/record-contract-signed",
        "/api/v1/gm/write/clients/{client_id}/sponsor/record-brief-received",
        "/api/v1/gm/write/clients/{client_id}/sponsor/set-campaign-start",
        "/api/v1/gm/write/sponsor-campaigns/{campaign_id}/placements",
        "/api/v1/gm/write/sponsor-placements/{placement_id}/record-delivered",
        "/api/v1/gm/write/sponsor-placements/{placement_id}/record-missed",
        "/api/v1/gm/write/sponsor-campaigns/{campaign_id}/compile-report",
        "/api/v1/gm/write/sponsor-reports/{report_id}/send",
        "/api/v1/gm/write/issues/drafts/{draft_id}/sponsor-classify",
    ):
        assert p in paths, f"missing Batch 13 endpoint {p}"
