"""Integration tests for the Batch 2B reply send loop.

Covers:
  1. POST approve  → status=pending → status=approved, approved_by set,
                     reply.draft.approved event emitted, OperatorAction written.
  2. POST reject   → status=pending → status=rejected, decision_trace
                     updated with rejected_by/at/reason, reply.draft.rejected
                     event emitted, OperatorAction written.
  3. Reject of sent/rejected draft returns 400.
  4. list_drafts   → intent field pulled from EmailClassification, not from
                     the (wrongly-named) reasoning JSON blob.
  5. Scheduled send worker success path → status=approved → status=sent,
                                           sent_at set, reply.draft.sent event.
  6. Scheduled send worker failure path → status stays approved,
                                          error_message populated,
                                          reply.draft.send_failed event.
  7. Operator HTML page renders 200 with the pending draft.
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
from packages.db.models.system_events import OperatorAction, SystemEvent


async def _seed_chain(
    db_session,
    *,
    org_id: uuid.UUID,
    draft_status: str = "pending",
    draft_reply_mode: str = "draft",
    intent: str = "pricing_request",
    confidence: float = 0.88,
    message_id_suffix: str = "",
) -> dict:
    """Seed a minimum InboxConnection → Thread → Message → Classification → Draft.

    Returns ids for easy reference in tests.
    """
    suffix = message_id_suffix or uuid.uuid4().hex[:8]

    inbox = InboxConnection(
        org_id=org_id,
        email_address=f"reply-test-{suffix}@inbound.proofhook.dev",
        provider="sendgrid_inbound",
        auth_method="webhook",
        credential_provider_key="sendgrid_inbound",
        status="active",
        is_active=True,
    )
    db_session.add(inbox)
    await db_session.flush()

    thread = EmailThread(
        inbox_connection_id=inbox.id,
        org_id=org_id,
        provider_thread_id=f"sha256:test-thread-{suffix}",
        subject="Re: pricing question",
        direction="inbound",
        from_email=f"lead-{suffix}@acme-brand.example",
        first_message_at=datetime.now(timezone.utc),
        last_message_at=datetime.now(timezone.utc),
        last_inbound_at=datetime.now(timezone.utc),
        message_count=1,
    )
    db_session.add(thread)
    await db_session.flush()

    msg = EmailMessage(
        thread_id=thread.id,
        inbox_connection_id=inbox.id,
        org_id=org_id,
        provider_message_id=f"<test-{suffix}@acme-brand.example>",
        direction="inbound",
        from_email=f"lead-{suffix}@acme-brand.example",
        to_emails=[inbox.email_address],
        subject="Re: pricing question",
        body_text="What's the pricing for a starter package?",
        snippet="What's the pricing for a starter package?",
        message_date=datetime.now(timezone.utc),
    )
    db_session.add(msg)
    await db_session.flush()

    classification = EmailClassification(
        message_id=msg.id,
        thread_id=thread.id,
        intent=intent,
        confidence=confidence,
        rationale=f"keyword match: {intent}",
        classifier_version="keyword_v1",
        reply_mode=draft_reply_mode,
    )
    db_session.add(classification)
    await db_session.flush()

    draft = EmailReplyDraft(
        thread_id=thread.id,
        message_id=msg.id,
        classification_id=classification.id,
        org_id=org_id,
        to_email=f"lead-{suffix}@acme-brand.example",
        subject="Re: pricing question",
        body_text="Thanks — here's the package details...",
        reply_mode=draft_reply_mode,
        status=draft_status,
        confidence=confidence,
        package_offered="growth-content-pack",
        decision_trace={"mode_source": "forced_draft", "rules_evaluated": ["forced_draft:HIT:pricing_objection"]},
    )
    db_session.add(draft)
    await db_session.commit()

    return {
        "inbox_id": inbox.id,
        "thread_id": thread.id,
        "message_id": msg.id,
        "classification_id": classification.id,
        "draft_id": draft.id,
    }


async def _org_id_from_auth(api_client, headers, db_session) -> uuid.UUID:
    """Get the user's organization_id from the /auth/me response or DB."""
    from packages.db.models.core import User

    me = await api_client.get("/api/v1/auth/me", headers=headers)
    if me.status_code == 200 and me.json().get("organization_id"):
        return uuid.UUID(me.json()["organization_id"])
    # Fall back to DB lookup by email
    headers.get("Authorization", "")
    # Can't pull email from token — use a direct query for the most recent user
    user = (
        await db_session.execute(select(User).order_by(User.created_at.desc()).limit(1))
    ).scalar_one()
    return user.organization_id


@pytest.mark.asyncio
async def test_approve_draft_emits_event_and_writes_action(
    api_client, db_session, auth_headers
):
    org_id = await _org_id_from_auth(api_client, auth_headers, db_session)
    ids = await _seed_chain(db_session, org_id=org_id, draft_status="pending")

    resp = await api_client.post(
        f"/api/v1/email/email-pipeline/drafts/{ids['draft_id']}/approve",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    assert payload["status"] == "approved"
    assert payload["approved_by"]
    assert payload["approved_at"]

    draft = (
        await db_session.execute(
            select(EmailReplyDraft).where(EmailReplyDraft.id == ids["draft_id"])
        )
    ).scalar_one()
    assert draft.status == "approved"
    assert draft.approved_by
    assert draft.approved_at is not None

    # revenue_event
    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "reply.draft.approved",
                SystemEvent.entity_id == ids["draft_id"],
            )
        )
    ).scalar_one()
    assert evt.event_domain == "monetization"
    assert evt.previous_state == "pending"
    assert evt.new_state == "approved"
    assert evt.actor_type == "operator"

    # operator_action audit trail
    action = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.action_type == "reply_draft_approved",
                OperatorAction.entity_id == ids["draft_id"],
            )
        )
    ).scalar_one()
    assert action.organization_id == org_id
    assert action.category == "monetization"


@pytest.mark.asyncio
async def test_reject_draft_updates_trace_and_emits_event(
    api_client, db_session, auth_headers
):
    org_id = await _org_id_from_auth(api_client, auth_headers, db_session)
    ids = await _seed_chain(db_session, org_id=org_id, draft_status="pending")

    resp = await api_client.post(
        f"/api/v1/email/email-pipeline/drafts/{ids['draft_id']}/reject",
        headers=auth_headers,
        json={"reason": "Off-topic — vendor spam"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "rejected"

    draft = (
        await db_session.execute(
            select(EmailReplyDraft).where(EmailReplyDraft.id == ids["draft_id"])
        )
    ).scalar_one()
    assert draft.status == "rejected"
    assert isinstance(draft.decision_trace, dict)
    assert draft.decision_trace.get("rejected_by")
    assert draft.decision_trace.get("rejected_at")
    assert draft.decision_trace.get("rejection_reason") == "Off-topic — vendor spam"

    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "reply.draft.rejected",
                SystemEvent.entity_id == ids["draft_id"],
            )
        )
    ).scalar_one()
    assert evt.new_state == "rejected"
    assert evt.event_severity == "warning"

    action = (
        await db_session.execute(
            select(OperatorAction).where(
                OperatorAction.action_type == "reply_draft_rejected",
                OperatorAction.entity_id == ids["draft_id"],
            )
        )
    ).scalar_one()
    assert action.organization_id == org_id


@pytest.mark.asyncio
async def test_reject_already_sent_draft_returns_400(
    api_client, db_session, auth_headers
):
    org_id = await _org_id_from_auth(api_client, auth_headers, db_session)
    ids = await _seed_chain(db_session, org_id=org_id, draft_status="sent")

    resp = await api_client.post(
        f"/api/v1/email/email-pipeline/drafts/{ids['draft_id']}/reject",
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_list_drafts_surfaces_intent_from_classification(
    api_client, db_session, auth_headers
):
    """The list_drafts endpoint previously returned d.reasoning (decision trace
    JSON) as 'intent'. It must now pull the real intent from the linked
    EmailClassification row."""
    org_id = await _org_id_from_auth(api_client, auth_headers, db_session)
    await _seed_chain(
        db_session,
        org_id=org_id,
        draft_status="pending",
        intent="warm_interest",
        confidence=0.91,
    )

    resp = await api_client.get(
        "/api/v1/email/email-pipeline/drafts?status=pending",
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()
    assert len(items) >= 1
    item = items[0]
    assert item["intent"] == "warm_interest"
    assert item["classification_confidence"] == 0.91
    # mode_source should be pulled from decision_trace
    assert item["mode_source"] == "forced_draft"


@pytest.mark.asyncio
async def test_scheduled_send_worker_marks_approved_drafts_sent(
    api_client, db_session, auth_headers, monkeypatch
):
    """Happy path: monkeypatch the SMTP client to return success, then call the
    worker impl directly. Draft must flip to status=sent, sent_at set,
    reply.draft.sent event emitted."""
    from apps.api.services import reply_engine
    from packages.clients.external_clients import SmtpEmailClient

    org_id = await _org_id_from_auth(api_client, auth_headers, db_session)
    ids = await _seed_chain(db_session, org_id=org_id, draft_status="approved")

    # Force the non-Graph path + make SMTP always succeed
    async def _fake_send_email(self, **kwargs):
        return {
            "success": True,
            "provider": "smtp_stub",
            "message_id": "<stub-id@test>",
        }

    monkeypatch.setattr(
        SmtpEmailClient, "_is_configured", lambda self: True, raising=False
    )
    monkeypatch.setattr(
        SmtpEmailClient, "send_email", _fake_send_email, raising=False
    )

    result = await reply_engine.send_approved_drafts(db_session, org_id)
    await db_session.commit()

    assert result["sent"] >= 1
    assert result["failed"] == 0

    draft = (
        await db_session.execute(
            select(EmailReplyDraft).where(EmailReplyDraft.id == ids["draft_id"])
        )
    ).scalar_one()
    assert draft.status == "sent"
    assert draft.sent_at is not None

    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "reply.draft.sent",
                SystemEvent.entity_id == ids["draft_id"],
            )
        )
    ).scalar_one()
    assert evt.actor_type == "worker"
    assert evt.new_state == "sent"


@pytest.mark.asyncio
async def test_scheduled_send_worker_records_send_failure(
    api_client, db_session, auth_headers, monkeypatch
):
    """Failure path: SMTP reports not configured, Graph not applicable.
    Draft stays approved, error_message populated, send_failed event emitted."""
    from apps.api.services import reply_engine
    from packages.clients.external_clients import SmtpEmailClient

    org_id = await _org_id_from_auth(api_client, auth_headers, db_session)
    ids = await _seed_chain(db_session, org_id=org_id, draft_status="approved")

    # Force SMTP to report unconfigured → send_approved_drafts writes
    # draft.error_message and marks failed.
    monkeypatch.setattr(
        SmtpEmailClient, "_is_configured", lambda self: False, raising=False
    )

    result = await reply_engine.send_approved_drafts(db_session, org_id)
    await db_session.commit()

    assert result["failed"] >= 1
    draft = (
        await db_session.execute(
            select(EmailReplyDraft).where(EmailReplyDraft.id == ids["draft_id"])
        )
    ).scalar_one()
    assert draft.status == "approved"  # still needs to retry later
    assert draft.error_message
    assert "SMTP" in draft.error_message or "not configured" in draft.error_message.lower()

    evt = (
        await db_session.execute(
            select(SystemEvent).where(
                SystemEvent.event_type == "reply.draft.send_failed",
                SystemEvent.entity_id == ids["draft_id"],
            )
        )
    ).scalar_one()
    assert evt.event_severity == "warning"


@pytest.mark.asyncio
async def test_operator_pending_drafts_page_renders(
    api_client, db_session, auth_headers
):
    org_id = await _org_id_from_auth(api_client, auth_headers, db_session)
    ids = await _seed_chain(db_session, org_id=org_id, draft_status="pending")

    resp = await api_client.get(
        "/api/v1/operator/pending-drafts", headers=auth_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith("text/html")
    body = resp.text
    # Core surface: title + a card with the draft id + approve/reject forms
    assert "Pending reply drafts" in body
    assert str(ids["draft_id"]) in body
    assert "/approve" in body
    assert "/reject" in body
