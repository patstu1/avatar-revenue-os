"""Email Pipeline Models — inbox connections, threads, messages, classifications.

Provides persistent, threaded email storage with contact/opportunity linkage,
intent classification, and reply draft management.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


# ── Sales Stage Enum (string-based, matches existing pattern) ──────────────


SALES_STAGES = [
    "new_lead",
    "contacted",
    "replied",
    "warm",
    "proof_sent",
    "pricing_sent",
    "payment_sent",
    "won",
    "lost",
    "dormant",
]

CLIENT_STAGES = [
    "paid",
    "onboarding_sent",
    "intake_pending",
    "intake_complete",
    "in_production",
    "qa_review",
    "delivered",
    "revision_pending",
    "completed",
    "upsell_due",
    "retainer_active",
]

EMAIL_INTENTS = [
    "warm_interest",
    "proof_request",
    "pricing_request",
    "objection",
    "negotiation",
    "not_now",
    "unsubscribe",
    "support",
    "intake_reply",
    "revision_request",
    "meeting_request",
    "payment_question",
    "referral",
    "escalation",
    "unknown",
]


# ── 1. InboxConnection ────────────────────────────────────────────────────


class InboxConnection(Base):
    """A configured email inbox (IMAP/API) linked to the organization."""
    __tablename__ = "inbox_connections"

    __table_args__ = (
        UniqueConstraint("org_id", "email_address", name="uq_inbox_org_email"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    email_address: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), default="")
    provider: Mapped[str] = mapped_column(String(50), default="imap", index=True)  # imap, graph_api, gmail_api
    host: Mapped[str] = mapped_column(String(255), default="")
    port: Mapped[int] = mapped_column(Integer, default=993)
    auth_method: Mapped[str] = mapped_column(String(30), default="password")  # password, oauth2, xoauth2
    # App-level client creds stored encrypted in integration_providers table — just reference here
    credential_provider_key: Mapped[str] = mapped_column(String(100), default="imap")

    # Per-mailbox OAuth tokens (for auth_method=oauth2/xoauth2) — encrypted
    oauth_access_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    oauth_refresh_token_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    oauth_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sync state
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)  # active, paused, error, disconnected
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_uid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # IMAP UID for incremental sync
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    messages_synced_total: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── 2. EmailThread ─────────────────────────────────────────────────────────


class EmailThread(Base):
    """A conversation thread grouping related email messages."""
    __tablename__ = "email_threads"

    __table_args__ = (
        UniqueConstraint("inbox_connection_id", "provider_thread_id", name="uq_thread_inbox_provider"),
    )

    inbox_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inbox_connections.id"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Provider identity
    provider_thread_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)  # e.g. Message-ID or References chain hash
    subject: Mapped[str] = mapped_column(String(1000), default="")

    # Contact/company linkage
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crm_contacts.id"), nullable=True, index=True
    )
    lead_opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_opportunities.id"), nullable=True, index=True
    )

    # Thread state
    direction: Mapped[str] = mapped_column(String(20), default="inbound", index=True)  # inbound, outbound, mixed
    sales_stage: Mapped[str] = mapped_column(String(30), default="new_lead", index=True)
    latest_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    reply_status: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending, drafted, sent, escalated, closed
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # Participant info
    from_email: Mapped[str] = mapped_column(String(255), default="", index=True)
    from_name: Mapped[str] = mapped_column(String(255), default="")
    to_emails: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)  # list of recipient emails

    # Timestamps
    first_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_inbound_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── 3. EmailMessage ────────────────────────────────────────────────────────


class EmailMessage(Base):
    """An individual email message within a thread."""
    __tablename__ = "email_messages"

    __table_args__ = (
        UniqueConstraint("provider_message_id", name="uq_email_message_provider_id"),
    )

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id"), nullable=False, index=True
    )
    inbox_connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("inbox_connections.id"), nullable=False, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Provider identity — dedup key
    provider_message_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    in_reply_to: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    references: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Direction + participants
    direction: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # inbound, outbound
    from_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    from_name: Mapped[str] = mapped_column(String(255), default="")
    to_emails: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    cc_emails: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)

    # Content
    subject: Mapped[str] = mapped_column(String(1000), default="")
    body_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snippet: Mapped[str] = mapped_column(String(500), default="")  # first ~200 chars for preview

    # Metadata
    message_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_headers_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── 4. EmailClassification ────────────────────────────────────────────────


class EmailClassification(Base):
    """Intent classification result for an inbound email message."""
    __tablename__ = "email_classifications"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=False, index=True
    )
    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id"), nullable=False, index=True
    )

    # Classification result
    intent: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # from EMAIL_INTENTS
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    secondary_intent: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    secondary_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Source
    classifier_version: Mapped[str] = mapped_column(String(50), default="keyword_v1")
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. claude-sonnet-4-20250514

    # Action taken
    reply_mode: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # auto_send, draft, escalate
    action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )  # OperatorAction created, if any

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── 5. EmailReplyDraft ─────────────────────────────────────────────────────


class EmailReplyDraft(Base):
    """A draft reply generated by the AI reply engine, pending approval or auto-send."""
    __tablename__ = "email_reply_drafts"

    thread_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id"), nullable=False, index=True
    )
    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=False, index=True
    )
    classification_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_classifications.id"), nullable=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Draft content
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(1000), default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Reply mode + approval
    reply_mode: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # auto_send, draft, escalate
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)  # pending, approved, sent, rejected, expired
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Generation metadata
    prompt_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Context used for generation
    thread_context_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    package_offered: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proof_links_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Structured audit trail of the 10-step reply_policy decision. Contains
    # the matched rule, confidence check, allowlist check, template check,
    # and cooldown check. Populated by reply_policy.decide_reply_mode.
    decision_trace: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ── 6. SalesStageTransition ───────────────────────────────────────────────


class SalesStageTransition(Base):
    """Audit log of sales stage changes on threads and leads."""
    __tablename__ = "sales_stage_transitions"

    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id"), nullable=True, index=True
    )
    lead_opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lead_opportunities.id"), nullable=True, index=True
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    from_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    to_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # email_inbound, email_outbound, manual, payment, website
    trigger_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # message_id, event_id, etc.
    rationale: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
