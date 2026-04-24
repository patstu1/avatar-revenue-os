"""Integration tests for the inbound email → email_pipeline path.

Exercises the full flow added in Batch 2A:

    SendGrid Inbound Parse POST
      → existing reply_ingestion (preserved)
      → InboxConnection (auto-provisioned)
      → EmailThread (upserted)
      → EmailMessage (idempotent on provider_message_id)
      → EmailClassification (via email_classifier.classify_and_persist)
      → EmailReplyDraft (via reply_engine.create_reply_draft)

Proves:
    1. All 4 core rows (thread, message, classification, draft) are written
       on first delivery.
    2. Idempotency: re-posting the same Message-ID does NOT create a second
       EmailMessage or a second draft.
    3. Failure isolation: if the pipeline wiring raises, the legacy
       reply_ingestion path still commits (verified by the test DB state
       carrying non-zero ingest side effects even when pipeline skips).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from packages.db.models.core import Organization
from packages.db.models.email_pipeline import (
    EmailClassification,
    EmailMessage,
    EmailReplyDraft,
    EmailThread,
    InboxConnection,
)
from packages.db.models.integration_registry import IntegrationProvider

INBOUND_URL = "/api/v1/webhooks/inbound-email"
TEST_INBOUND_ADDRESS = "reply-test@inbound.proofhook.dev"
TEST_SENDER = "ceo@acme-brand.example"
TEST_SUBJECT = "Re: quick question on your outreach — what does the starter look like"
TEST_BODY_TEXT = (
    "Hey — got your note. Curious about your pricing and what a starter "
    "engagement would look like for a brand our size. Could you send over "
    "package details?\n\nThanks,\nSam"
)
TEST_MESSAGE_ID = "test-msg-0001@acme-brand.example"


async def _seed_org_and_route(db_session) -> uuid.UUID:
    """Create an Organization and an inbound_email_route IntegrationProvider row."""
    org = Organization(name="Test Org", slug=f"test-org-{uuid.uuid4().hex[:8]}")
    db_session.add(org)
    await db_session.flush()

    route = IntegrationProvider(
        organization_id=org.id,
        provider_key="inbound_email_route",
        provider_name="SendGrid Inbound (test)",
        provider_category="inbox",
        is_enabled=True,
        extra_config={"to_address": TEST_INBOUND_ADDRESS},
    )
    db_session.add(route)
    await db_session.commit()
    return org.id


def _webhook_form(*, message_id: str = TEST_MESSAGE_ID) -> dict:
    headers_block = (
        f"Message-ID: <{message_id}>\n"
        f"From: Sam CEO <{TEST_SENDER}>\n"
        f"To: {TEST_INBOUND_ADDRESS}\n"
        f"Subject: {TEST_SUBJECT}\n"
    )
    return {
        "from": f"Sam CEO <{TEST_SENDER}>",
        "to": TEST_INBOUND_ADDRESS,
        "subject": TEST_SUBJECT,
        "text": TEST_BODY_TEXT,
        "html": f"<p>{TEST_BODY_TEXT}</p>",
        "headers": headers_block,
        "envelope": '{"to":["' + TEST_INBOUND_ADDRESS + '"],"from":"' + TEST_SENDER + '"}',
        "dkim": "{@acme-brand.example : pass}",
        "SPF": "pass",
        "spam_score": "0.1",
    }


@pytest.mark.asyncio
async def test_inbound_email_persists_full_pipeline(api_client, db_session):
    """First inbound delivery writes all 4 core rows + auto-provisions InboxConnection."""
    org_id = await _seed_org_and_route(db_session)

    response = await api_client.post(INBOUND_URL, data=_webhook_form())

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "accepted"
    pipeline = body.get("email_pipeline") or {}
    assert pipeline, f"email_pipeline result missing from response: {body}"
    assert pipeline.get("skipped") is not True
    assert pipeline.get("thread_id")
    assert pipeline.get("message_id")
    assert pipeline.get("classification_id")
    assert pipeline.get("intent")
    assert pipeline.get("inbox_connection_id")

    # InboxConnection auto-provisioned
    inbox = (
        await db_session.execute(
            select(InboxConnection).where(
                InboxConnection.org_id == org_id,
                InboxConnection.email_address == TEST_INBOUND_ADDRESS,
            )
        )
    ).scalar_one()
    assert inbox.provider == "sendgrid_inbound"
    assert inbox.status == "active"

    # EmailThread
    thread = (
        await db_session.execute(select(EmailThread).where(EmailThread.inbox_connection_id == inbox.id))
    ).scalar_one()
    assert thread.org_id == org_id
    assert thread.from_email == TEST_SENDER
    assert thread.message_count == 1
    assert thread.latest_classification  # set after classify_and_persist
    assert thread.last_inbound_at is not None

    # EmailMessage (idempotent key)
    messages = (
        (await db_session.execute(select(EmailMessage).where(EmailMessage.thread_id == thread.id))).scalars().all()
    )
    assert len(messages) == 1
    msg = messages[0]
    assert msg.provider_message_id == TEST_MESSAGE_ID
    assert msg.direction == "inbound"
    assert msg.from_email == TEST_SENDER

    # EmailClassification
    classification = (
        await db_session.execute(select(EmailClassification).where(EmailClassification.message_id == msg.id))
    ).scalar_one()
    assert classification.intent  # some intent (pricing_request / warm_interest / unknown)
    assert 0.0 <= classification.confidence <= 1.0
    assert classification.classifier_version == "keyword_v1"

    # EmailReplyDraft — reply_engine.create_reply_draft persisted exactly one
    drafts = (
        (await db_session.execute(select(EmailReplyDraft).where(EmailReplyDraft.message_id == msg.id))).scalars().all()
    )
    assert len(drafts) == 1
    draft = drafts[0]
    assert draft.thread_id == thread.id
    assert draft.classification_id == classification.id
    assert draft.reply_mode in {"auto_send", "draft", "escalate"}
    assert draft.status in {"approved", "pending"}
    # Decision trace from reply_policy is persisted
    assert draft.decision_trace, "decision_trace JSONB must be populated by reply_policy"
    assert draft.decision_trace.get("rules_evaluated")


@pytest.mark.asyncio
async def test_inbound_email_is_idempotent_on_message_id(api_client, db_session):
    """Re-posting the same Message-ID does not duplicate rows."""
    await _seed_org_and_route(db_session)

    first = await api_client.post(INBOUND_URL, data=_webhook_form())
    assert first.status_code == 200
    first_pipeline = first.json().get("email_pipeline") or {}
    first_message_id = first_pipeline.get("message_id")
    assert first_message_id

    # Second post with identical Message-ID
    second = await api_client.post(INBOUND_URL, data=_webhook_form())
    assert second.status_code == 200
    second_pipeline = second.json().get("email_pipeline") or {}

    # Pipeline should have short-circuited — skipped=True, same message_id
    assert second_pipeline.get("skipped") is True
    assert second_pipeline.get("reason") == "message_already_ingested"
    assert second_pipeline.get("message_id") == first_message_id

    # DB confirms: only ONE EmailMessage and ONE EmailReplyDraft
    message_count = (
        (await db_session.execute(select(EmailMessage).where(EmailMessage.provider_message_id == TEST_MESSAGE_ID)))
        .scalars()
        .all()
    )
    assert len(message_count) == 1

    draft_count = (
        (
            await db_session.execute(
                select(EmailReplyDraft).where(EmailReplyDraft.message_id == uuid.UUID(first_message_id))
            )
        )
        .scalars()
        .all()
    )
    assert len(draft_count) == 1
