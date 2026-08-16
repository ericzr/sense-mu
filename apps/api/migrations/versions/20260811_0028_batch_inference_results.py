"""add immutable batch inference result records

Revision ID: 20260811_0028
Revises: 20260811_0027
Create Date: 2026-08-11
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260811_0028"
down_revision: str | None = "20260811_0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "batch_inference_results",
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=False),
        sa.Column("output_uri", sa.Text(), nullable=False),
        sa.Column("report_uri", sa.Text(), nullable=False),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["deployment_id"], ["deployments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index(
        "ix_batch_inference_results_deployment_completed_at",
        "batch_inference_results",
        ["deployment_id", "completed_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_batch_inference_results_deployment_completed_at",
        table_name="batch_inference_results",
    )
    op.drop_table("batch_inference_results")
