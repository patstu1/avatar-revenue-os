"""Add execution_status column to Phase C action tables.

Revision ID: ae03phase_c_002
Revises: ae03phase_c_001
Create Date: 2026-03-31
"""
from alembic import op
import sqlalchemy as sa

revision = "ae03phase_c_002"
down_revision = "ae03phase_c_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in (
        "paid_operator_decisions",
        "sponsor_autonomous_actions",
        "retention_automation_actions",
        "self_healing_actions",
    ):
        op.add_column(
            table,
            sa.Column("execution_status", sa.String(50), server_default="proposed", nullable=False),
        )


def downgrade() -> None:
    for table in (
        "self_healing_actions",
        "retention_automation_actions",
        "sponsor_autonomous_actions",
        "paid_operator_decisions",
    ):
        op.drop_column(table, "execution_status")
