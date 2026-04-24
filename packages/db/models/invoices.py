"""Invoice models (Batch 13).

Introduced to close the Pay:P → Pay:Y gap for ``sponsor_deals``.
Sponsor relationships bill by invoice + net-terms (ACH / wire / check
/ purchase order), not by Stripe Checkout. These three models are
avenue-agnostic — any avenue that needs invoice-based billing can
reuse them. Today only sponsor_deals writes to them.

Payment semantics: ``Invoice.mark_paid`` creates a
``Payment(provider='invoice')`` row using the existing Payment
table's UniqueConstraint(provider, provider_event_id) for
idempotence, then calls ``activate_client_from_payment`` — the same
chain Stripe webhooks use. No parallel client-creation path.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class Invoice(Base):
    """Header row for an invoice-billed engagement.

    Can exist without a Client until payment is recorded (client is
    activated at ``mark_paid`` time via the Batch 9 chain, mirroring
    the Stripe-webhook path).
    """
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("org_id", "invoice_number",
                         name="uq_invoices_org_number"),
    )

    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"),
        nullable=False, index=True,
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True,
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proposals.id"),
        nullable=True, index=True,
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"),
        nullable=True, index=True,
    )

    avenue_slug: Mapped[Optional[str]] = mapped_column(
        String(60), nullable=True, index=True,
    )
    invoice_number: Mapped[str] = mapped_column(String(100), nullable=False)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), default="usd", nullable=False,
    )

    # status: draft / sent / paid / overdue / void
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False, index=True,
    )

    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    payment_method: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True,
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )

    recipient_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )
    recipient_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )
    recipient_company: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"),
        nullable=False, index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(
        String(10), default="usd", nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )


class InvoiceMilestone(Base):
    """Milestone-billing schedule for invoices that bill in stages
    (e.g. 30% at signing / 40% midpoint / 30% end).

    Each milestone pays independently. ``Invoice.mark_paid`` with a
    ``milestone_position`` parameter marks one milestone paid; without
    one, the whole invoice flips paid and all pending milestones are
    marked paid together.
    """
    __tablename__ = "invoice_milestones"

    invoice_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("invoices.id"),
        nullable=False, index=True,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # status: pending / paid / void
    status: Mapped[str] = mapped_column(
        String(30), default="pending", nullable=False, index=True,
    )
    paid_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    payment_reference: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
