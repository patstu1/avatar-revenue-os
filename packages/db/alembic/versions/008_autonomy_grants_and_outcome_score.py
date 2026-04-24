"""Add brand_autonomy_grants table and outcome_score/was_auto_approved columns to operator_actions.

Revision ID: 008_autonomy_grants
Revises: 007_publish_policy
Create Date: 2026-04-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "008_autonomy_grants"
down_revision = "007_publish_policy"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = :t)"),
        {"t": name},
    )
    return result.scalar()


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = :t AND column_name = :c)"),
        {"t": table, "c": column},
    )
    return result.scalar()


def upgrade() -> None:
    # --- operator_actions: add outcome_score and was_auto_approved ---
    if not _column_exists("operator_actions", "outcome_score"):
        op.add_column(
            "operator_actions",
            sa.Column(
                "outcome_score",
                sa.Float(),
                nullable=True,
                comment="Post-execution outcome: >0 = positive impact, <0 = negative, NULL = not yet measured",
            ),
        )

    if not _column_exists("operator_actions", "was_auto_approved"):
        op.add_column(
            "operator_actions",
            sa.Column(
                "was_auto_approved",
                sa.Boolean(),
                server_default=sa.text("false"),
                nullable=False,
                comment="True if auto-promoted from assisted to autonomous via brand_autonomy_grants",
            ),
        )

    # --- brand_autonomy_grants table ---
    if not _table_exists("brand_autonomy_grants"):
        op.create_table(
            "brand_autonomy_grants",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=False, index=True),
            sa.Column("action_type", sa.String(100), nullable=False),
            sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("granted_by", sa.String(50), nullable=False, server_default=sa.text("'auto'")),
            sa.Column("success_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("success_rate", sa.Float(), server_default=sa.text("0.0"), nullable=False),
            sa.Column("daily_cap", sa.Integer(), server_default=sa.text("5"), nullable=False),
            sa.Column("today_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
            sa.Column("last_reset_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
            sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("revoke_reason", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
            sa.UniqueConstraint("brand_id", "action_type", name="uq_brand_autonomy_grant_brand_action"),
        )
        op.create_index(
            "ix_brand_autonomy_grants_brand_active",
            "brand_autonomy_grants",
            ["brand_id"],
            postgresql_where=sa.text("revoked_at IS NULL"),
        )


def downgrade() -> None:
    op.drop_table("brand_autonomy_grants")
    op.drop_column("operator_actions", "was_auto_approved")
    op.drop_column("operator_actions", "outcome_score")
