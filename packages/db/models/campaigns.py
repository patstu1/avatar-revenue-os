"""Campaign Constructor — complete campaign objects for monetization execution."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class Campaign(Base):
    __tablename__ = "cp_campaigns"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    campaign_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    campaign_name: Mapped[str] = mapped_column(String(255), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    target_platforms: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    target_accounts: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    target_audience: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    hook_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    landing_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lp_pages.id"), nullable=True
    )
    cta_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True)
    monetization_path: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    followup_path: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    budget_tier: Mapped[str] = mapped_column(String(20), default="bulk")
    expected_upside: Mapped[float] = mapped_column(Float, default=0.0)
    expected_cost: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    launch_status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    truth_label: Mapped[str] = mapped_column(String(40), default="recommendation_only")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CampaignVariant(Base):
    __tablename__ = "cp_variants"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cp_campaigns.id"), nullable=False, index=True
    )
    variant_label: Mapped[str] = mapped_column(String(120), nullable=False)
    hook_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    cta_family: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    landing_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lp_pages.id"), nullable=True
    )
    is_control: Mapped[bool] = mapped_column(Boolean, default=False)
    performance_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CampaignAsset(Base):
    __tablename__ = "cp_assets"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cp_campaigns.id"), nullable=False, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True
    )
    asset_role: Mapped[str] = mapped_column(String(60), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CampaignDestination(Base):
    __tablename__ = "cp_destinations"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cp_campaigns.id"), nullable=False, index=True
    )
    landing_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("lp_pages.id"), nullable=True
    )
    destination_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    destination_type: Mapped[str] = mapped_column(String(40), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CampaignBlocker(Base):
    __tablename__ = "cp_blockers"

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cp_campaigns.id"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    blocker_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="high")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
