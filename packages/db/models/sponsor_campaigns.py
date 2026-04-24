"""Sponsor campaign models (Batch 13).

Three tables:
  - SponsorCampaign  — 1:1 with Client (parallel to
                       ClientHighTicketProfile for high_ticket);
                       carries the contract / brief / schedule state.
  - SponsorPlacement — N:1 with campaign; each row is one scheduled
                       ad placement, host-read, mention, etc.
                       Self-referential FK for make-goods
                       (SponsorPlacement.make_good_of_placement_id).
  - SponsorReport    — N:1 with campaign; periodic performance
                       summary delivered to the sponsor.

Every operationally-daily field is a first-class column. Only
free-form content (brief_json, metrics_json,
exclusivity_clauses_json, notes) is JSONB.
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


class SponsorCampaign(Base):
    __tablename__ = "sponsor_campaigns"
    __table_args__ = (
        UniqueConstraint("client_id", name="uq_sponsor_campaigns_client"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("clients.id"),
        nullable=False, unique=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"),
        nullable=False, index=True,
    )
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True,
    )
    sponsor_opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )
    avenue_slug: Mapped[str] = mapped_column(
        String(60), default="sponsor_deals", nullable=False,
    )

    # status: pre_contract / contract_signed / brief_received /
    #         campaign_live / campaign_complete / cancelled
    status: Mapped[str] = mapped_column(
        String(30), default="pre_contract", nullable=False, index=True,
    )

    contract_url: Mapped[Optional[str]] = mapped_column(
        String(2048), nullable=True,
    )
    contract_signed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    counterparty_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )

    brief_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    brief_received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    campaign_start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )
    campaign_end_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    exclusivity_clauses_json: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )


class SponsorPlacement(Base):
    __tablename__ = "sponsor_placements"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sponsor_campaigns.id"),
        nullable=False, index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False,
    )

    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # placement_type: ad_spot / host_read / video_integration /
    #                 social_mention / newsletter / other
    placement_type: Mapped[str] = mapped_column(String(40), nullable=False)

    # status: scheduled / delivered / missed / make_good / cancelled
    status: Mapped[str] = mapped_column(
        String(30), default="scheduled", nullable=False, index=True,
    )

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # Self-referential FK — when a placement is missed, a new Placement
    # row can be created with make_good_of_placement_id pointing at the
    # missed one, preserving the link for reports + dispute tracking.
    make_good_of_placement_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True,
    )

    metrics_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )


class SponsorReport(Base):
    __tablename__ = "sponsor_reports"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sponsor_campaigns.id"),
        nullable=False, index=True,
    )
    org_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False,
    )

    # report_type: weekly / monthly / final / ad_hoc
    report_type: Mapped[str] = mapped_column(
        String(30), default="monthly", nullable=False,
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )

    # status: draft / sent
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False,
    )

    compiled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    recipient_email: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True,
    )

    metrics_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False,
    )
