"""Digital Twin / Simulation tables.

Revision ID: dt_001
Revises: rld_001
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "dt_001"
down_revision: Union[str, None] = "rld_001"
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
        "dt_simulation_runs",
        *_b(),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("run_name", sa.String(255), nullable=False),
        sa.Column("scenario_count", sa.Integer(), server_default="0"),
        sa.Column("best_scenario_id", sa.UUID()),
        sa.Column("total_expected_upside", sa.Float(), server_default="0"),
        sa.Column("summary", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dt_scenarios",
        *_b(),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("scenario_type", sa.String(60), nullable=False),
        sa.Column("option_label", sa.String(255), nullable=False),
        sa.Column("compared_to", sa.String(255)),
        sa.Column("expected_upside", sa.Float(), server_default="0"),
        sa.Column("expected_cost", sa.Float(), server_default="0"),
        sa.Column("expected_risk", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("time_to_signal_days", sa.Integer(), server_default="14"),
        sa.Column("is_recommended", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("explanation", sa.Text()),
        sa.Column("evidence_json", JSONB(), server_default="{}"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["run_id"], ["dt_simulation_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dt_assumptions",
        *_b(),
        sa.Column("scenario_id", sa.UUID(), nullable=False),
        sa.Column("assumption_key", sa.String(120), nullable=False),
        sa.Column("assumption_value", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), server_default="0.5"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["scenario_id"], ["dt_scenarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dt_outcomes",
        *_b(),
        sa.Column("scenario_id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(60), nullable=False),
        sa.Column("predicted_value", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("risk_adjusted_value", sa.Float(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["scenario_id"], ["dt_scenarios.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "dt_recommendations",
        *_b(),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("scenario_type", sa.String(60), nullable=False),
        sa.Column("expected_profit_delta", sa.Float(), server_default="0"),
        sa.Column("confidence", sa.Float(), server_default="0"),
        sa.Column("missing_evidence", JSONB(), server_default="[]"),
        sa.Column("explanation", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["run_id"], ["dt_simulation_runs.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    for t in ("dt_recommendations", "dt_outcomes", "dt_assumptions", "dt_scenarios", "dt_simulation_runs"):
        op.drop_table(t)
