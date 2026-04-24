"""Add monetization machine and SaaS metrics models.

Revision ID: 004_monetization
Revises: b6587e9c03b5
Create Date: 2026-04-03
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from packages.db.alembic.migration_safety import (
    safe_create_index,
    safe_create_table,
    safe_drop_table,
)

revision = "004_monetization"
down_revision = "b6587e9c03b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. credit_ledgers ─────────────────────────────────────────────
    safe_create_table(
        "credit_ledgers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("total_credits", sa.Integer, server_default="0", nullable=False),
        sa.Column("used_credits", sa.Integer, server_default="0", nullable=False),
        sa.Column("remaining_credits", sa.Integer, server_default="0", nullable=False),
        sa.Column("bonus_credits", sa.Integer, server_default="0", nullable=False),
        sa.Column("replenishment_rate", sa.Integer, server_default="0", nullable=False),
        sa.Column("overage_enabled", sa.Boolean, server_default="false", nullable=False),
        sa.Column("overage_rate", sa.Float, server_default="0.10", nullable=False),
        sa.Column("next_replenishment_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_credit_ledgers_organization_id", "credit_ledgers", ["organization_id"])

    # ── 2. credit_transactions ────────────────────────────────────────
    safe_create_table(
        "credit_transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("transaction_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Integer, nullable=False),
        sa.Column("balance_after", sa.Integer, server_default="0", nullable=False),
        sa.Column("meter_type", sa.String(60), nullable=True),
        sa.Column("reference_id", sa.String(255), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("transacted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_credit_transactions_organization_id", "credit_transactions", ["organization_id"])
    safe_create_index("ix_credit_transactions_user_id", "credit_transactions", ["user_id"])
    safe_create_index("ix_credit_transactions_transaction_type", "credit_transactions", ["transaction_type"])
    safe_create_index("ix_credit_transactions_meter_type", "credit_transactions", ["meter_type"])
    safe_create_index("ix_credit_transactions_transacted_at", "credit_transactions", ["transacted_at"])

    # ── 3. usage_meter_snapshots ──────────────────────────────────────
    safe_create_table(
        "usage_meter_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("meter_type", sa.String(60), nullable=False),
        sa.Column("period_start", sa.String(10), nullable=False),
        sa.Column("period_end", sa.String(10), nullable=False),
        sa.Column("units_used", sa.Integer, server_default="0", nullable=False),
        sa.Column("units_limit", sa.Integer, server_default="0", nullable=False),
        sa.Column("utilization_pct", sa.Float, server_default="0.0", nullable=False),
        sa.Column("overage_units", sa.Integer, server_default="0", nullable=False),
        sa.Column("overage_cost", sa.Float, server_default="0.0", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_usage_meter_snapshots_organization_id", "usage_meter_snapshots", ["organization_id"])
    safe_create_index("ix_usage_meter_snapshots_meter_type", "usage_meter_snapshots", ["meter_type"])

    # ── 4. plan_subscriptions ─────────────────────────────────────────
    safe_create_table(
        "plan_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("plan_tier", sa.String(40), nullable=False),
        sa.Column("plan_name", sa.String(120), nullable=False),
        sa.Column("monthly_price", sa.Float, server_default="0.0", nullable=False),
        sa.Column("billing_interval", sa.String(20), server_default="'monthly'", nullable=False),
        sa.Column("included_credits", sa.Integer, server_default="0", nullable=False),
        sa.Column("max_seats", sa.Integer, server_default="1", nullable=False),
        sa.Column("max_brands", sa.Integer, server_default="1", nullable=False),
        sa.Column("features_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("meter_limits_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), server_default="'active'", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_plan_subscriptions_organization_id", "plan_subscriptions", ["organization_id"])
    safe_create_index("ix_plan_subscriptions_plan_tier", "plan_subscriptions", ["plan_tier"])
    safe_create_index("ix_plan_subscriptions_status", "plan_subscriptions", ["status"])

    # ── 5. pack_purchases ─────────────────────────────────────────────
    safe_create_table(
        "pack_purchases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("pack_type", sa.String(40), nullable=False),
        sa.Column("pack_id", sa.String(120), nullable=False),
        sa.Column("pack_name", sa.String(255), nullable=False),
        sa.Column("price", sa.Float, server_default="0.0", nullable=False),
        sa.Column("credits_awarded", sa.Integer, server_default="0", nullable=False),
        sa.Column("items_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("stripe_payment_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), server_default="'completed'", nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_pack_purchases_organization_id", "pack_purchases", ["organization_id"])
    safe_create_index("ix_pack_purchases_user_id", "pack_purchases", ["user_id"])
    safe_create_index("ix_pack_purchases_pack_type", "pack_purchases", ["pack_type"])
    safe_create_index("ix_pack_purchases_pack_id", "pack_purchases", ["pack_id"])
    safe_create_index("ix_pack_purchases_status", "pack_purchases", ["status"])

    # ── 6. multiplication_events ──────────────────────────────────────
    safe_create_table(
        "multiplication_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("trigger_context", sa.Text, nullable=True),
        sa.Column("offered", sa.Boolean, server_default="true", nullable=False),
        sa.Column("converted", sa.Boolean, server_default="false", nullable=False),
        sa.Column("revenue", sa.Float, server_default="0.0", nullable=False),
        sa.Column("offered_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("converted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_multiplication_events_organization_id", "multiplication_events", ["organization_id"])
    safe_create_index("ix_multiplication_events_user_id", "multiplication_events", ["user_id"])
    safe_create_index("ix_multiplication_events_event_type", "multiplication_events", ["event_type"])

    # ── 7. monetization_telemetry ─────────────────────────────────────
    safe_create_table(
        "monetization_telemetry",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "organization_id", UUID(as_uuid=True), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("event_name", sa.String(120), nullable=False),
        sa.Column("event_value", sa.Float, server_default="0.0", nullable=False),
        sa.Column("event_properties", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_monetization_telemetry_organization_id", "monetization_telemetry", ["organization_id"])
    safe_create_index("ix_monetization_telemetry_user_id", "monetization_telemetry", ["user_id"])
    safe_create_index("ix_monetization_telemetry_event_name", "monetization_telemetry", ["event_name"])
    safe_create_index("ix_monetization_telemetry_occurred_at", "monetization_telemetry", ["occurred_at"])

    # ── 8. subscriptions ──────────────────────────────────────────────
    safe_create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("customer_name", sa.String(255), nullable=True),
        sa.Column("plan_name", sa.String(120), nullable=False),
        sa.Column("plan_tier", sa.String(60), server_default="'standard'", nullable=False),
        sa.Column("mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("billing_interval", sa.String(20), server_default="'monthly'", nullable=False),
        sa.Column("status", sa.String(30), server_default="'active'", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column("metadata_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_subscriptions_brand_id", "subscriptions", ["brand_id"])
    safe_create_index("ix_subscriptions_customer_id", "subscriptions", ["customer_id"])
    safe_create_index("ix_subscriptions_plan_name", "subscriptions", ["plan_name"])
    safe_create_index("ix_subscriptions_plan_tier", "subscriptions", ["plan_tier"])
    safe_create_index("ix_subscriptions_status", "subscriptions", ["status"])
    safe_create_index("ix_subscriptions_stripe_subscription_id", "subscriptions", ["stripe_subscription_id"])

    # ── 9. subscription_events ────────────────────────────────────────
    safe_create_table(
        "subscription_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("subscriptions.id"), nullable=False),
        sa.Column("customer_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("old_mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("new_mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("mrr_delta", sa.Float, server_default="0.0", nullable=False),
        sa.Column("old_plan", sa.String(120), nullable=True),
        sa.Column("new_plan", sa.String(120), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("event_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_subscription_events_brand_id", "subscription_events", ["brand_id"])
    safe_create_index("ix_subscription_events_subscription_id", "subscription_events", ["subscription_id"])
    safe_create_index("ix_subscription_events_customer_id", "subscription_events", ["customer_id"])
    safe_create_index("ix_subscription_events_event_type", "subscription_events", ["event_type"])
    safe_create_index("ix_subscription_events_event_at", "subscription_events", ["event_at"])

    # ── 10. saas_metric_snapshots ─────────────────────────────────────
    safe_create_table(
        "saas_metric_snapshots",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period", sa.String(10), nullable=False),
        sa.Column("snapshot_date", sa.String(10), nullable=False),
        sa.Column("mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("arr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("new_mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("churned_mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("expansion_mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("contraction_mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("net_new_mrr", sa.Float, server_default="0.0", nullable=False),
        sa.Column("active_subscriptions", sa.Integer, server_default="0", nullable=False),
        sa.Column("churned_subscriptions", sa.Integer, server_default="0", nullable=False),
        sa.Column("new_subscriptions", sa.Integer, server_default="0", nullable=False),
        sa.Column("gross_churn_rate", sa.Float, server_default="0.0", nullable=False),
        sa.Column("net_revenue_retention", sa.Float, server_default="1.0", nullable=False),
        sa.Column("ltv", sa.Float, server_default="0.0", nullable=False),
        sa.Column("cac", sa.Float, server_default="0.0", nullable=False),
        sa.Column("quick_ratio", sa.Float, server_default="0.0", nullable=False),
        sa.Column("details_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_saas_metric_snapshots_brand_id", "saas_metric_snapshots", ["brand_id"])
    safe_create_index("ix_saas_metric_snapshots_period", "saas_metric_snapshots", ["period"])
    safe_create_index("ix_saas_metric_snapshots_snapshot_date", "saas_metric_snapshots", ["snapshot_date"])

    # ── 11. high_ticket_deals ─────────────────────────────────────────
    safe_create_table(
        "high_ticket_deals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_name", sa.String(255), nullable=False),
        sa.Column("customer_email", sa.String(255), nullable=True),
        sa.Column("deal_value", sa.Float, server_default="0.0", nullable=False),
        sa.Column("stage", sa.String(60), server_default="'awareness'", nullable=False),
        sa.Column("product_type", sa.String(80), nullable=False),
        sa.Column("source", sa.String(60), server_default="'content'", nullable=False),
        sa.Column("probability", sa.Float, server_default="0.1", nullable=False),
        sa.Column("expected_close_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("interactions", sa.Integer, server_default="0", nullable=False),
        sa.Column("score", sa.Float, server_default="0.0", nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("metadata_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_high_ticket_deals_brand_id", "high_ticket_deals", ["brand_id"])
    safe_create_index("ix_high_ticket_deals_stage", "high_ticket_deals", ["stage"])
    safe_create_index("ix_high_ticket_deals_product_type", "high_ticket_deals", ["product_type"])
    safe_create_index("ix_high_ticket_deals_source", "high_ticket_deals", ["source"])

    # ── 12. product_launches ──────────────────────────────────────────
    safe_create_table(
        "product_launches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand_id", UUID(as_uuid=True), sa.ForeignKey("brands.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("product_type", sa.String(80), nullable=False),
        sa.Column("price", sa.Float, server_default="0.0", nullable=False),
        sa.Column("launch_phase", sa.String(40), server_default="'planning'", nullable=False),
        sa.Column("registrations", sa.Integer, server_default="0", nullable=False),
        sa.Column("sales", sa.Integer, server_default="0", nullable=False),
        sa.Column("total_revenue", sa.Float, server_default="0.0", nullable=False),
        sa.Column("ad_spend", sa.Float, server_default="0.0", nullable=False),
        sa.Column("launch_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("funnel_metrics_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("launch_plan_json", JSONB, server_default=sa.text("'{}'::jsonb"), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    safe_create_index("ix_product_launches_brand_id", "product_launches", ["brand_id"])
    safe_create_index("ix_product_launches_product_type", "product_launches", ["product_type"])
    safe_create_index("ix_product_launches_launch_phase", "product_launches", ["launch_phase"])


def downgrade() -> None:
    for table in [
        "product_launches",
        "high_ticket_deals",
        "saas_metric_snapshots",
        "subscription_events",
        "subscriptions",
        "monetization_telemetry",
        "multiplication_events",
        "pack_purchases",
        "plan_subscriptions",
        "usage_meter_snapshots",
        "credit_transactions",
        "credit_ledgers",
    ]:
        safe_drop_table(table)
