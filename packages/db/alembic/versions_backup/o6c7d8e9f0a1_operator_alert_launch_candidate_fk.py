"""FK operator_alerts.linked_launch_candidate_id -> launch_candidates.id

Revision ID: o6c7d8e9f0a1
Revises: n5b6c7d8e9f0
"""

from collections.abc import Sequence
from typing import Union

from alembic import op

revision: str = "o6c7d8e9f0a1"
down_revision: Union[str, None] = "n5b6c7d8e9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_operator_alerts_linked_launch_candidate_id",
        "operator_alerts",
        "launch_candidates",
        ["linked_launch_candidate_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_operator_alerts_linked_launch_candidate_id",
        "operator_alerts",
        type_="foreignkey",
    )
