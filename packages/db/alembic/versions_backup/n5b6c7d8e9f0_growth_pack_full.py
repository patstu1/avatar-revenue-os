"""Growth pack: growth_commands canonical columns + portfolio launch tables

Revision ID: n5b6c7d8e9f0
Revises: m3a4b5c6d7e8
"""

from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "n5b6c7d8e9f0"
down_revision: Union[str, None] = "m3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("growth_commands", sa.Column("command_priority", sa.Integer(), server_default="50", nullable=False))
    op.add_column("growth_commands", sa.Column("action_deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("growth_commands", sa.Column("platform", sa.String(80), nullable=True))
    op.add_column("growth_commands", sa.Column("account_type", sa.String(100), nullable=True))
    op.add_column("growth_commands", sa.Column("niche", sa.String(255), nullable=True))
    op.add_column("growth_commands", sa.Column("sub_niche", sa.String(255), nullable=True))
    op.add_column(
        "growth_commands",
        sa.Column("persona_strategy_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "growth_commands",
        sa.Column("monetization_strategy_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "growth_commands",
        sa.Column("output_requirements_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "growth_commands",
        sa.Column("success_threshold_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "growth_commands",
        sa.Column("failure_threshold_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column("growth_commands", sa.Column("expected_revenue_min", sa.Float(), server_default="0", nullable=False))
    op.add_column("growth_commands", sa.Column("expected_revenue_max", sa.Float(), server_default="0", nullable=False))
    op.add_column("growth_commands", sa.Column("risk_score", sa.Float(), server_default="0", nullable=False))
    op.add_column(
        "growth_commands", sa.Column("blockers_json", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False)
    )
    op.add_column(
        "growth_commands", sa.Column("explanation_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False)
    )
    op.add_column(
        "growth_commands",
        sa.Column("consequence_if_ignored_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
    )
    op.add_column(
        "growth_commands", sa.Column("lifecycle_status", sa.String(30), server_default="active", nullable=False)
    )
    op.create_index("ix_growth_commands_platform", "growth_commands", ["platform"])
    op.create_index("ix_growth_commands_lifecycle_status", "growth_commands", ["lifecycle_status"])

    op.create_table(
        "portfolio_launch_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("recommended_total_account_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("recommended_platform_mix_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("recommended_launch_order_json", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("recommended_role_mix_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("estimated_first_90_day_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_first_90_day_revenue_min", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_first_90_day_revenue_max", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_launch_plans_brand_id", "portfolio_launch_plans", ["brand_id"])

    op.create_table(
        "account_launch_blueprints",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("account_type", sa.String(100), nullable=False),
        sa.Column("niche", sa.String(255), nullable=False),
        sa.Column("sub_niche", sa.String(255), nullable=True),
        sa.Column("avatar_id", sa.UUID(), nullable=True),
        sa.Column("persona_strategy_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("monetization_strategy_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("content_role", sa.String(120), nullable=True),
        sa.Column("first_30_content_plan_json", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("first_offer_stack_json", JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("first_cta_strategy_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("first_owned_audience_strategy_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("success_criteria_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("failure_criteria_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("expected_cost", sa.Float(), server_default="0", nullable=False),
        sa.Column("expected_time_to_signal_days", sa.Integer(), server_default="21", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["avatar_id"], ["avatars.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_account_launch_blueprints_brand_id", "account_launch_blueprints", ["brand_id"])
    op.create_index("ix_account_launch_blueprints_platform", "account_launch_blueprints", ["platform"])

    op.create_table(
        "platform_allocation_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(80), nullable=False),
        sa.Column("recommended_account_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_account_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expansion_priority", sa.Integer(), server_default="50", nullable=False),
        sa.Column("rationale_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("expected_upside", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_platform_allocation_brand_platform", "platform_allocation_reports", ["brand_id", "platform"])

    op.create_table(
        "niche_deployment_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("niche", sa.String(255), nullable=False),
        sa.Column("sub_niche", sa.String(255), nullable=True),
        sa.Column("recommended_account_role", sa.String(120), server_default="growth", nullable=False),
        sa.Column("recommended_platform", sa.String(80), server_default="youtube", nullable=False),
        sa.Column("expected_upside", sa.Float(), server_default="0", nullable=False),
        sa.Column("saturation_risk", sa.Float(), server_default="0", nullable=False),
        sa.Column("cannibalization_risk", sa.Float(), server_default="0", nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_niche_deployment_brand_niche", "niche_deployment_reports", ["brand_id", "niche"])

    op.create_table(
        "growth_blocker_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("blocker_type", sa.String(100), nullable=False),
        sa.Column("severity", sa.String(30), nullable=False),
        sa.Column("affected_scope_type", sa.String(80), server_default="brand", nullable=False),
        sa.Column("affected_scope_id", sa.UUID(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recommended_fix", sa.Text(), nullable=False),
        sa.Column("expected_impact_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("urgency_score", sa.Float(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_growth_blocker_reports_brand", "growth_blocker_reports", ["brand_id"])

    op.create_table(
        "capital_deployment_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("total_budget", sa.Float(), server_default="0", nullable=False),
        sa.Column("platform_budget_mix_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("account_budget_mix_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("content_budget_mix_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("funnel_budget_mix_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("paid_budget_mix_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("holdback_budget", sa.Float(), server_default="0", nullable=False),
        sa.Column("explanation_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("confidence_score", sa.Float(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_capital_deployment_brand", "capital_deployment_plans", ["brand_id"])

    op.create_table(
        "cross_account_cannibalization_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("account_a_id", sa.UUID(), nullable=False),
        sa.Column("account_b_id", sa.UUID(), nullable=False),
        sa.Column("overlap_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("audience_overlap_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("topic_overlap_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("monetization_overlap_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("risk_level", sa.String(30), server_default="low", nullable=False),
        sa.Column("recommendation_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["account_a_id"], ["creator_accounts.id"]),
        sa.ForeignKeyConstraint(["account_b_id"], ["creator_accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cross_cannibal_brand", "cross_account_cannibalization_reports", ["brand_id"])

    op.create_table(
        "portfolio_output_reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("total_output_recommendation", sa.Integer(), server_default="0", nullable=False),
        sa.Column("per_platform_output_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("per_account_output_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("duplication_risk_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("saturation_risk_score", sa.Float(), server_default="0", nullable=False),
        sa.Column("throttle_recommendation_json", JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_output_brand", "portfolio_output_reports", ["brand_id"])


def downgrade() -> None:
    op.drop_table("portfolio_output_reports")
    op.drop_table("cross_account_cannibalization_reports")
    op.drop_table("capital_deployment_plans")
    op.drop_table("growth_blocker_reports")
    op.drop_table("niche_deployment_reports")
    op.drop_table("platform_allocation_reports")
    op.drop_table("account_launch_blueprints")
    op.drop_table("portfolio_launch_plans")
    op.drop_index("ix_growth_commands_lifecycle_status", table_name="growth_commands")
    op.drop_index("ix_growth_commands_platform", table_name="growth_commands")
    op.drop_column("growth_commands", "lifecycle_status")
    op.drop_column("growth_commands", "consequence_if_ignored_json")
    op.drop_column("growth_commands", "explanation_json")
    op.drop_column("growth_commands", "blockers_json")
    op.drop_column("growth_commands", "risk_score")
    op.drop_column("growth_commands", "expected_revenue_max")
    op.drop_column("growth_commands", "expected_revenue_min")
    op.drop_column("growth_commands", "failure_threshold_json")
    op.drop_column("growth_commands", "success_threshold_json")
    op.drop_column("growth_commands", "output_requirements_json")
    op.drop_column("growth_commands", "monetization_strategy_json")
    op.drop_column("growth_commands", "persona_strategy_json")
    op.drop_column("growth_commands", "sub_niche")
    op.drop_column("growth_commands", "niche")
    op.drop_column("growth_commands", "account_type")
    op.drop_column("growth_commands", "platform")
    op.drop_column("growth_commands", "action_deadline")
    op.drop_column("growth_commands", "command_priority")
