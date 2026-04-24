"""Recovery / Rollback Engine tables.

Revision ID: rec_001
Revises: dt_001
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "rec_001"
down_revision: Union[str, None] = "dt_001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def _b():
    return [sa.Column("id", sa.UUID(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)]

def upgrade() -> None:
    op.create_table("rec_incidents", *_b(), sa.Column("organization_id", sa.UUID(), nullable=False), sa.Column("brand_id", sa.UUID()), sa.Column("incident_type", sa.String(60), nullable=False), sa.Column("severity", sa.String(20), server_default="high"), sa.Column("affected_scope", sa.String(60), nullable=False), sa.Column("affected_id", sa.UUID()), sa.Column("detail", sa.Text(), nullable=False), sa.Column("auto_recoverable", sa.Boolean(), server_default=sa.text("false")), sa.Column("recovery_status", sa.String(20), server_default="open"), sa.Column("playbook_id", sa.UUID()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]), sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("rec_rollbacks", *_b(), sa.Column("incident_id", sa.UUID(), nullable=False), sa.Column("rollback_type", sa.String(40), nullable=False), sa.Column("rollback_target", sa.String(120), nullable=False), sa.Column("previous_state", JSONB(), server_default="{}"), sa.Column("execution_status", sa.String(20), server_default="pending"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["incident_id"], ["rec_incidents.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("rec_reroutes", *_b(), sa.Column("incident_id", sa.UUID(), nullable=False), sa.Column("from_path", sa.String(255), nullable=False), sa.Column("to_path", sa.String(255), nullable=False), sa.Column("reason", sa.Text(), nullable=False), sa.Column("execution_status", sa.String(20), server_default="pending"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["incident_id"], ["rec_incidents.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("rec_throttles", *_b(), sa.Column("incident_id", sa.UUID(), nullable=False), sa.Column("throttle_target", sa.String(120), nullable=False), sa.Column("throttle_level", sa.String(20), server_default="50pct"), sa.Column("reason", sa.Text(), nullable=False), sa.Column("execution_status", sa.String(20), server_default="pending"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["incident_id"], ["rec_incidents.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("rec_outcomes", *_b(), sa.Column("incident_id", sa.UUID(), nullable=False), sa.Column("outcome_type", sa.String(40), nullable=False), sa.Column("success", sa.Boolean(), server_default=sa.text("false")), sa.Column("detail", sa.Text()), sa.Column("time_to_recover_minutes", sa.Integer(), server_default="0"), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.ForeignKeyConstraint(["incident_id"], ["rec_incidents.id"]), sa.PrimaryKeyConstraint("id"))

    op.create_table("rec_playbooks", *_b(), sa.Column("playbook_name", sa.String(120), nullable=False), sa.Column("incident_type", sa.String(60), nullable=False), sa.Column("steps_json", JSONB(), server_default="[]"), sa.Column("auto_execute", sa.Boolean(), server_default=sa.text("false")), sa.Column("description", sa.Text()), sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")), sa.PrimaryKeyConstraint("id"))


def downgrade() -> None:
    for t in ("rec_playbooks", "rec_outcomes", "rec_throttles", "rec_reroutes", "rec_rollbacks", "rec_incidents"):
        op.drop_table(t)
