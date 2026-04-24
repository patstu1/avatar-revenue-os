"""Causal Attribution tables.

Revision ID: ca_001
Revises: opm_001
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "ca_001"
down_revision: Union[str, None] = "opm_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("ca_attribution_reports", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("target_metric", sa.String(60), nullable=False), sa.Column("direction", sa.String(10), nullable=False), sa.Column("magnitude", sa.Float(), server_default="0"), sa.Column("top_driver", sa.String(255)), sa.Column("total_hypotheses", sa.Integer(), server_default="0"), sa.Column("summary", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ca_signals", *_b(), sa.Column("brand_id", sa.UUID(), nullable=False), sa.Column("report_id", sa.UUID(), nullable=False), sa.Column("signal_type", sa.String(40), nullable=False), sa.Column("scope", sa.String(60), nullable=False), sa.Column("before_value", sa.Float(), server_default="0"), sa.Column("after_value", sa.Float(), server_default="0"), sa.Column("change_pct", sa.Float(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.ForeignKeyConstraint(["report_id"], ["ca_attribution_reports.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ca_hypotheses", *_b(), sa.Column("report_id", sa.UUID(), nullable=False), sa.Column("driver_type", sa.String(60), nullable=False), sa.Column("driver_name", sa.String(255), nullable=False), sa.Column("estimated_lift_pct", sa.Float(), server_default="0"), sa.Column("confidence", sa.Float(), server_default="0"), sa.Column("competing_explanations", JSONB(), server_default="[]"), sa.Column("evidence_json", JSONB(), server_default="{}"), sa.Column("recommended_action", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["report_id"], ["ca_attribution_reports.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ca_confidence_reports", *_b(), sa.Column("report_id", sa.UUID(), nullable=False), sa.Column("hypothesis_count", sa.Integer(), server_default="0"), sa.Column("high_confidence_count", sa.Integer(), server_default="0"), sa.Column("noise_flagged_count", sa.Integer(), server_default="0"), sa.Column("recommendation", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["report_id"], ["ca_attribution_reports.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("ca_credit_allocations", *_b(), sa.Column("report_id", sa.UUID(), nullable=False), sa.Column("driver_name", sa.String(255), nullable=False), sa.Column("credit_pct", sa.Float(), server_default="0"), sa.Column("confidence", sa.Float(), server_default="0"), sa.Column("promote_cautiously", sa.Boolean(), server_default=sa.text("false")), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["report_id"], ["ca_attribution_reports.id"]), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("ca_credit_allocations", "ca_confidence_reports", "ca_hypotheses", "ca_signals", "ca_attribution_reports"):
        op.drop_table(t)
