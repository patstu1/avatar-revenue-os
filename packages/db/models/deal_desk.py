"""Deal desk: strategy recommendations and lifecycle events for deals."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class DealDeskRecommendation(Base):
    __tablename__ = "deal_desk_recommendations"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    scope_type: Mapped[str] = mapped_column(String(100), nullable=False)
    scope_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    deal_strategy: Mapped[str] = mapped_column(String(100), nullable=False)
    pricing_stance: Mapped[str] = mapped_column(String(100), nullable=False)
    packaging_recommendation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    expected_margin: Mapped[float] = mapped_column(Float, default=0.0)
    expected_close_probability: Mapped[float] = mapped_column(Float, default=0.0)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    explanation_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class DealDeskEvent(Base):
    __tablename__ = "deal_desk_events"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True
    )
    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("deal_desk_recommendations.id"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    result_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
