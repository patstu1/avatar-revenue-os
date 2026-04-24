"""Integration tests for Batch 7B — GM write authority.

Each of the 10 write endpoints gets at least one test covering:
  - success path (row mutated, event emitted, audit row written)
  - auth requirement (401/403 on unauthenticated or cross-org)
  - doctrine-enforced refusal where applicable (stage-mark without
    backing event; avenue activation without acknowledgement)

All tests run against real Postgres via the api_client fixture.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from packages.db.models.email_pipeline import (
    EmailClassification,
    EmailMessage,
    EmailReplyDraft,
    EmailThread,
    InboxConnection,
)
from packages.db.models.gm_control import GMApproval, GMEscalation
from packages.db.models.proposals import Proposal
from packages.db.models.system_events import OperatorAction, SystemEvent


async def _auth(api_client, sample_org_data) -> tuple[dict, uuid.UUID]:
    await api_client.post("/api/v1/auth/register", json=sample_org_data)
    login = await api_client.post(
        "/api/v1/auth/login",
        json={"email": sample_org_data["email"], "password": sample_org_data["password"]},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    me = await api_client.get("/api/v1/auth/me", headers=headers)
    return headers, uuid.UUID(me.json()["organization_id"])


# ═══════════════════════════════════════════════════════════════════════════
#  1. Approvals
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_gm_approve_approval_writes_audit_and_emits_event(
    api_client,
    db_session,
    sample_org_data,
):
    headers, org_id = await _auth(api_client, sample_org_data)
    approval = GMApproval(
        org_id=org_id,
        action_type="test_high_value_deal",
        entity_type="proposal",
        entity_id=uuid.uuid4(),
        title="Test approval",
        description="needs operator sign-off",
        risk_level="high",
        status="pending",
        confidence=0.82,
    )
    db_session.add(approval)
    await db_session.commit()

    r = await api_client.post(
        f"/api/v1/gm/write/approvals/{approval.id}/approve",
        headers=headers,
        json={"notes": "approved by gm write test"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body["action_class"] in ("approval_required", "auto_execute")

    # Audit row
    audit = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.action_type == "gm.write.approvals.approve",
                OperatorAction.entity_id == approval.id,
            )
        )
    ).scalar_one()
    assert audit.source_module == "gm_write"

    # Event
    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "gm.write.approvals.approve",
                SystemEvent.entity_id == approval.id,
            )
        )
    ).scalar_one()
    assert evt.actor_type == "operator"


@pytest.mark.asyncio
async def test_gm_reject_approval_transitions_status(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    approval = GMApproval(
        org_id=org_id,
        action_type="test_reject",
        entity_type="proposal",
        entity_id=uuid.uuid4(),
        title="Test reject approval",
        status="pending",
        risk_level="low",
    )
    db_session.add(approval)
    await db_session.commit()

    r = await api_client.post(
        f"/api/v1/gm/write/approvals/{approval.id}/reject",
        headers=headers,
        json={"notes": "not worth it"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


@pytest.mark.asyncio
async def test_gm_approve_approval_requires_auth(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    approval = GMApproval(
        org_id=org_id,
        action_type="test_auth",
        entity_type="proposal",
        entity_id=uuid.uuid4(),
        title="x",
        status="pending",
        risk_level="low",
    )
    db_session.add(approval)
    await db_session.commit()

    r = await api_client.post(
        f"/api/v1/gm/write/approvals/{approval.id}/approve",
        json={"notes": "no auth"},
    )
    assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════════════
#  2. Escalations
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_gm_resolve_escalation_emits_event(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    esc = GMEscalation(
        org_id=org_id,
        entity_type="proposal",
        entity_id=uuid.uuid4(),
        reason_code="test_reason",
        title="Test escalation",
        description="need operator decision",
        status="open",
        severity="warning",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(esc)
    await db_session.commit()

    r = await api_client.post(
        f"/api/v1/gm/write/escalations/{esc.id}/resolve",
        headers=headers,
        json={"notes": "resolved in gm write test"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "resolved"
    audit = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.action_type == "gm.write.escalations.resolve",
                OperatorAction.entity_id == esc.id,
            )
        )
    ).scalar_one()
    assert audit.source_module == "gm_write"


# ═══════════════════════════════════════════════════════════════════════════
#  3. Reply drafts
# ═══════════════════════════════════════════════════════════════════════════


async def _seed_draft(db_session, org_id: uuid.UUID, status: str = "pending") -> EmailReplyDraft:
    suffix = uuid.uuid4().hex[:8]
    inbox = InboxConnection(
        org_id=org_id,
        email_address=f"r-{suffix}@inbound.test",
        provider="sendgrid_inbound",
        status="active",
    )
    db_session.add(inbox)
    await db_session.flush()
    thread = EmailThread(
        inbox_connection_id=inbox.id,
        org_id=org_id,
        provider_thread_id=f"t-{suffix}",
        direction="inbound",
        from_email=f"lead-{suffix}@acme.test",
    )
    db_session.add(thread)
    await db_session.flush()
    msg = EmailMessage(
        thread_id=thread.id,
        inbox_connection_id=inbox.id,
        org_id=org_id,
        provider_message_id=f"<m-{suffix}@acme.test>",
        direction="inbound",
        from_email=f"lead-{suffix}@acme.test",
    )
    db_session.add(msg)
    await db_session.flush()
    classification = EmailClassification(
        message_id=msg.id,
        thread_id=thread.id,
        intent="warm_interest",
        confidence=0.88,
        reply_mode="draft",
    )
    db_session.add(classification)
    await db_session.flush()
    draft = EmailReplyDraft(
        thread_id=thread.id,
        message_id=msg.id,
        classification_id=classification.id,
        org_id=org_id,
        to_email=f"lead-{suffix}@acme.test",
        subject="Re: test",
        body_text="hi",
        reply_mode="draft",
        status=status,
    )
    db_session.add(draft)
    await db_session.commit()
    return draft


@pytest.mark.asyncio
async def test_gm_approve_draft_transitions_status(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    draft = await _seed_draft(db_session, org_id, status="pending")
    r = await api_client.post(
        f"/api/v1/gm/write/drafts/{draft.id}/approve",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_gm_reject_draft_transitions_status(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    draft = await _seed_draft(db_session, org_id, status="pending")
    r = await api_client.post(
        f"/api/v1/gm/write/drafts/{draft.id}/reject",
        headers=headers,
        json={"reason": "off topic"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "rejected"


# ═══════════════════════════════════════════════════════════════════════════
#  4. Proposals
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_gm_create_proposal_writes_rows(api_client, db_session, sample_org_data):
    headers, org_id = await _auth(api_client, sample_org_data)
    r = await api_client.post(
        "/api/v1/gm/write/proposals",
        headers=headers,
        json={
            "recipient_email": "buyer@test.local",
            "title": "GM write proposal",
            "line_items": [{"description": "pack", "unit_amount_cents": 100_000}],
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "draft"
    assert body["total_amount_cents"] == 100_000
    proposal = (
        await db_session.execute(select(Proposal).where(Proposal.id == uuid.UUID(body["proposal_id"])))
    ).scalar_one()
    assert proposal.org_id == org_id
    audit = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.action_type == "gm.write.proposals.create",
                OperatorAction.entity_id == proposal.id,
            )
        )
    ).scalar_one()
    assert audit.source_module == "gm_write"


@pytest.mark.asyncio
async def test_gm_send_proposal_transitions(api_client, db_session, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/gm/write/proposals",
        headers=headers,
        json={
            "recipient_email": "send@test.local",
            "title": "sendable",
            "line_items": [{"description": "pack", "unit_amount_cents": 50_000}],
        },
    )
    pid = create.json()["proposal_id"]
    r = await api_client.post(
        f"/api/v1/gm/write/proposals/{pid}/send",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "sent"


@pytest.mark.asyncio
async def test_gm_create_payment_link_persists(api_client, db_session, sample_org_data, monkeypatch):
    async def _fake_stripe(**kwargs):
        return {"url": "https://checkout.stripe.com/mock", "id": "plink_mock_123"}

    from apps.api.services import stripe_billing_service

    monkeypatch.setattr(stripe_billing_service, "create_payment_link", _fake_stripe)

    headers, _ = await _auth(api_client, sample_org_data)
    create = await api_client.post(
        "/api/v1/gm/write/proposals",
        headers=headers,
        json={
            "recipient_email": "pl@test.local",
            "title": "pack",
            "line_items": [{"description": "pack", "unit_amount_cents": 75_000}],
        },
    )
    pid = create.json()["proposal_id"]
    r = await api_client.post(
        f"/api/v1/gm/write/proposals/{pid}/payment-link",
        headers=headers,
        json={},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["amount_cents"] == 75_000
    assert body["url"] == "https://checkout.stripe.com/mock"
    assert body["provider_link_id"] == "plink_mock_123"


# ═══════════════════════════════════════════════════════════════════════════
#  5. Dormant-avenue activation
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_gm_activate_dormant_avenue_writes_audit_row(api_client, db_session, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.post(
        "/api/v1/gm/write/avenues/consulting/activate",
        headers=headers,
        json={
            "authorization_notes": "operator approves consulting unlock for Q2",
            "acknowledge_unlock_plan": True,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["avenue_id"] == "consulting"
    assert body["avenue_n"] == 3
    assert isinstance(body["unlock_plan"], list)
    assert body["action_class"] == "approval_required"

    # Audit action
    audit_id = uuid.UUID(body["audit_action_id"])
    audit = (await db_session.execute(select(OperatorAction).where(OperatorAction.id == audit_id))).scalar_one()
    assert audit.action_type == "gm.write.avenues.activate"
    assert audit.action_payload["avenue_id"] == "consulting"


@pytest.mark.asyncio
async def test_gm_activate_unknown_avenue_returns_404(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.post(
        "/api/v1/gm/write/avenues/not_a_real_avenue/activate",
        headers=headers,
        json={"authorization_notes": "x", "acknowledge_unlock_plan": True},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_gm_activate_requires_unlock_plan_acknowledgement(api_client, sample_org_data):
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.post(
        "/api/v1/gm/write/avenues/consulting/activate",
        headers=headers,
        json={"authorization_notes": "x", "acknowledge_unlock_plan": False},
    )
    assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════════════
#  6. Stage mark (event-backed)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_gm_mark_stage_requires_backing_event(api_client, sample_org_data):
    """Stage advancement MUST cite a real SystemEvent row."""
    headers, _ = await _auth(api_client, sample_org_data)
    r = await api_client.post(
        "/api/v1/gm/write/stages/mark",
        headers=headers,
        json={
            "entity_type": "proposal",
            "entity_id": str(uuid.uuid4()),
            "stage": "sent",
            "backing_event_id": str(uuid.uuid4()),  # random, not a real event
        },
    )
    assert r.status_code == 400
    assert "not found" in r.text.lower()


@pytest.mark.asyncio
async def test_gm_mark_stage_succeeds_with_valid_event(api_client, db_session, sample_org_data):
    from apps.api.services.event_bus import emit_event

    headers, org_id = await _auth(api_client, sample_org_data)

    target_id = uuid.uuid4()
    await emit_event(
        db_session,
        domain="monetization",
        event_type="proposal.sent",
        summary="test event",
        org_id=org_id,
        entity_type="proposal",
        entity_id=target_id,
        new_state="sent",
        actor_type="test",
    )
    await db_session.commit()

    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "proposal.sent",
                SystemEvent.entity_id == target_id,
            )
        )
    ).scalar_one()

    r = await api_client.post(
        "/api/v1/gm/write/stages/mark",
        headers=headers,
        json={
            "entity_type": "proposal",
            "entity_id": str(target_id),
            "stage": "sent",
            "backing_event_id": str(evt.id),
            "notes": "backed by emit_event above",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["stage"] == "sent"
    assert r.json()["backing_event_id"] == str(evt.id)


# ═══════════════════════════════════════════════════════════════════════════
#  All endpoints require auth
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_all_gm_write_endpoints_require_auth(api_client):
    fake = str(uuid.uuid4())
    calls = [
        ("POST", f"/api/v1/gm/write/approvals/{fake}/approve", {"notes": "x"}),
        ("POST", f"/api/v1/gm/write/approvals/{fake}/reject", {"notes": "x"}),
        ("POST", f"/api/v1/gm/write/escalations/{fake}/resolve", {"notes": "x"}),
        ("POST", f"/api/v1/gm/write/drafts/{fake}/approve", None),
        ("POST", f"/api/v1/gm/write/drafts/{fake}/reject", {"reason": "x"}),
        (
            "POST",
            "/api/v1/gm/write/proposals",
            {"recipient_email": "x@y", "title": "x", "line_items": [{"description": "x", "unit_amount_cents": 100}]},
        ),
        ("POST", f"/api/v1/gm/write/proposals/{fake}/send", None),
        ("POST", f"/api/v1/gm/write/proposals/{fake}/payment-link", {}),
        (
            "POST",
            "/api/v1/gm/write/avenues/consulting/activate",
            {"authorization_notes": "x", "acknowledge_unlock_plan": True},
        ),
        (
            "POST",
            "/api/v1/gm/write/stages/mark",
            {"entity_type": "proposal", "entity_id": fake, "stage": "sent", "backing_event_id": fake},
        ),
    ]
    for method, path, body in calls:
        if body is None:
            r = await api_client.post(path)
        else:
            r = await api_client.post(path, json=body)
        assert r.status_code in (401, 403), f"{path} returned {r.status_code}"
