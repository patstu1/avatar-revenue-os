"""growth commander: execution spec, resources, soft supersede audit, portfolio directive

Revision ID: m3a4b5c6d7e8
Revises: k1f6g7h8i9j0
Create Date: 2026-03-29
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "m3a4b5c6d7e8"
down_revision: Union[str, None] = "k1f6g7h8i9j0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "growth_command_runs",
        sa.Column("portfolio_directive", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "growth_commands",
        sa.Column("execution_spec", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column(
        "growth_commands",
        sa.Column("required_resources", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.add_column("growth_commands", sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("growth_commands", sa.Column("superseded_by_run_id", sa.UUID(), nullable=True))
    op.add_column("growth_commands", sa.Column("created_in_run_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_growth_commands_created_in_run_id",
        "growth_commands", "growth_command_runs",
        ["created_in_run_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_growth_commands_superseded_by_run_id",
        "growth_commands", "growth_command_runs",
        ["superseded_by_run_id"], ["id"],
    )
    op.create_index("ix_growth_commands_created_in_run_id", "growth_commands", ["created_in_run_id"])
    op.create_index("ix_growth_commands_superseded_at", "growth_commands", ["superseded_at"])


def downgrade() -> None:
    op.drop_index("ix_growth_commands_superseded_at", table_name="growth_commands")
    op.drop_index("ix_growth_commands_created_in_run_id", table_name="growth_commands")
    op.drop_constraint("fk_growth_commands_superseded_by_run_id", "growth_commands", type_="foreignkey")
    op.drop_constraint("fk_growth_commands_created_in_run_id", "growth_commands", type_="foreignkey")
    op.drop_column("growth_commands", "created_in_run_id")
    op.drop_column("growth_commands", "superseded_by_run_id")
    op.drop_column("growth_commands", "superseded_at")
    op.drop_column("growth_commands", "required_resources")
    op.drop_column("growth_commands", "execution_spec")
    op.drop_column("growth_command_runs", "portfolio_directive")
