"""Canonical Revenue Ledger — the single source of truth for all money.

Every dollar that enters the machine resolves into this ledger, regardless
of source: affiliate commissions, sponsor payments, service fees, product
sales, ad revenue, or manual entries. No fragmented money truth.

Revenue source types:
- affiliate_commission: Earnings from affiliate offers via tracking links
- sponsor_payment: Sponsor deal milestone payments
- service_fee: Service/consulting/campaign execution revenue
- consulting_fee: Direct consulting engagements
- product_sale: Digital or physical product sales
- digital_product: Courses, templates, assets
- ad_revenue: Platform ad revenue (YouTube, TikTok, etc.)
- lead_gen_fee: Lead generation/referral commissions
- membership_payment: Recurring membership/premium access
- refund: Reversal of a previous entry (negative amount)
- chargeback: Disputed charge reversal
- adjustment: Manual correction entry
"""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class RevenueLedgerEntry(Base):
    """One row per money event. Append-only. The canonical revenue record."""
    __tablename__ = "revenue_ledger"

    # ── Source Identification ──
    revenue_source_type: Mapped[str] = mapped_column(
        String(60), nullable=False, index=True,
        comment="affiliate_commission, sponsor_payment, service_fee, product_sale, ad_revenue, refund, etc."
    )
    source_object_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="FK-less pointer to originating row (af_commissions.id, sponsor_opportunities.id, etc.)"
    )
    source_object_table: Mapped[Optional[str]] = mapped_column(
        String(80), nullable=True,
        comment="Which table source_object_id references"
    )

    # ── Business Context ──
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), nullable=True, index=True
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="FK-less ref to cp_campaigns.id"
    )
    sponsor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sponsor_profiles.id"), nullable=True, index=True
    )
    affiliate_link_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="FK-less ref to af_links.id"
    )

    # ── Money ──
    gross_amount: Mapped[float] = mapped_column(
        Float, nullable=False, comment="Full revenue before fees/costs"
    )
    net_amount: Mapped[float] = mapped_column(
        Float, nullable=False, comment="After platform fees, network fees"
    )
    platform_fee: Mapped[float] = mapped_column(
        Float, default=0.0, comment="Stripe fee, network cut, etc."
    )
    cost: Mapped[float] = mapped_column(
        Float, default=0.0, comment="Production/ad cost against this event"
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")

    # ── State Machine ──
    payment_state: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, default="pending",
        comment="pending, confirmed, paid, disputed, refunded, reversed, voided"
    )
    attribution_state: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True, default="unattributed",
        comment="unattributed, auto_attributed, manually_attributed, multi_touch"
    )
    payout_state: Mapped[str] = mapped_column(
        String(30), default="not_applicable",
        comment="not_applicable, pending_payout, paid_out, held"
    )

    # ── External References ──
    webhook_ref: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, unique=True,
        comment="Idempotency key from webhook (stripe:evt_xxx, shopify:order_xxx)"
    )
    external_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
        comment="Stripe charge ID, network txn ID, etc."
    )
    payment_processor: Mapped[Optional[str]] = mapped_column(
        String(60), nullable=True,
        comment="stripe, shopify, paypal, impact, partnerstack, direct, manual"
    )

    # ── Dispute / Refund ──
    is_refund: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dispute: Mapped[bool] = mapped_column(Boolean, default=False)
    refund_of_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("revenue_ledger.id"), nullable=True,
        comment="Self-referential FK: this entry is a refund of another entry"
    )
    dispute_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # ── Timing ──
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    paid_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # ── Metadata ──
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        Index("ix_revenue_ledger_brand_source_time", "brand_id", "revenue_source_type", "occurred_at"),
        Index("ix_revenue_ledger_brand_state", "brand_id", "payment_state"),
        Index("ix_revenue_ledger_attribution", "brand_id", "attribution_state"),
    )
