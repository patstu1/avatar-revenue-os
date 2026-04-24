"""Memory, comments, knowledge graph."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class MemoryEntry(Base):
    __tablename__ = "memory_entries"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    memory_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(255))
    key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    value: Mapped[Optional[str]] = mapped_column(Text)
    structured_value: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    source_content_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    source_type: Mapped[Optional[str]] = mapped_column(String(100))
    times_reinforced: Mapped[int] = mapped_column(Integer, default=1)
    times_contradicted: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CommentIngestion(Base):
    __tablename__ = "comment_ingestion"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    content_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("content_items.id"), index=True
    )
    creator_account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("creator_accounts.id"), index=True
    )
    platform: Mapped[Optional[str]] = mapped_column(String(50))
    platform_comment_id: Mapped[Optional[str]] = mapped_column(String(255))
    author_name: Mapped[Optional[str]] = mapped_column(String(255))
    comment_text: Mapped[str] = mapped_column(Text, nullable=False)
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    intent_classification: Mapped[Optional[str]] = mapped_column(String(100))
    is_question: Mapped[bool] = mapped_column(Boolean, default=False)
    is_purchase_intent: Mapped[bool] = mapped_column(Boolean, default=False)
    is_complaint: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False)


class CommentCluster(Base):
    __tablename__ = "comment_clusters"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    cluster_label: Mapped[str] = mapped_column(String(255), nullable=False)
    cluster_type: Mapped[str] = mapped_column(String(100), nullable=False)
    representative_comments: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_sentiment: Mapped[float] = mapped_column(Float, default=0.0)
    purchase_intent_pct: Mapped[float] = mapped_column(Float, default=0.0)
    suggested_action: Mapped[Optional[str]] = mapped_column(Text)
    is_actionable: Mapped[bool] = mapped_column(Boolean, default=False)


class CommentCashSignal(Base):
    __tablename__ = "comment_cash_signals"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    comment_cluster_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comment_clusters.id"), index=True
    )
    signal_type: Mapped[str] = mapped_column(String(100), nullable=False)
    signal_strength: Mapped[float] = mapped_column(Float, default=0.0)
    estimated_revenue_potential: Mapped[float] = mapped_column(Float, default=0.0)
    suggested_offer_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("offers.id"))
    suggested_content_angle: Mapped[Optional[str]] = mapped_column(Text)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    is_actioned: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeGraphNode(Base):
    __tablename__ = "knowledge_graph_nodes"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    properties: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    embedding_vector: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    source_type: Mapped[Optional[str]] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class KnowledgeGraphEdge(Base):
    __tablename__ = "knowledge_graph_edges"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_graph_nodes.id"), nullable=False, index=True
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("knowledge_graph_nodes.id"), nullable=False, index=True
    )
    edge_type: Mapped[str] = mapped_column(String(100), nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    properties: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
