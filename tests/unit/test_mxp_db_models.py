"""Unit tests for all 11 MXP database model files — importability, table names, key fields."""
from __future__ import annotations


class TestExperimentDecisionModels:
    def test_model_structure(self):
        from packages.db.models.experiment_decisions import (
            ExperimentDecision,
            ExperimentOutcome,
            ExperimentOutcomeAction,
        )

        assert ExperimentDecision.__tablename__ == "experiment_decisions"
        assert ExperimentOutcome.__tablename__ == "experiment_outcomes"
        assert ExperimentOutcomeAction.__tablename__ == "experiment_outcome_actions"
        cols = {c.name for c in ExperimentDecision.__table__.columns}
        assert "brand_id" in cols
        assert "explanation_json" in cols
        assert "priority_score" in cols
        outcome_cols = {c.name for c in ExperimentOutcome.__table__.columns}
        assert "brand_id" in outcome_cols
        assert "confidence_score" in outcome_cols
        assert "observation_source" in outcome_cols
        action_cols = {c.name for c in ExperimentOutcomeAction.__table__.columns}
        assert "experiment_outcome_id" in action_cols
        assert "execution_status" in action_cols


class TestContributionModels:
    def test_model_structure(self):
        from packages.db.models.contribution import (
            AttributionModelRun,
            ContributionReport,
        )

        assert ContributionReport.__tablename__ == "contribution_reports"
        assert AttributionModelRun.__tablename__ == "attribution_model_runs"
        cols = {c.name for c in ContributionReport.__table__.columns}
        assert "brand_id" in cols
        assert "explanation_json" in cols
        assert "confidence_score" in cols


class TestCapacityModels:
    def test_model_structure(self):
        from packages.db.models.capacity import (
            CapacityReport,
            QueueAllocationDecision,
        )

        assert CapacityReport.__tablename__ == "capacity_reports"
        assert QueueAllocationDecision.__tablename__ == "queue_allocation_decisions"
        cols = {c.name for c in CapacityReport.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "explanation_json" in cols


class TestOfferLifecycleModels:
    def test_model_structure(self):
        from packages.db.models.offer_lifecycle import (
            OfferLifecycleEvent,
            OfferLifecycleReport,
        )

        assert OfferLifecycleReport.__tablename__ == "offer_lifecycle_reports"
        assert OfferLifecycleEvent.__tablename__ == "offer_lifecycle_events"
        cols = {c.name for c in OfferLifecycleReport.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "explanation_json" in cols
        assert "health_score" in cols


class TestCreativeMemoryModels:
    def test_model_structure(self):
        from packages.db.models.creative_memory import (
            CreativeMemoryAtom,
            CreativeMemoryLink,
        )

        assert CreativeMemoryAtom.__tablename__ == "creative_memory_atoms"
        assert CreativeMemoryLink.__tablename__ == "creative_memory_links"
        cols = {c.name for c in CreativeMemoryAtom.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "content_json" in cols


class TestRecoveryModels:
    def test_model_structure(self):
        from packages.db.models.recovery import RecoveryAction, RecoveryIncident

        assert RecoveryIncident.__tablename__ == "recovery_incidents"
        assert RecoveryAction.__tablename__ == "recovery_actions"
        cols = {c.name for c in RecoveryIncident.__table__.columns}
        assert "brand_id" in cols
        assert "explanation_json" in cols
        assert "severity" in cols
        assert "escalation_state" in cols
        assert "recommended_recovery_action" in cols
        action_cols = {c.name for c in RecoveryAction.__table__.columns}
        assert "brand_id" in action_cols
        assert "confidence_score" in action_cols


class TestDealDeskModels:
    def test_model_structure(self):
        from packages.db.models.deal_desk import (
            DealDeskEvent,
            DealDeskRecommendation,
        )

        assert DealDeskRecommendation.__tablename__ == "deal_desk_recommendations"
        assert DealDeskEvent.__tablename__ == "deal_desk_events"
        cols = {c.name for c in DealDeskRecommendation.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "explanation_json" in cols


class TestAudienceStateModels:
    def test_model_structure(self):
        from packages.db.models.audience_state import (
            AudienceStateEvent,
            AudienceStateReport,
        )

        assert AudienceStateReport.__tablename__ == "audience_state_reports"
        assert AudienceStateEvent.__tablename__ == "audience_state_events"
        cols = {c.name for c in AudienceStateReport.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "explanation_json" in cols
        assert "state_name" in cols


class TestReputationModels:
    def test_model_structure(self):
        from packages.db.models.reputation import ReputationEvent, ReputationReport

        assert ReputationReport.__tablename__ == "reputation_reports"
        assert ReputationEvent.__tablename__ == "reputation_events"
        cols = {c.name for c in ReputationReport.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "reputation_risk_score" in cols


class TestMarketTimingModels:
    def test_model_structure(self):
        from packages.db.models.market_timing import (
            MacroSignalEvent,
            MarketTimingReport,
        )

        assert MarketTimingReport.__tablename__ == "market_timing_reports"
        assert MacroSignalEvent.__tablename__ == "macro_signal_events"
        cols = {c.name for c in MarketTimingReport.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "explanation_json" in cols
        assert "timing_score" in cols


class TestKillLedgerModels:
    def test_model_structure(self):
        from packages.db.models.kill_ledger import (
            KillHindsightReview,
            KillLedgerEntry,
        )

        assert KillLedgerEntry.__tablename__ == "kill_ledger_entries"
        assert KillHindsightReview.__tablename__ == "kill_hindsight_reviews"
        cols = {c.name for c in KillLedgerEntry.__table__.columns}
        assert "brand_id" in cols
        assert "confidence_score" in cols
        assert "kill_reason" in cols
        review_cols = {c.name for c in KillHindsightReview.__table__.columns}
        assert "brand_id" in review_cols
        assert "was_correct_kill" in review_cols
