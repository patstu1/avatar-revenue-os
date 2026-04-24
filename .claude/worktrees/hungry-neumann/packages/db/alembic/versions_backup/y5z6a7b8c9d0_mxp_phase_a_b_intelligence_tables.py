"""MXP Phase A+B: experiment, contribution, capacity, offer lifecycle, creative memory, audience state.

Revision ID: y5z6a7b8c9d0
Revises: x3y4z5a6b7c8
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "y5z6a7b8c9d0"
down_revision: Union[str, None] = "x3y4z5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Generated from ORM models (CreateTable compile) — FK order preserved.
    op.execute(
        sa.text("""
CREATE TABLE experiment_decisions (
    brand_id UUID NOT NULL,
    experiment_type VARCHAR(100) NOT NULL,
    target_scope_type VARCHAR(100) NOT NULL,
    target_scope_id UUID,
    hypothesis TEXT,
    expected_upside FLOAT NOT NULL,
    confidence_gap FLOAT NOT NULL,
    priority_score FLOAT NOT NULL,
    recommended_allocation FLOAT NOT NULL,
    promotion_rule_json JSONB,
    suppression_rule_json JSONB,
    explanation_json JSONB,
    status VARCHAR(50) NOT NULL,
    is_active BOOLEAN NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE experiment_outcomes (
    brand_id UUID NOT NULL,
    experiment_decision_id UUID NOT NULL,
    outcome_type VARCHAR(50) NOT NULL,
    winner_variant_id UUID,
    loser_variant_ids_json JSONB,
    confidence_score FLOAT NOT NULL,
    observed_uplift FLOAT NOT NULL,
    recommended_next_action VARCHAR(255),
    explanation_json JSONB,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id),
    FOREIGN KEY(experiment_decision_id) REFERENCES experiment_decisions (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE contribution_reports (
    brand_id UUID NOT NULL,
    attribution_model VARCHAR(100) NOT NULL,
    scope_type VARCHAR(100) NOT NULL,
    scope_id UUID,
    estimated_contribution_value FLOAT NOT NULL,
    contribution_score FLOAT NOT NULL,
    confidence_score FLOAT NOT NULL,
    caveats_json JSONB,
    explanation_json JSONB,
    is_active BOOLEAN NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE attribution_model_runs (
    brand_id UUID NOT NULL,
    model_type VARCHAR(100) NOT NULL,
    scope_definition_json JSONB,
    status VARCHAR(50) NOT NULL,
    summary_json JSONB,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE capacity_reports (
    brand_id UUID NOT NULL,
    capacity_type VARCHAR(100) NOT NULL,
    current_capacity FLOAT NOT NULL,
    used_capacity FLOAT NOT NULL,
    constrained_scope_json JSONB,
    recommended_volume FLOAT NOT NULL,
    recommended_throttle FLOAT,
    expected_profit_impact FLOAT NOT NULL,
    confidence_score FLOAT NOT NULL,
    explanation_json JSONB,
    is_active BOOLEAN NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE queue_allocation_decisions (
    brand_id UUID NOT NULL,
    queue_name VARCHAR(100) NOT NULL,
    priority_score FLOAT NOT NULL,
    allocated_capacity FLOAT NOT NULL,
    deferred_capacity FLOAT NOT NULL,
    reason_json JSONB,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE offer_lifecycle_reports (
    brand_id UUID NOT NULL,
    offer_id UUID NOT NULL,
    lifecycle_state VARCHAR(50) NOT NULL,
    health_score FLOAT NOT NULL,
    dependency_risk_score FLOAT NOT NULL,
    decay_score FLOAT NOT NULL,
    recommended_next_action VARCHAR(255),
    expected_impact_json JSONB,
    confidence_score FLOAT NOT NULL,
    explanation_json JSONB,
    is_active BOOLEAN NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id),
    FOREIGN KEY(offer_id) REFERENCES offers (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE offer_lifecycle_events (
    brand_id UUID NOT NULL,
    offer_id UUID NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    from_state VARCHAR(50),
    to_state VARCHAR(50),
    reason_json JSONB,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id),
    FOREIGN KEY(offer_id) REFERENCES offers (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE creative_memory_atoms (
    brand_id UUID NOT NULL,
    atom_type VARCHAR(100) NOT NULL,
    content_json JSONB,
    niche VARCHAR(200),
    audience_segment_id UUID,
    platform VARCHAR(50),
    monetization_type VARCHAR(100),
    account_type VARCHAR(50),
    funnel_stage VARCHAR(100),
    performance_summary_json JSONB,
    reuse_recommendations_json JSONB,
    originality_caution_score FLOAT NOT NULL,
    confidence_score FLOAT NOT NULL,
    is_active BOOLEAN NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE creative_memory_links (
    brand_id UUID NOT NULL,
    atom_id UUID NOT NULL,
    linked_scope_type VARCHAR(100) NOT NULL,
    linked_scope_id UUID NOT NULL,
    relationship_type VARCHAR(100) NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id),
    FOREIGN KEY(atom_id) REFERENCES creative_memory_atoms (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE audience_state_reports (
    brand_id UUID NOT NULL,
    audience_segment_id UUID,
    state_name VARCHAR(100) NOT NULL,
    state_score FLOAT NOT NULL,
    transition_probabilities_json JSONB,
    best_next_action VARCHAR(255) NOT NULL,
    confidence_score FLOAT NOT NULL,
    explanation_json JSONB,
    is_active BOOLEAN NOT NULL,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )
    op.execute(
        sa.text("""
CREATE TABLE audience_state_events (
    brand_id UUID NOT NULL,
    audience_segment_id UUID,
    from_state VARCHAR(100),
    to_state VARCHAR(100) NOT NULL,
    trigger_reason_json JSONB,
    id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY(brand_id) REFERENCES brands (id)
)
        """)
    )

    for stmt in (
        "CREATE INDEX ix_experiment_decisions_brand_id ON experiment_decisions (brand_id)",
        "CREATE INDEX ix_experiment_decisions_id ON experiment_decisions (id)",
        "CREATE INDEX ix_experiment_outcomes_id ON experiment_outcomes (id)",
        "CREATE INDEX ix_experiment_outcomes_brand_id ON experiment_outcomes (brand_id)",
        "CREATE INDEX ix_experiment_outcomes_experiment_decision_id ON experiment_outcomes (experiment_decision_id)",
        "CREATE INDEX ix_contribution_reports_id ON contribution_reports (id)",
        "CREATE INDEX ix_contribution_reports_brand_id ON contribution_reports (brand_id)",
        "CREATE INDEX ix_attribution_model_runs_id ON attribution_model_runs (id)",
        "CREATE INDEX ix_attribution_model_runs_brand_id ON attribution_model_runs (brand_id)",
        "CREATE INDEX ix_capacity_reports_id ON capacity_reports (id)",
        "CREATE INDEX ix_capacity_reports_brand_id ON capacity_reports (brand_id)",
        "CREATE INDEX ix_queue_allocation_decisions_brand_id ON queue_allocation_decisions (brand_id)",
        "CREATE INDEX ix_queue_allocation_decisions_id ON queue_allocation_decisions (id)",
        "CREATE INDEX ix_offer_lifecycle_reports_offer_id ON offer_lifecycle_reports (offer_id)",
        "CREATE INDEX ix_offer_lifecycle_reports_id ON offer_lifecycle_reports (id)",
        "CREATE INDEX ix_offer_lifecycle_reports_brand_id ON offer_lifecycle_reports (brand_id)",
        "CREATE INDEX ix_offer_lifecycle_events_id ON offer_lifecycle_events (id)",
        "CREATE INDEX ix_offer_lifecycle_events_offer_id ON offer_lifecycle_events (offer_id)",
        "CREATE INDEX ix_offer_lifecycle_events_brand_id ON offer_lifecycle_events (brand_id)",
        "CREATE INDEX ix_creative_memory_atoms_brand_id ON creative_memory_atoms (brand_id)",
        "CREATE INDEX ix_creative_memory_atoms_id ON creative_memory_atoms (id)",
        "CREATE INDEX ix_creative_memory_links_brand_id ON creative_memory_links (brand_id)",
        "CREATE INDEX ix_creative_memory_links_id ON creative_memory_links (id)",
        "CREATE INDEX ix_creative_memory_links_atom_id ON creative_memory_links (atom_id)",
        "CREATE INDEX ix_audience_state_reports_id ON audience_state_reports (id)",
        "CREATE INDEX ix_audience_state_reports_brand_id ON audience_state_reports (brand_id)",
        "CREATE INDEX ix_audience_state_events_brand_id ON audience_state_events (brand_id)",
        "CREATE INDEX ix_audience_state_events_id ON audience_state_events (id)",
    ):
        op.execute(sa.text(stmt))


def downgrade() -> None:
    op.execute(sa.text("DROP TABLE IF EXISTS audience_state_events CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS audience_state_reports CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS creative_memory_links CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS creative_memory_atoms CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS offer_lifecycle_events CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS offer_lifecycle_reports CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS queue_allocation_decisions CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS capacity_reports CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS attribution_model_runs CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS contribution_reports CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS experiment_outcomes CASCADE"))
    op.execute(sa.text("DROP TABLE IF EXISTS experiment_decisions CASCADE"))
