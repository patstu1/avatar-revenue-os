"""Enterprise Affiliate Governance + Owned Program Ops."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class AffiliateGovernanceRule(Base):
    __tablename__ = "af_governance_rules"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    rule_key: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_value: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default="hard")
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateBannedEntity(Base):
    __tablename__ = "af_banned_entities"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateApproval(Base):
    __tablename__ = "af_approvals"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    approval_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateAuditEvent(Base):
    __tablename__ = "af_audit_events"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AffiliateRiskFlag(Base):
    __tablename__ = "af_risk_flags"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("af_offers.id"), nullable=True)
    merchant_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_merchants.id"), nullable=True
    )
    risk_type: Mapped[str] = mapped_column(String(40), nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OwnedAffiliatePartner(Base):
    __tablename__ = "af_own_partners"
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    partner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    partner_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    partner_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    partner_score: Mapped[float] = mapped_column(Float, default=0.0)
    conversion_quality: Mapped[float] = mapped_column(Float, default=0.0)
    fraud_risk: Mapped[float] = mapped_column(Float, default=0.0)
    total_conversions: Mapped[int] = mapped_column(Integer, default=0)
    total_revenue_generated: Mapped[float] = mapped_column(Float, default=0.0)
    total_payout: Mapped[float] = mapped_column(Float, default=0.0)
    asset_kit_assigned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OwnedPartnerConversion(Base):
    __tablename__ = "af_own_partner_conversions"
    partner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("af_own_partners.id"), nullable=False, index=True
    )
    conversion_value: Mapped[float] = mapped_column(Float, default=0.0)
    commission_paid: Mapped[float] = mapped_column(Float, default=0.0)
    quality_score: Mapped[float] = mapped_column(Float, default=0.5)
    fraud_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
