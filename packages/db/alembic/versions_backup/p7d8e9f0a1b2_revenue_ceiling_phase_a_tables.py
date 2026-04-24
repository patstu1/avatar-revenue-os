"""Revenue Ceiling Phase A: offer ladders, owned audience, sequences, funnel metrics/leaks

Revision ID: p7d8e9f0a1b2
Revises: o6c7d8e9f0a1
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "p7d8e9f0a1b2"
down_revision: Union[str, None] = "o6c7d8e9f0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "offer_ladders",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_key", sa.String(255), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("offer_id", sa.UUID(), nullable=True),
        sa.Column("top_of_funnel_asset", sa.String(500), server_default="", nullable=False),
        sa.Column("first_monetization_step", sa.Text(), server_default="", nullable=False),
        sa.Column("second_monetization_step", sa.Text(), server_default="", nullable=False),
        sa.Column("upsell_path", JSONB(), nullable=True),
        sa.Column("retention_path", JSONB(), nullable=True),
        sa.Column("fallback_path", JSONB(), nullable=True),
        sa.Column("ladder_recommendation", sa.Text(), nullable=True),
        sa.Column("expected_first_conversion_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_downstream_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_ltv_contribution", sa.Float(), server_default="0", nullable=False),
        sa.Column("friction_level", sa.String(30), server_default="medium", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_offer_ladders_brand_id", "offer_ladders", ["brand_id"])
    op.create_index("ix_offer_ladders_opportunity_key", "offer_ladders", ["opportunity_key"])
    op.create_index("ix_offer_ladders_content_item_id", "offer_ladders", ["content_item_id"])

    op.create_table(
        "owned_audience_assets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("asset_type", sa.String(80), nullable=False),
        sa.Column("channel_name", sa.String(255), server_default="", nullable=False),
        sa.Column("content_family", sa.String(120), nullable=True),
        sa.Column("objective_per_family", JSONB(), nullable=True),
        sa.Column("cta_variants", JSONB(), nullable=True),
        sa.Column("estimated_channel_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("direct_vs_capture_score", sa.Float(), server_default="0.5", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owned_audience_assets_brand_id", "owned_audience_assets", ["brand_id"])
    op.create_index("ix_owned_audience_assets_asset_type", "owned_audience_assets", ["asset_type"])
    op.create_index("ix_owned_audience_assets_content_family", "owned_audience_assets", ["content_family"])

    op.create_table(
        "owned_audience_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_item_id", sa.UUID(), nullable=True),
        sa.Column("asset_id", sa.UUID(), nullable=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("value_contribution", sa.Float(), server_default="0", nullable=False),
        sa.Column("source_metadata", JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["content_item_id"], ["content_items.id"]),
        sa.ForeignKeyConstraint(["asset_id"], ["owned_audience_assets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owned_audience_events_brand_id", "owned_audience_events", ["brand_id"])
    op.create_index("ix_owned_audience_events_content_item_id", "owned_audience_events", ["content_item_id"])
    op.create_index("ix_owned_audience_events_event_type", "owned_audience_events", ["event_type"])

    op.create_table(
        "message_sequences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("sequence_type", sa.String(80), nullable=False),
        sa.Column("channel", sa.String(30), server_default="email", nullable=False),
        sa.Column("title", sa.String(500), server_default="", nullable=False),
        sa.Column("sponsor_safe", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_sequences_brand_id", "message_sequences", ["brand_id"])
    op.create_index("ix_message_sequences_sequence_type", "message_sequences", ["sequence_type"])

    op.create_table(
        "message_sequence_steps",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sequence_id", sa.UUID(), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), server_default="email", nullable=False),
        sa.Column("subject_or_title", sa.String(500), nullable=True),
        sa.Column("body_template", sa.Text(), nullable=True),
        sa.Column("delay_hours_after_previous", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["sequence_id"], ["message_sequences.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_message_sequence_steps_sequence_id", "message_sequence_steps", ["sequence_id"])

    op.create_table(
        "funnel_stage_metrics",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("content_family", sa.String(120), server_default="default", nullable=False),
        sa.Column("stage", sa.String(80), nullable=False),
        sa.Column("metric_value", sa.Float(), server_default="0", nullable=False),
        sa.Column("sample_size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("period_start", sa.String(40), nullable=True),
        sa.Column("period_end", sa.String(40), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_funnel_stage_metrics_brand_id", "funnel_stage_metrics", ["brand_id"])
    op.create_index("ix_funnel_stage_metrics_content_family", "funnel_stage_metrics", ["content_family"])
    op.create_index("ix_funnel_stage_metrics_stage", "funnel_stage_metrics", ["stage"])

    op.create_table(
        "funnel_leak_fixes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("leak_type", sa.String(120), nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium", nullable=False),
        sa.Column("affected_funnel_stage", sa.String(80), server_default="", nullable=False),
        sa.Column("affected_content_family", sa.String(120), nullable=True),
        sa.Column("suspected_cause", sa.Text(), nullable=True),
        sa.Column("recommended_fix", sa.Text(), nullable=True),
        sa.Column("expected_upside", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0", nullable=False),
        sa.Column("urgency", sa.Float(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_funnel_leak_fixes_brand_id", "funnel_leak_fixes", ["brand_id"])
    op.create_index("ix_funnel_leak_fixes_leak_type", "funnel_leak_fixes", ["leak_type"])


def downgrade() -> None:
    op.drop_index("ix_funnel_leak_fixes_leak_type", table_name="funnel_leak_fixes")
    op.drop_index("ix_funnel_leak_fixes_brand_id", table_name="funnel_leak_fixes")
    op.drop_table("funnel_leak_fixes")
    op.drop_index("ix_funnel_stage_metrics_stage", table_name="funnel_stage_metrics")
    op.drop_index("ix_funnel_stage_metrics_content_family", table_name="funnel_stage_metrics")
    op.drop_index("ix_funnel_stage_metrics_brand_id", table_name="funnel_stage_metrics")
    op.drop_table("funnel_stage_metrics")
    op.drop_index("ix_message_sequence_steps_sequence_id", table_name="message_sequence_steps")
    op.drop_table("message_sequence_steps")
    op.drop_index("ix_message_sequences_sequence_type", table_name="message_sequences")
    op.drop_index("ix_message_sequences_brand_id", table_name="message_sequences")
    op.drop_table("message_sequences")
    op.drop_index("ix_owned_audience_events_event_type", table_name="owned_audience_events")
    op.drop_index("ix_owned_audience_events_content_item_id", table_name="owned_audience_events")
    op.drop_index("ix_owned_audience_events_brand_id", table_name="owned_audience_events")
    op.drop_table("owned_audience_events")
    op.drop_index("ix_owned_audience_assets_content_family", table_name="owned_audience_assets")
    op.drop_index("ix_owned_audience_assets_asset_type", table_name="owned_audience_assets")
    op.drop_index("ix_owned_audience_assets_brand_id", table_name="owned_audience_assets")
    op.drop_table("owned_audience_assets")
    op.drop_index("ix_offer_ladders_content_item_id", table_name="offer_ladders")
    op.drop_index("ix_offer_ladders_opportunity_key", table_name="offer_ladders")
    op.drop_index("ix_offer_ladders_brand_id", table_name="offer_ladders")
    op.drop_table("offer_ladders")
