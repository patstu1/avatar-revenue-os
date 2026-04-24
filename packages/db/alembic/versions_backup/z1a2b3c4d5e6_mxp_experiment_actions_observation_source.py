"""MXP: experiment outcome actions queue + observation_source on outcomes.

Revision ID: z1a2b3c4d5e6
Revises: y5z6a7b8c9d0
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "z1a2b3c4d5e6"
down_revision: Union[str, None] = "y5z6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "experiment_outcomes",
        sa.Column(
            "observation_source",
            sa.String(40),
            server_default="synthetic_proxy",
            nullable=False,
        ),
    )
    op.create_table(
        "experiment_outcome_actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("experiment_outcome_id", sa.UUID(), nullable=False),
        sa.Column("action_kind", sa.String(50), nullable=False),
        sa.Column("execution_status", sa.String(40), server_default="pending_operator", nullable=False),
        sa.Column("structured_payload_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("operator_note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["experiment_outcome_id"], ["experiment_outcomes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_experiment_outcome_actions_brand_id", "experiment_outcome_actions", ["brand_id"])
    op.create_index("ix_experiment_outcome_actions_outcome_id", "experiment_outcome_actions", ["experiment_outcome_id"])


def downgrade() -> None:
    op.drop_index("ix_experiment_outcome_actions_outcome_id", table_name="experiment_outcome_actions")
    op.drop_index("ix_experiment_outcome_actions_brand_id", table_name="experiment_outcome_actions")
    op.drop_table("experiment_outcome_actions")
    op.drop_column("experiment_outcomes", "observation_source")
