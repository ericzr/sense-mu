"""allow independent acceptance-dataset evaluations

Revision ID: 20260809_0019
Revises: 20260809_0018
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0019"
down_revision: str | None = "20260809_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_constraint(
            "uq_evaluations_model_version_id",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_evaluations_model_policy_source_dataset",
            ["model_version_id", "policy_id", "source", "dataset_version_id"],
        )
    op.execute(
        sa.text(
            """
            UPDATE model_versions
            SET status = 'validation_passed'
            WHERE status = 'approved'
              AND EXISTS (
                SELECT 1 FROM evaluations
                WHERE evaluations.model_version_id = model_versions.id
                  AND evaluations.source = 'training-validation'
                  AND evaluations.verdict = 'approved'
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE model_versions
            SET status = 'validation_failed'
            WHERE status = 'rejected'
              AND EXISTS (
                SELECT 1 FROM evaluations
                WHERE evaluations.model_version_id = model_versions.id
                  AND evaluations.source = 'training-validation'
                  AND evaluations.verdict = 'rejected'
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE model_versions SET status = 'approved' "
            "WHERE status = 'validation_passed'"
        )
    )
    op.execute(
        sa.text(
            "UPDATE model_versions SET status = 'rejected' "
            "WHERE status = 'validation_failed'"
        )
    )
    with op.batch_alter_table("evaluations") as batch_op:
        batch_op.drop_constraint(
            "uq_evaluations_model_policy_source_dataset",
            type_="unique",
        )
        batch_op.create_unique_constraint(
            "uq_evaluations_model_version_id",
            ["model_version_id", "policy_id"],
        )
