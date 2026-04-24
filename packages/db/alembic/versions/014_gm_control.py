"""GM operating truth: approvals, escalations, stage states.

Revision ID: 014_gm_control
Revises: 013_qa_delivery
Create Date: 2026-04-20

Batch 4. Additive; each table guarded by ``IF NOT EXISTS``.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "014_gm_control"
down_revision = "013_qa_delivery"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": name},
    )
    return bool(result.scalar())


def _base_cols():
    return (
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    if not _table_exists("gm_approvals"):
        op.create_table(
            "gm_approvals",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("action_type", sa.String(60), nullable=False),
            sa.Column("entity_type", sa.String(60), nullable=False),
            sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("reason", sa.Text, nullable=True),
            sa.Column("risk_level", sa.String(20), nullable=False, server_default="medium"),
            sa.Column("proposed_payload", JSONB, nullable=True),
            sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("decided_by", sa.String(255), nullable=True),
            sa.Column("decision_notes", sa.Text, nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("source_module", sa.String(80), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint(
                "org_id", "entity_type", "entity_id", "action_type", name="uq_gm_approvals_entity_action"
            ),
        )
        for col in ("org_id", "action_type", "entity_type", "entity_id", "risk_level", "status"):
            op.create_index(f"ix_gm_approvals_{col}", "gm_approvals", [col])

    if not _table_exists("gm_escalations"):
        op.create_table(
            "gm_escalations",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("entity_type", sa.String(60), nullable=False),
            sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
            sa.Column("reason_code", sa.String(80), nullable=False),
            sa.Column("stage", sa.String(60), nullable=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
            sa.Column("details_json", JSONB, nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="open"),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledged_by", sa.String(255), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("resolution_notes", sa.Text, nullable=True),
            sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("occurrence_count", sa.Integer, nullable=False, server_default="1"),
            sa.Column("source_module", sa.String(80), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint(
                "org_id", "entity_type", "entity_id", "reason_code", name="uq_gm_escalations_entity_reason"
            ),
        )
        for col in ("org_id", "entity_type", "entity_id", "reason_code", "stage", "severity", "status"):
            op.create_index(f"ix_gm_escalations_{col}", "gm_escalations", [col])

    if not _table_exists("stage_states"):
        op.create_table(
            "stage_states",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("entity_type", sa.String(60), nullable=False),
            sa.Column("entity_id", UUID(as_uuid=True), nullable=False),
            sa.Column("stage", sa.String(60), nullable=False),
            sa.Column("previous_stage", sa.String(60), nullable=True),
            sa.Column("entered_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("sla_deadline", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_watcher_tick_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_stuck", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("stuck_reason", sa.String(255), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("entity_type", "entity_id", name="uq_stage_states_entity"),
        )
        for col in ("org_id", "entity_type", "entity_id", "stage", "sla_deadline", "is_stuck"):
            op.create_index(f"ix_stage_states_{col}", "stage_states", [col])


def downgrade() -> None:
    for name in ("stage_states", "gm_escalations", "gm_approvals"):
        if _table_exists(name):
            op.drop_table(name)
