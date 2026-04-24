"""Client projects, project briefs, production jobs.

Revision ID: 012_fulfillment
Revises: 011_clients_intake
Create Date: 2026-04-20

Batch 3C. Additive. Each table guarded by ``IF NOT EXISTS``.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "012_fulfillment"
down_revision = "011_clients_intake"
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
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(), nullable=False,
        ),
    )


def upgrade() -> None:
    if not _table_exists("client_projects"):
        op.create_table(
            "client_projects",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("client_id", UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("intake_submission_id", UUID(as_uuid=True), sa.ForeignKey("intake_submissions.id"), nullable=True),
            sa.Column("proposal_id", UUID(as_uuid=True), sa.ForeignKey("proposals.id"), nullable=True),
            sa.Column("payment_id", UUID(as_uuid=True), sa.ForeignKey("payments.id"), nullable=True),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("description", sa.Text, nullable=False, server_default=""),
            sa.Column("package_slug", sa.String(100), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="active"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("org_id", "client_id", "intake_submission_id",
                    "proposal_id", "payment_id", "status"):
            op.create_index(f"ix_client_projects_{col}", "client_projects", [col])

    if not _table_exists("project_briefs"):
        op.create_table(
            "project_briefs",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("client_projects.id"), nullable=False),
            sa.Column("version", sa.Integer, nullable=False, server_default="1"),
            sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("summary", sa.Text, nullable=False, server_default=""),
            sa.Column("goals", sa.Text, nullable=False, server_default=""),
            sa.Column("audience", sa.Text, nullable=False, server_default=""),
            sa.Column("tone_and_voice", sa.Text, nullable=False, server_default=""),
            sa.Column("deliverables_json", JSONB, nullable=True),
            sa.Column("assets_json", JSONB, nullable=True),
            sa.Column("generator", sa.String(50), nullable=False, server_default="template_v1"),
            sa.Column("source_intake_submission_id", UUID(as_uuid=True), sa.ForeignKey("intake_submissions.id"), nullable=True),
            sa.Column("approved_by", sa.String(255), nullable=True),
            sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.UniqueConstraint("project_id", "version", name="uq_project_briefs_project_version"),
        )
        for col in ("org_id", "project_id", "status"):
            op.create_index(f"ix_project_briefs_{col}", "project_briefs", [col])

    if not _table_exists("production_jobs"):
        op.create_table(
            "production_jobs",
            *_base_cols(),
            sa.Column("org_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
            sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("client_projects.id"), nullable=False),
            sa.Column("brief_id", UUID(as_uuid=True), sa.ForeignKey("project_briefs.id"), nullable=False),
            sa.Column("job_type", sa.String(60), nullable=False),
            sa.Column("title", sa.String(500), nullable=False),
            sa.Column("status", sa.String(30), nullable=False, server_default="queued"),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column("retry_limit", sa.Integer, nullable=False, server_default="2"),
            sa.Column("last_qa_report_id", UUID(as_uuid=True), nullable=True),
            sa.Column("output_url", sa.String(2048), nullable=True),
            sa.Column("output_payload_json", JSONB, nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("linked_media_job_id", UUID(as_uuid=True), nullable=True),
            sa.Column("metadata_json", JSONB, nullable=True),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        )
        for col in ("org_id", "project_id", "brief_id", "job_type", "status"):
            op.create_index(f"ix_production_jobs_{col}", "production_jobs", [col])


def downgrade() -> None:
    for name in ("production_jobs", "project_briefs", "client_projects"):
        if _table_exists(name):
            op.drop_table(name)
