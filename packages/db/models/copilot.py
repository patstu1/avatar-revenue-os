"""Operator Copilot — chat sessions, messages, citations, action/issue summaries."""

import uuid
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from packages.db.base import Base


class CopilotChatSession(Base):
    __tablename__ = "copilot_chat_sessions"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), default="Operator session")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_message_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CopilotChatMessage(Base):
    __tablename__ = "copilot_chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("copilot_chat_sessions.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    grounding_sources: Mapped[Optional[dict]] = mapped_column(JSONB, default=list)
    truth_boundaries: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    quick_prompt_key: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    generation_mode: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    generation_model: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    context_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CopilotResponseCitation(Base):
    __tablename__ = "copilot_response_citations"

    message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("copilot_chat_messages.id"), nullable=False, index=True
    )
    source_table: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    truth_level: Mapped[str] = mapped_column(String(30), default="live", index=True)
    snippet: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CopilotActionSummary(Base):
    __tablename__ = "copilot_action_summaries"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(30), default="medium", index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_module: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CopilotIssueSummary(Base):
    __tablename__ = "copilot_issue_summaries"

    brand_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=False, index=True)
    issue_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(30), default="high", index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_module: Mapped[str] = mapped_column(String(120), nullable=False)
    source_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    truth_level: Mapped[str] = mapped_column(String(30), default="live", index=True)
    operator_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
