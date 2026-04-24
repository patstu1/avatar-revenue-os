"""Creator Revenue Avenues Pack — Phase A models."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class CreatorRevenueOpportunity(Base):
    """A scored revenue opportunity across UGC, services, or premium access."""
    __tablename__ = "creator_revenue_opportunities"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    avenue_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    subtype: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_segment: Mapped[str] = mapped_column(String(120), nullable=False)
    recommended_package: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    expected_margin: Mapped[float] = mapped_column(Float, default=0.0)
    priority_score: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UgcServiceAction(Base):
    """A UGC or creative services execution plan."""
    __tablename__ = "ugc_service_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_segment: Mapped[str] = mapped_column(String(120), nullable=False)
    recommended_package: Mapped[str] = mapped_column(String(200), nullable=False)
    price_band: Mapped[str] = mapped_column(String(60), default="mid")
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    expected_margin: Mapped[float] = mapped_column(Float, default=0.0)
    execution_steps_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ServiceConsultingAction(Base):
    """A services / consulting execution plan."""
    __tablename__ = "service_consulting_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    service_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    service_tier: Mapped[str] = mapped_column(String(40), default="standard", index=True)
    target_buyer: Mapped[str] = mapped_column(String(120), nullable=False)
    price_band: Mapped[str] = mapped_column(String(60), default="mid")
    expected_deal_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class PremiumAccessAction(Base):
    """A premium access / concierge execution plan."""
    __tablename__ = "premium_access_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    offer_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_segment: Mapped[str] = mapped_column(String(120), nullable=False)
    entry_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revenue_model: Mapped[str] = mapped_column(String(30), default="recurring", index=True)
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LicensingAction(Base):
    """A licensing execution plan."""
    __tablename__ = "licensing_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    asset_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    licensing_tier: Mapped[str] = mapped_column(String(40), default="standard", index=True)
    target_buyer_type: Mapped[str] = mapped_column(String(120), nullable=False)
    usage_scope: Mapped[str] = mapped_column(String(40), default="limited_use", index=True)
    price_band: Mapped[str] = mapped_column(String(60), default="mid")
    expected_deal_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SyndicationAction(Base):
    """A syndication execution plan."""
    __tablename__ = "syndication_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    syndication_format: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_partner: Mapped[str] = mapped_column(String(120), nullable=False)
    revenue_model: Mapped[str] = mapped_column(String(30), default="recurring", index=True)
    price_band: Mapped[str] = mapped_column(String(60), default="mid")
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DataProductAction(Base):
    """A data product execution plan."""
    __tablename__ = "data_product_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    product_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_segment: Mapped[str] = mapped_column(String(120), nullable=False)
    revenue_model: Mapped[str] = mapped_column(String(30), default="recurring", index=True)
    price_band: Mapped[str] = mapped_column(String(60), default="mid")
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MerchAction(Base):
    """A merch / physical product execution plan."""
    __tablename__ = "merch_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    product_class: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_segment: Mapped[str] = mapped_column(String(120), nullable=False)
    price_band: Mapped[str] = mapped_column(String(60), default="mid")
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    truth_label: Mapped[str] = mapped_column(String(30), default="recommended", index=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class LiveEventAction(Base):
    """A live event execution plan."""
    __tablename__ = "live_event_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    audience_segment: Mapped[str] = mapped_column(String(120), nullable=False)
    ticket_model: Mapped[str] = mapped_column(String(40), default="paid", index=True)
    price_band: Mapped[str] = mapped_column(String(60), default="mid")
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    truth_label: Mapped[str] = mapped_column(String(30), default="recommended", index=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class OwnedAffiliateProgramAction(Base):
    """An owned affiliate program execution plan."""
    __tablename__ = "owned_affiliate_program_actions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    program_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_partner_type: Mapped[str] = mapped_column(String(120), nullable=False)
    incentive_model: Mapped[str] = mapped_column(String(60), default="percentage", index=True)
    partner_tier: Mapped[str] = mapped_column(String(40), default="standard", index=True)
    expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    execution_plan_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    truth_label: Mapped[str] = mapped_column(String(30), default="recommended", index=True)
    status: Mapped[str] = mapped_column(String(30), default="planned", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blockers_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AvenueExecutionTruth(Base):
    """Per-avenue execution truth state for the unified Creator Revenue Hub."""
    __tablename__ = "avenue_execution_truth"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    avenue_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    truth_state: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    total_actions: Mapped[int] = mapped_column(default=0)
    active_actions: Mapped[int] = mapped_column(default=0)
    blocked_actions: Mapped[int] = mapped_column(default=0)
    total_expected_value: Mapped[float] = mapped_column(Float, default=0.0)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    blocker_count: Mapped[int] = mapped_column(default=0)
    revenue_to_date: Mapped[float] = mapped_column(Float, default=0.0)
    operator_next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    missing_integrations: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CreatorRevenueBlocker(Base):
    """Blockers preventing creator revenue avenue execution."""
    __tablename__ = "creator_revenue_blockers"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    avenue_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    blocker_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    operator_action_needed: Mapped[str] = mapped_column(Text, nullable=False)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CreatorRevenueEvent(Base):
    """Revenue events tied to creator revenue avenues."""
    __tablename__ = "creator_revenue_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("creator_revenue_opportunities.id"), nullable=True, index=True)
    avenue_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    profit: Mapped[float] = mapped_column(Float, default=0.0)
    client_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
