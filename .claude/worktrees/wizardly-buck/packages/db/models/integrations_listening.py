"""Integrations + Listening OS — connectors, social listening, BI signals."""
import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class EnterpriseConnector(Base):
    __tablename__ = "il_connectors"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    connector_name: Mapped[str] = mapped_column(String(120), nullable=False)
    connector_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    endpoint_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    auth_method: Mapped[str] = mapped_column(String(30), default="api_key")
    credential_env_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    sync_direction: Mapped[str] = mapped_column(String(20), default="inbound")
    status: Mapped[str] = mapped_column(String(20), default="configured", index=True)
    last_sync_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    config_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class EnterpriseConnectorSync(Base):
    __tablename__ = "il_connector_syncs"
    connector_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("il_connectors.id"), nullable=False, index=True)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False)
    records_synced: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SocialListeningEvent(Base):
    __tablename__ = "il_social_listening"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True)
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    platform: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[float] = mapped_column(Float, default=0.0)
    relevance_score: Mapped[float] = mapped_column(Float, default=0.5)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CompetitorSignalEvent(Base):
    __tablename__ = "il_competitor_signals"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True)
    competitor_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment: Mapped[float] = mapped_column(Float, default=0.0)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class InternalBusinessSignal(Base):
    __tablename__ = "il_business_signals"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)
    signal_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_system: Mapped[str] = mapped_column(String(60), nullable=False)
    data_json: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ListeningCluster(Base):
    __tablename__ = "il_listening_clusters"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    brand_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True, index=True)
    cluster_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    cluster_label: Mapped[str] = mapped_column(String(255), nullable=False)
    signal_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0.0)
    avg_relevance: Mapped[float] = mapped_column(Float, default=0.0)
    representative_texts: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    recommended_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SignalResponseRecommendation(Base):
    __tablename__ = "il_signal_responses"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    cluster_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("il_listening_clusters.id"), nullable=False, index=True)
    response_type: Mapped[str] = mapped_column(String(60), nullable=False)
    response_action: Mapped[str] = mapped_column(Text, nullable=False)
    target_system: Mapped[str] = mapped_column(String(60), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class IntegrationBlocker(Base):
    __tablename__ = "il_blockers"
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True)
    connector_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("il_connectors.id"), nullable=True)
    blocker_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), default="high")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
