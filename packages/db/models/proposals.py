"""Explicit conversion-system objects: proposals, line items, payment links, payments.

Introduced in Batch 3A. The schema is intentionally narrow — enough to
represent the full conversion backbone (reply → draft → proposal →
payment link → paid) without speculative fields or fulfillment-side
work that belongs in later batches.

Relationships:

    EmailReplyDraft  ──┐
                       │
    EmailThread   ─────┼──► Proposal ──► ProposalLineItem (many)
                       │        │
    OperatorAction ────┘        │
                                │
                                └──► PaymentLink ──► Payment (one per
                                                     Stripe success)

All four tables are org-scoped and Brand-scoped (brand_id nullable for
org-only payments). Stripe is the only payment provider modelled here.
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base

# ── Proposal status enum ─────────────────────────────────────────────────────

PROPOSAL_STATUSES = [
    "draft",       # created, not sent
    "sent",        # outbound email dispatched
    "viewed",      # recipient opened the proposal (future: tracking pixel)
    "accepted",    # recipient clicked the payment link but not yet paid
    "paid",        # payment.completed fired, full amount captured
    "expired",     # past expiry without payment
    "withdrawn",   # operator withdrew
]

PAYMENT_LINK_STATUSES = [
    "active",      # live and accepting payment
    "expired",     # past expiry
    "completed",   # payment succeeded at least once
    "revoked",     # operator revoked
]

PAYMENT_STATUSES = [
    "pending",     # created but not yet confirmed (unusual for Stripe)
    "succeeded",   # Stripe confirmed capture
    "failed",      # Stripe reported failure
    "refunded",    # refund webhook recorded
]


# ── 1. Proposal ──────────────────────────────────────────────────────────────


class Proposal(Base):
    """A proposal issued to a prospect in response to a reply/opportunity.

    Created either:
      - by POST /proposals with explicit line items (manual/GM path), or
      - implicitly by proposal_drain when draining a ``send_proposal``
        OperatorAction (auto path).
    """
    __tablename__ = "proposals"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )

    # Upstream context — all nullable because a proposal can be created
    # manually without a triggering inbound reply.
    thread_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_threads.id"), nullable=True, index=True
    )
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_messages.id"), nullable=True, index=True
    )
    draft_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("email_reply_drafts.id"), nullable=True, index=True
    )
    operator_action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )

    # Recipient
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    recipient_name: Mapped[str] = mapped_column(String(255), default="")
    recipient_company: Mapped[str] = mapped_column(String(255), default="")

    # Content
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    package_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    # Batch 9: which of the 22 revenue avenues this proposal belongs to.
    # Threaded downstream to Payment, Client, IntakeRequest, ClientProject,
    # ProductionJob, Delivery so every post-purchase action knows which
    # avenue it serves.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    # State machine
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False, index=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    viewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Batch 9: proposal dunning (automatic reminders for unpaid proposals).
    dunning_reminders_sent: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    dunning_last_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # "none" | "in_progress" | "max_reached" | "paid" | "cancelled"
    dunning_status: Mapped[str] = mapped_column(
        String(30), default="none", nullable=False, index=True
    )

    # Money (cents, to avoid float)
    total_amount_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)

    # Attribution
    created_by_actor_type: Mapped[str] = mapped_column(String(30), default="system")
    created_by_actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Misc
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 2. ProposalLineItem ──────────────────────────────────────────────────────


class ProposalLineItem(Base):
    """A single billable item on a proposal.

    Stores its own denormalised unit_amount + total so historical
    proposals stay stable even if the linked Offer price changes later.
    """
    __tablename__ = "proposal_line_items"

    proposal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=False, index=True
    )

    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True
    )
    package_slug: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 3. PaymentLink ───────────────────────────────────────────────────────────


class PaymentLink(Base):
    """A provider-issued payment link (e.g. Stripe Payment Link) attached
    to a proposal. We persist the provider IDs so an incoming Stripe
    webhook can match back to the originating proposal.
    """
    __tablename__ = "payment_links"

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, index=True
    )

    # Provider-side
    provider: Mapped[str] = mapped_column(String(30), default="stripe", nullable=False, index=True)
    provider_link_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_price_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_product_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    url: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="active", nullable=False, index=True
    )

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)

    # Attribution (what created this link)
    source: Mapped[str] = mapped_column(String(50), default="proposal", nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    first_clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


# ── 4. Payment ───────────────────────────────────────────────────────────────


class Payment(Base):
    """A confirmed money movement from Stripe, attached to a proposal /
    payment link when resolvable.

    Idempotent on ``(provider, provider_event_id)`` so the same Stripe
    event can never produce two Payment rows even if the webhook is
    redelivered.
    """
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_event_id", name="uq_payments_provider_event"
        ),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True
    )

    # Linkage
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"), nullable=True, index=True
    )
    payment_link_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("payment_links.id"), nullable=True, index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True
    )

    # Provider (Stripe)
    provider: Mapped[str] = mapped_column(String(30), default="stripe", nullable=False, index=True)
    provider_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_payment_intent_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_checkout_session_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_charge_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="usd", nullable=False)

    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    customer_email: Mapped[str] = mapped_column(String(255), default="", index=True)
    customer_name: Mapped[str] = mapped_column(String(255), default="")

    raw_event_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Batch 9: avenue attribution, propagated from source proposal or
    # from Stripe metadata.avenue at webhook time.
    avenue_slug: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
