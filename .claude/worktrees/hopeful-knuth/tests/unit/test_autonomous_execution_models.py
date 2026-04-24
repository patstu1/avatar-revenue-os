"""ORM table names for autonomous execution control plane."""
from __future__ import annotations


class TestAutonomousExecutionModels:
    def test_tables(self):
        from packages.db.models.autonomous_execution import (
            AutomationExecutionPolicy,
            AutomationExecutionRun,
            ExecutionBlockerEscalation,
        )

        assert AutomationExecutionPolicy.__tablename__ == "automation_execution_policies"
        assert AutomationExecutionRun.__tablename__ == "automation_execution_runs"
        assert ExecutionBlockerEscalation.__tablename__ == "execution_blocker_escalations"
        assert "operating_mode" in {c.name for c in AutomationExecutionPolicy.__table__.columns}
        assert "exact_operator_steps_json" in {c.name for c in ExecutionBlockerEscalation.__table__.columns}
