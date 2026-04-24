"""Creator Revenue Avenues Pack — Phase D: Hub + Execution Truth

Revision ID: cra_phase_d_001
Revises: cra_phase_c_001
Create Date: 2025-01-01 00:00:00.000000
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "cra_phase_d_001"
down_revision = "cra_phase_c_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "avenue_execution_truth",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
        sa.Column("avenue_type", sa.String(60), nullable=False, index=True),
        sa.Column("truth_state", sa.String(30), nullable=False, index=True),
        sa.Column("total_actions", sa.Integer, server_default="0"),
        sa.Column("active_actions", sa.Integer, server_default="0"),
        sa.Column("blocked_actions", sa.Integer, server_default="0"),
        sa.Column("total_expected_value", sa.Float, server_default="0"),
        sa.Column("avg_confidence", sa.Float, server_default="0"),
        sa.Column("blocker_count", sa.Integer, server_default="0"),
        sa.Column("revenue_to_date", sa.Float, server_default="0"),
        sa.Column("operator_next_action", sa.Text, nullable=True),
        sa.Column("missing_integrations", JSONB, server_default="[]"),
        sa.Column("details_json", JSONB, server_default="{}"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("avenue_execution_truth")
