"""Operator Copilot — 5 tables for chat sessions, messages, citations, action/issue summaries.

Revision ID: copilot_001
Revises: provider_reg_001
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "copilot_001"
down_revision = "provider_reg_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "copilot_chat_sessions",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title", sa.String(255), server_default="Operator session"),
        sa.Column("status", sa.String(30), server_default="active", index=True),
        sa.Column("message_count", sa.Integer(), server_default="0"),
        sa.Column("last_message_at", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "copilot_chat_messages",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("session_id", sa.UUID(), sa.ForeignKey("copilot_chat_sessions.id"), nullable=False, index=True),
        sa.Column("role", sa.String(20), nullable=False, index=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("grounding_sources", JSONB(), server_default="[]"),
        sa.Column("truth_boundaries", JSONB(), server_default="{}"),
        sa.Column("quick_prompt_key", sa.String(120), nullable=True, index=True),
        sa.Column("confidence", sa.Float(), server_default="1.0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "copilot_response_citations",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("message_id", sa.UUID(), sa.ForeignKey("copilot_chat_messages.id"), nullable=False, index=True),
        sa.Column("source_table", sa.String(120), nullable=False, index=True),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("source_label", sa.String(255), nullable=True),
        sa.Column("truth_level", sa.String(30), server_default="live", index=True),
        sa.Column("snippet", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "copilot_action_summaries",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("action_type", sa.String(80), nullable=False, index=True),
        sa.Column("urgency", sa.String(30), server_default="medium", index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_module", sa.String(120), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), index=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "copilot_issue_summaries",
        sa.Column("id", sa.UUID(), nullable=False, primary_key=True),
        sa.Column("brand_id", sa.UUID(), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("issue_type", sa.String(80), nullable=False, index=True),
        sa.Column("severity", sa.String(30), server_default="high", index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_module", sa.String(120), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("truth_level", sa.String(30), server_default="live", index=True),
        sa.Column("operator_action", sa.Text(), nullable=True),
        sa.Column("resolved", sa.Boolean(), server_default=sa.text("false"), index=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("copilot_issue_summaries")
    op.drop_table("copilot_action_summaries")
    op.drop_table("copilot_response_citations")
    op.drop_table("copilot_chat_messages")
    op.drop_table("copilot_chat_sessions")
