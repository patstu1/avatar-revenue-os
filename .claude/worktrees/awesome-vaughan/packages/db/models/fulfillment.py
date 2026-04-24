"""Fulfillment order model — tracks delivery after successful payment.

Created automatically when a Stripe payment webhook fires.
Bridges the gap between payment confirmation and actual service delivery.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class FulfillmentOrder(Base):
    __tablename__ = "fulfillment_orders"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True,
    )
    ledger_entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("revenue_ledger.id"), nullable=False, unique=True,
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True, index=True,
    )
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Type of fulfillment: onboarding, digital_delivery, consulting_kickoff, course_access
    fulfillment_type: Mapped[str] = mapped_column(
        String(60), nullable=False, default="onboarding", index=True,
    )

    # Status progression: pending -> email_sent -> briefs_created -> completed | failed
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)

    gross_amount: Mapped[float] = mapped_column(Float, default=0.0)

    # JSONB tracking each step completion: {"onboarding_email": "2026-04-13T...", "briefs_created": 3}
    steps_completed: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
