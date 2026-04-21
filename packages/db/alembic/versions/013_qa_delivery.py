"""Production QA reviews + deliveries.

Revision ID: 013_qa_delivery
Revises: 012_fulfillment
Create Date: 2026-04-20

Batch 3D. Additive; each table guarded by ``IF NOT EXISTS``.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "013_qa_delivery"
down_revision = "012_fulfillment"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"
        ),
        {"t": name},
    )
    return bool(result.scalar())


def _base_cols():
    return (
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )


def upgrade() -> None:
    if not _table_exists("production_qa_reviews"):
        op.create_table(
            "production_qa_reviews",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("production_job_id", UUID(as_uuid=True), sa.ForeignKey("production_jobs.id"), nullable=False),
            sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("client_projects.id"), nullable=False),
            sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
            sa.Column("result", sa.String(20), nullable=False),
            sa.Column("composite_score", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("scores_json", JSONB, nullable=True),
            sa.Column("issues_json", JSONB, nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("reviewer_type", sa.String(30), nullable=False, server_default="auto"),
            sa.Column("reviewer_id", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("org_id", "production_job_id", "project_id", "result"):
            op.create_index(f"ix_production_qa_reviews_{col}", "production_qa_reviews", [col])

    if not _table_exists("deliveries"):
        op.create_table(
            "deliveries",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("client_projects.id"), nullable=False),
            sa.Column("production_job_id", UUID(as_uuid=True), sa.ForeignKey("production_jobs.id"), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("channel", sa.String(30), nullable=False, server_default="email"),
            sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
            sa.Column("deliverable_url", sa.String(2048), nullable=True),
            sa.Column("recipient_email", sa.String(255), nullable=False, server_default=""),
            sa.Column("subject", sa.String(1000), nullable=False, server_default=""),
            sa.Column("message", sa.Text, nullable=False, server_default=""),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("followup_scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("org_id", "client_id", "project_id", "production_job_id",
                    "channel", "status"):
            op.create_index(f"ix_deliveries_{col}", "deliveries", [col])


def downgrade() -> None:
    for name in ("deliveries", "production_qa_reviews"):
        if _table_exists(name):
            op.drop_table(name)
