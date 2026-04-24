"""Revenue Leak Detector tables.

Revision ID: rld_001
Revises: ol_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "rld_001"
down_revision: Union[str, None] = "ol_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _b():
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "rld_reports",
        *_b(),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("total_leaks", sa.Integer(), server_default="0"),
        sa.Column("total_estimated_loss", sa.Float(), server_default="0"),
        sa.Column("critical_count", sa.Integer(), server_default="0"),
        sa.Column("top_leak_type", sa.String(60)),
        sa.Column("summary", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rld_events",
        *_b(),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("leak_type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), server_default="medium"),
        sa.Column("affected_scope", sa.String(60), nullable=False),
        sa.Column("affected_id", sa.UUID()),
        sa.Column("estimated_revenue_loss", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("evidence_json", JSONB(), server_default="{}"),
        sa.Column("next_best_action", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), server_default="open"),
        sa.Column("truth_label", sa.String(40), server_default="measured"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["rld_reports.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rld_clusters",
        *_b(),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("cluster_type", sa.String(60), nullable=False),
        sa.Column("event_count", sa.Integer(), server_default="0"),
        sa.Column("total_loss", sa.Float(), server_default="0"),
        sa.Column("priority_score", sa.Float(), server_default="0"),
        sa.Column("recommended_action", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rld_corrections",
        *_b(),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("leak_event_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(60), nullable=False),
        sa.Column("action_detail", sa.Text(), nullable=False),
        sa.Column("target_system", sa.String(60), nullable=False),
        sa.Column("priority", sa.String(20), server_default="medium"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["leak_event_id"], ["rld_events.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "rld_loss_estimates",
        *_b(),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("period", sa.String(30), nullable=False),
        sa.Column("total_estimated_loss", sa.Float(), server_default="0"),
        sa.Column("by_leak_type", JSONB(), server_default="{}"),
        sa.Column("by_scope", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in ("rld_loss_estimates", "rld_corrections", "rld_clusters", "rld_events", "rld_reports"):
        op.drop_table(t)
