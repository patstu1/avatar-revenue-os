"""Elite Affiliate Intelligence — full affiliate revenue operating layer."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AffiliateNetworkAccount(Base):
    __tablename__ = "af_network_accounts"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    network_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    account_id_external: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    api_key_env: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateMerchant(Base):
    __tablename__ = "af_merchants"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    network_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_network_accounts.id"), nullable=True
    )
    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    merchant_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateOffer(Base):
    __tablename__ = "af_offers"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    merchant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_merchants.id"), nullable=True
    )
    offer_id_internal: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("offers.id"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(500), nullable=False)
    product_category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    offer_type: Mapped[str] = mapped_column(String(60), default="affiliate", index=True)
    destination_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    affiliate_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    commission_type: Mapped[str] = mapped_column(String(30), default="percentage")
    commission_rate: Mapped[float] = mapped_column(Float, default=0.0)
    cookie_window_days: Mapped[int] = mapped_column(Integer, default=30)
    epc: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_rate: Mapped[float] = mapped_column(Float, default=0.0)
    refund_rate: Mapped[float] = mapped_column(Float, default=0.0)
    trust_score: Mapped[float] = mapped_column(Float, default=0.5)
    content_fit_score: Mapped[float] = mapped_column(Float, default=0.5)
    platform_fit_score: Mapped[float] = mapped_column(Float, default=0.5)
    audience_fit_score: Mapped[float] = mapped_column(Float, default=0.5)
    rank_score: Mapped[float] = mapped_column(Float, default=0.0)
    blocker_state: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    truth_label: Mapped[str] = mapped_column(String(40), default="configured")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateLink(Base):
    __tablename__ = "af_links"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_offers.id"), nullable=False, index=True
    )
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), nullable=True, index=True
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    landing_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    full_url: Mapped[str] = mapped_column(String(1500), nullable=False)
    short_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    utm_params: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    disclosure_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    click_count: Mapped[int] = mapped_column(Integer, default=0)
    conversion_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateClickEvent(Base):
    __tablename__ = "af_clicks"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_links.id"), nullable=False, index=True
    )
    clicked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    referrer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)


class AffiliateConversionEvent(Base):
    __tablename__ = "af_conversions"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    link_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_links.id"), nullable=False, index=True
    )
    offer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_offers.id"), nullable=False, index=True
    )
    conversion_value: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_type: Mapped[str] = mapped_column(String(40), default="sale")
    converted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AffiliateCommissionEvent(Base):
    __tablename__ = "af_commissions"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    conversion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_conversions.id"), nullable=False, index=True
    )
    commission_amount: Mapped[float] = mapped_column(Float, default=0.0)
    commission_status: Mapped[str] = mapped_column(String(30), default="pending")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliatePayoutEvent(Base):
    __tablename__ = "af_payouts"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    network_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_network_accounts.id"), nullable=True
    )
    payout_amount: Mapped[float] = mapped_column(Float, default=0.0)
    payout_status: Mapped[str] = mapped_column(String(30), default="pending")
    period: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateBlocker(Base):
    __tablename__ = "af_blockers"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("af_offers.id"), nullable=True)
    blocker_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="high")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateDisclosure(Base):
    __tablename__ = "af_disclosures"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    disclosure_type: Mapped[str] = mapped_column(String(60), nullable=False)
    disclosure_text: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateLeak(Base):
    __tablename__ = "af_leaks"
    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("af_offers.id"), nullable=True)
    link_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("af_links.id"), nullable=True)
    leak_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    revenue_loss_estimate: Mapped[float] = mapped_column(Float, default=0.0)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
