"""Newsletter integration models — Beehiiv connections and campaign tracking."""
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class NewsletterConnection(Base):
    __tablename__ = "newsletter_connections"

    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False, default="beehiiv")
    publication_id: Mapped[str] = mapped_column(String(255), nullable=False)
    publication_name: Mapped[Optional[str]] = mapped_column(String(255))
    api_key_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    subscriber_count: Mapped[int] = mapped_column(Integer, default=0)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)


class NewsletterCampaign(Base):
    __tablename__ = "newsletter_campaigns"

    connection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("newsletter_connections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("brands.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_campaign_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="draft")
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    open_rate: Mapped[float] = mapped_column(Float, default=0.0)
    click_rate: Mapped[float] = mapped_column(Float, default=0.0)
    unsubscribe_count: Mapped[int] = mapped_column(Integer, default=0)
    revenue: Mapped[float] = mapped_column(Float, default=0.0)
    raw_stats: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
